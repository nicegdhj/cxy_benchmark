#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_daemon.py - 持续评测流水线守护进程

功能：
  - 每 10 分钟扫描 /dpc/exp/v260306/ 下新完成的训练实验（.done 标记）
  - 最多 8 个并发评测（1 个模型 1 张 NPU）
  - 每个模型独立输出目录，避免并发写冲突
  - 状态持久化，支持 Daemon 重启后续跑
  - 实时生成横向对比报告

用法：
  python3 scripts/pipeline_daemon.py [选项]

  --models-dir   训练产物根目录 (默认 /dpc/exp/v260306)
  --eval-dir     评测输出根目录 (默认 /dpc/exp/eval_v260306)
  --workspace    Docker 工作区   (默认 /opt/eval_workspace)
  --deploy-api   部署 API 地址   (默认 http://188.109.35.159:8080)
  --max-workers  最大并发数       (默认 8)
  --poll-interval 轮询间隔秒数   (默认 600)
  --dry-run      只扫描，不实际评测
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests

# ── 默认配置（可通过命令行覆盖）─────────────────────────────────────────
DEFAULT_MODELS_DIR    = "/dpc/exp/v260306"
DEFAULT_EVAL_DIR      = "/dpc/exp/eval_v260306"
DEFAULT_WORKSPACE     = "/opt/eval_workspace"
DEFAULT_DEPLOY_API    = "http://188.109.35.159:8080"
DEFAULT_MAX_WORKERS   = 8
DEFAULT_POLL_INTERVAL = 600   # 10 分钟
DEFAULT_EVAL_TIMEOUT  = 14400  # 4 小时
MODEL_SUBPATH         = "sft"
DONE_MARKER           = ".done"
IMAGE_TAG             = "benchmark-eval:latest"

EVAL_TASKS = ["1", "34", "36", "43", "44", "60"]
EVAL_GENERIC = [
    "mmlu_redux_gen_5_shot_str", "ceval_gen_0_shot_str",
    "gpqa_gen_0_shot_str", "bbh_gen_3_shot_cot_chat",
    "BFCL_gen_simple", "ifeval_0_shot_gen_str",
    "math500_gen_0_shot_cot_chat_prompt", "aime2025_gen_0_shot_chat_prompt",
    "humaneval_gen_0_shot", "livecodebench_0_shot_chat_v6",
    "telemath_gen_0_cot_shot", "teleqna_gen_0_shot",
    "tspec_gen_0_shot", "teledata_gen_0_shot",
    "telequad_gen_0_shot", "tele_exam_gen_0_shot",
    "tele_exam_gen_0_shot_str",
]


# ── 状态读写（线程安全）──────────────────────────────────────────────────

def load_state(state_file: Path) -> dict:
    """从 state_file 加载流水线状态；文件不存在时返回空默认值。"""
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as e:
            logging.warning("无法解析 state 文件 %s，将从头开始：%s", state_file, e)
    return {
        "last_scan": datetime.now().isoformat(timespec="seconds"),
        "stats": {},
        "models": {},
    }


def save_state(state: dict, state_file: Path, lock: threading.Lock) -> None:
    """将状态原子写入 state_file（先写临时文件再 rename，防止写坏）。"""
    tmp = state_file.with_suffix(".tmp")
    with lock:
        state["last_scan"] = datetime.now().isoformat(timespec="seconds")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(state_file)


def _compute_stats(state: dict) -> dict:
    counts = {"total_discovered": 0, "done": 0, "evaluating": 0, "queued": 0, "failed": 0}
    for m in state["models"].values():
        counts["total_discovered"] += 1
        s = m.get("status", "queued")
        if s in counts:
            counts[s] += 1
    return counts


def scan_done_experiments(models_dir: Path) -> set:
    """扫描 models_dir 下所有已完成训练的实验名（有 .done 且有 sft/ 子目录）。

    Returns:
        set of experiment directory names (str), e.g. {"pt0_sft0", "pt0_sft1"}
    """
    done = set()
    if not models_dir.exists():
        return done
    for exp_dir in models_dir.iterdir():
        if not exp_dir.is_dir():
            continue
        if (exp_dir / DONE_MARKER).exists() and (exp_dir / MODEL_SUBPATH).is_dir():
            done.add(exp_dir.name)
    return done


def parse_serving_url(url: str):
    """从部署 API 返回的 URL 中解析出 (host_ip, host_port)。

    Args:
        url: e.g. "http://188.109.35.159:10051/v1/chat/completions"，必须包含端口号

    Returns:
        (host_ip: str, host_port: str)

    Raises:
        ValueError: URL 中不含端口号
    """
    parsed = urlparse(url)
    if parsed.port is None:
        raise ValueError(f"URL 中缺少端口号: {url}")
    return parsed.hostname, str(parsed.port)


def build_docker_cmd(
    exp_name: str,
    task_id: str,
    output_dir: Path,
    host_ip: str,
    host_port: str,
    workspace: Path,
) -> list:
    """构造 docker run 命令列表。

    设计要点：
    - 每个模型挂载独立输出目录 output_dir → /app/outputs（避免并发冲突）
    - LOCAL_HOST_IP / LOCAL_HOST_PORT 覆盖 .env 中的静态值
    - LOCAL_MODEL_NAME 设为实验目录名，方便报告中识别
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "--rm",
        "-e", "PYTHONUNBUFFERED=1",
        "--env-file", str(workspace / ".env"),
        # 覆盖为本次动态分配的模型服务地址
        "-e", f"LOCAL_HOST_IP={host_ip}",
        "-e", f"LOCAL_HOST_PORT={host_port}",
        "-e", f"LOCAL_MODEL_NAME={exp_name}",
        "-e", "LOCAL_CONCURRENCY=50",
        # 数据（共享只读）
        "-v", f"{workspace}/data:/app/data",
        # 代码（共享只读）
        "-v", f"{workspace}/code/eval_entry.py:/app/eval_entry.py",
        "-v", f"{workspace}/code/scripts:/app/scripts",
        # 输出目录（每个模型独立，并发安全）
        "-v", f"{output_dir}:/app/outputs",
        IMAGE_TAG,
        "python", "eval_entry.py",
        "--task-id", task_id,
        "--model-config", "local_qwen",
    ]
    if EVAL_TASKS:
        cmd += ["--tasks"] + EVAL_TASKS
    if EVAL_GENERIC:
        cmd += ["--generic-datasets"] + EVAL_GENERIC
    return cmd


class DeployError(Exception):
    """部署 API 业务错误（非网络错误）"""
    pass


def load_model(deploy_api: str, model_path: str, timeout: int = 120) -> dict:
    """调用 /load_model，返回 config dict。

    Args:
        deploy_api: 如 "http://188.109.35.159:8080"
        model_path: 如 "/dpc/exp/v260306/pt0_sft0/sft"

    Returns:
        {"model_id": "...", "model_name": "...", "url": "..."}

    Raises:
        DeployError: API 返回非 200 业务码（如"无空闲npu"）
        requests.RequestException: 网络连接失败
    """
    resp = requests.post(
        f"{deploy_api}/load_model",
        json={"model_path": model_path},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise DeployError(f"load_model 失败: {data.get('message', data)}")
    return data["config"]


def unload_model(deploy_api: str, model_id: str, timeout: int = 30) -> None:
    """调用 /unload_model 卸载模型，释放 NPU。忽略"未找到模型ID"错误（已被卸载）。"""
    try:
        resp = requests.post(
            f"{deploy_api}/unload_model",
            json={"model_id": model_id},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") not in (200, 10001):  # 10001 = 未找到（已卸载）
            logging.warning(f"unload_model 异常响应: {data}")
    except Exception as e:
        logging.warning(f"unload_model 失败（忽略）: {e}")
