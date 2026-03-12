#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_daemon.py v2 - 多机 GPU 池化评测流水线守护进程

功能：
  - 多机 GPU 池化调度（可配置 N 台机器，每台 8 卡，最多 48 并发）
  - 显式实验组列表控制（手动指定要跑的组）
  - 每台机器 load/unload 串行化（避免代理 API 冲突）
  - 评测容器独立输出目录 + 自动归集到 fmt/
  - 状态持久化，支持断点续跑
  - 管理容器化部署（Docker-out-of-Docker）

用法：
  python3 pipeline_daemon.py [选项]

  --work-dir       工作目录，存放输出和状态文件 (默认 /app/workdir)
  --workspace      Docker 工作区，含 .env/data/code  (默认 /opt/eval_workspace)
  --max-workers    最大并发评测数 (默认 48)
  --poll-interval  轮询间隔秒数   (默认 300)
  --dry-run        只打印调度计划，不实际执行
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

# ── 默认配置 ──────────────────────────────────────────────────────────────

def get_default_config() -> dict:
    """返回默认配置字典，所有可配置项集中在此。"""
    return {
        # GPU 机器池：每台机器运行代理 API（:8090），提供 8 卡推理服务
        # 新机器加入只需在此追加一行
        "gpu_machines": [
            {"ip": "188.109.35.159", "port": 8090, "slots": 8},
            {"ip": "188.109.35.148", "port": 8090, "slots": 8},
            {"ip": "188.109.35.149", "port": 8090, "slots": 8},
            {"ip": "188.109.35.150", "port": 8090, "slots": 8},
            {"ip": "188.109.35.151", "port": 8090, "slots": 8},
            {"ip": "188.109.35.152", "port": 8090, "slots": 8},
        ],

        # 本轮要跑的实验组（手动维护，只有在此列表中的组才会被调度）
        "experiment_groups": [
            "pt14_sft0",
            "pt15_sft0",
            "pt16_sft0",
            "pt17_sft0",
            "pt18_sft0",
            "pt19_sft0",
        ],

        # 路径配置
        "models_dir": "/dpc/exp/v260306",
        "model_subpath": "sft",
        "workspace": "/opt/eval_workspace",
        "work_dir": "/app/workdir",

        # 并发与超时
        "max_workers": 48,
        "poll_interval": 300,
        "eval_timeout": 14400,
        "load_timeout": 600,
        "unload_timeout": 600,

        # Docker 配置
        "image_tag": "benchmark-eval:latest",

        # 评测任务列表
        "eval_tasks": ["1", "34", "36", "43", "44", "60"],
        "eval_generic": [
            "mmlu_redux_gen_5_shot_str", "ceval_gen_0_shot_str",
            "gpqa_gen_0_shot_str", "bbh_gen_3_shot_cot_chat",
            "BFCL_gen_simple", "ifeval_0_shot_gen_str",
            "math500_gen_0_shot_cot_chat_prompt", "aime2025_gen_0_shot_chat_prompt",
            "humaneval_gen_0_shot", "livecodebench_0_shot_chat_v6",
            "telemath_gen_0_cot_shot", "teleqna_gen_0_shot",
            "tspec_gen_0_shot", "teledata_gen_0_shot",
            "telequad_gen_0_shot", "tele_exam_gen_0_shot",
            "tele_exam_gen_0_shot_str",
        ],
    }


# ── 状态读写（线程安全）──────────────────────────────────────────────────

def load_state(state_file: Path) -> dict:
    """加载流水线状态；文件不存在时返回空默认值。"""
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as e:
            logging.warning("无法解析 state 文件 %s: %s", state_file, e)
    return {
        "last_scan": datetime.now().isoformat(timespec="seconds"),
        "stats": {},
        "models": {},
    }


def save_state(state: dict, state_file: Path, lock: threading.Lock) -> None:
    """原子写入 state（先写 .tmp 再 rename）。"""
    tmp = state_file.with_suffix(".tmp")
    with lock:
        state["last_scan"] = datetime.now().isoformat(timespec="seconds")
        state["stats"] = _compute_stats(state)
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(state_file)


def _compute_stats(state: dict) -> dict:
    counts = {"total": 0, "done": 0, "evaluating": 0, "queued": 0, "failed": 0}
    for m in state["models"].values():
        counts["total"] += 1
        s = m.get("status", "queued")
        if s in counts:
            counts[s] += 1
    return counts


# ── GPU 机器池调度器 ─────────────────────────────────────────────────────

class MachinePool:
    """GPU 机器池管理器。

    职责：
    - 跟踪每台机器的槽位使用量
    - 分配/释放槽位
    - 为每台机器提供独立的 Lock（保证 load/unload 串行化）
    """

    def __init__(self, machines: List[dict]):
        self._machines = machines
        self._used: Dict[str, int] = {m["ip"]: 0 for m in machines}
        self._locks: Dict[str, threading.Lock] = {m["ip"]: threading.Lock() for m in machines}
        self._pool_lock = threading.Lock()  # 保护 _used 的并发访问

    def allocate(self) -> Optional[dict]:
        """分配一个空闲槽位，返回 machine dict；无空闲返回 None。"""
        with self._pool_lock:
            for m in self._machines:
                ip = m["ip"]
                if self._used[ip] < m["slots"]:
                    self._used[ip] += 1
                    return dict(m)  # 返回副本
            return None

    def release(self, ip: str) -> None:
        """释放指定机器的一个槽位。"""
        with self._pool_lock:
            if ip in self._used and self._used[ip] > 0:
                self._used[ip] -= 1

    def get_lock(self, ip: str) -> threading.Lock:
        """获取指定机器的操作锁（load/unload 串行化）。"""
        return self._locks[ip]

    def status(self) -> Dict[str, dict]:
        """返回每台机器的使用状态。"""
        with self._pool_lock:
            return {
                m["ip"]: {"used": self._used[m["ip"]], "total": m["slots"]}
                for m in self._machines
            }


# ── 部署 API 客户端 ──────────────────────────────────────────────────────

class DeployError(Exception):
    """部署 API 业务错误"""
    pass


def load_model(deploy_api: str, model_path: str, timeout: int = 600) -> dict:
    """调用 /load_model，成功返回 config dict，失败抛 DeployError。

    注意：此函数本身不持锁，调用方应通过 MachinePool.get_lock() 串行化。
    """
    resp = requests.post(
        f"{deploy_api}/load_model",
        json={"model_path": model_path},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise DeployError(f"load_model 失败 (code={data.get('code')}): {data.get('message', data)}")
    return data["config"]


def unload_model(deploy_api: str, model_id: str, timeout: int = 600) -> None:
    """调用 /unload_model 卸载模型。忽略"未找到"错误（已被卸载）。"""
    try:
        resp = requests.post(
            f"{deploy_api}/unload_model",
            json={"model_id": model_id},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") not in (200, 10001):
            logging.warning(f"unload_model 异常响应: {data}")
    except requests.exceptions.ConnectionError as e:
        logging.error(f"unload_model 网络连接失败（NPU 可能未释放）: {e}")
    except requests.exceptions.Timeout as e:
        logging.error(f"unload_model 请求超时（NPU 可能未释放）: {e}")
    except Exception as e:
        logging.warning(f"unload_model 失败（忽略）: {e}")


def parse_serving_url(url: str):
    """从推理服务 URL 解析 (host_ip, host_port)。"""
    parsed = urlparse(url)
    if parsed.port is None:
        raise ValueError(f"URL 中缺少端口号: {url}")
    return parsed.hostname, str(parsed.port)


# ── Docker 命令构造与 fmt 归集 ─────────────────────────────────────────────

def build_docker_cmd(
    exp_name: str,
    task_id: str,
    output_dir: Path,
    host_ip: str,
    host_port: str,
    workspace: Path,
    config: dict,
) -> list:
    """构造 docker run 命令。

    关键设计：
    - data/ 和 code/ 以只读方式共享挂载（:ro），所有容器复用同一份
    - outputs/ 每个实验组独立挂载（可写），避免并发冲突
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "--rm",
        "-e", "PYTHONUNBUFFERED=1",
        "--env-file", str(workspace / ".env"),
        "-e", f"LOCAL_HOST_IP={host_ip}",
        "-e", f"LOCAL_HOST_PORT={host_port}",
        "-e", f"LOCAL_MODEL_NAME={exp_name}",
        "-e", "LOCAL_CONCURRENCY=50",
        "-v", f"{workspace}/data:/app/data:ro",
        "-v", f"{workspace}/code/eval_entry.py:/app/eval_entry.py:ro",
        "-v", f"{workspace}/code/scripts:/app/scripts:ro",
        "-v", f"{output_dir}:/app/outputs",
        config["image_tag"],
        "python", "eval_entry.py",
        "--task-id", task_id,
        "--model-config", "local_qwen",
    ]
    if config["eval_tasks"]:
        cmd += ["--tasks"] + config["eval_tasks"]
    if config["eval_generic"]:
        cmd += ["--generic-datasets"] + config["eval_generic"]
    return cmd


def collect_to_fmt(exp_name: str, task_id: str, output_dir: Path, fmt_dir: Path) -> None:
    """将评测结果从 output_dir/<task_id>/ 归集到 fmt/<exp_name>/。

    目标结构（与现有 outputs/fmt/ 一致）：
      fmt/<exp_name>/
      ├── report.json
      ├── report.md
      └── details/
    """
    src = output_dir / task_id
    if not src.exists():
        logging.warning(f"[{exp_name}] 评测输出目录不存在，跳过 fmt 归集: {src}")
        return

    dst = fmt_dir / exp_name
    dst.mkdir(parents=True, exist_ok=True)

    for fname in ("report.json", "report.md"):
        src_file = src / fname
        if src_file.exists():
            shutil.copy2(src_file, dst / fname)

    src_details = src / "details"
    if src_details.exists():
        dst_details = dst / "details"
        if dst_details.exists():
            shutil.rmtree(dst_details)
        shutil.copytree(src_details, dst_details)

    logging.info(f"[{exp_name}] 结果已归集到 {dst}")


def read_report_accuracy(report_path: Path) -> Optional[float]:
    """读取 report.json，返回 avg_accuracy。"""
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        return data.get("avg_accuracy")
    except Exception:
        return None


# ── Worker 线程 ────────────────────────────────────────────────────────────

def eval_worker(exp_name: str, config: dict, pool: MachinePool) -> dict:
    """Worker 线程：allocate → lock → load → eval → unload → release → collect。

    Args:
        exp_name: 实验组名，如 "pt14_sft0"
        config: 配置字典（含 work_dir, workspace, dry_run 等）
        pool: GPU 机器池

    Returns:
        dict with status, machine_ip, model_id, avg_accuracy, error 等
    """
    model_path = f"{config['models_dir']}/{exp_name}/{config['model_subpath']}"
    task_id = f"eval_{exp_name}"
    work_dir = Path(config["work_dir"])
    output_dir = work_dir / exp_name / "outputs"
    log_dir = work_dir / exp_name / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    log = logging.getLogger(__name__)
    log.info(f"[{exp_name}] 开始评测")

    # dry-run 模式
    if config.get("dry_run"):
        log.info(f"[{exp_name}] dry-run 模式，跳过")
        return {"status": "done", "model_id": "dry-run", "machine_ip": "dry-run",
                "task_id": task_id, "avg_accuracy": None, "report_path": None}

    # ① 分配机器槽位
    machine = pool.allocate()
    if machine is None:
        return {"status": "failed", "error": "无空闲 GPU 槽位", "machine_ip": None,
                "model_id": None, "task_id": task_id, "avg_accuracy": None}

    machine_ip = machine["ip"]
    deploy_api = f"http://{machine_ip}:{machine['port']}"
    model_id = None

    try:
        # ② 串行化 load（per-machine lock）
        machine_lock = pool.get_lock(machine_ip)
        log.info(f"[{exp_name}] 等待机器 {machine_ip} 的加载锁...")
        with machine_lock:
            log.info(f"[{exp_name}] 调用 load_model @ {machine_ip}")
            model_config = load_model(deploy_api, model_path, timeout=config["load_timeout"])
            model_id = model_config["model_id"]
            serving_url = model_config["url"]

        host_ip, host_port = parse_serving_url(serving_url)
        log.info(f"[{exp_name}] 模型已部署: {machine_ip}, port={host_port}, model_id={model_id}")

        # ③ 启动评测容器（不持锁，可并行）
        cmd = build_docker_cmd(
            exp_name=exp_name, task_id=task_id, output_dir=output_dir,
            host_ip=host_ip, host_port=host_port,
            workspace=Path(config["workspace"]), config=config,
        )
        log.info(f"[{exp_name}] 启动评测容器...")
        proc = subprocess.run(cmd, timeout=config["eval_timeout"])

        # ④ 读取报告
        report_path = output_dir / task_id / "report.json"
        avg_accuracy = read_report_accuracy(report_path)
        status = "done" if proc.returncode == 0 else "failed"
        error = None if proc.returncode == 0 else f"docker exit code {proc.returncode}"
        log.info(f"[{exp_name}] 评测完成: {status}, accuracy={avg_accuracy}")

        # ⑤ 归集到 fmt
        if status == "done":
            fmt_dir = work_dir / "fmt"
            collect_to_fmt(exp_name, task_id, output_dir, fmt_dir)

        return {
            "status": status, "model_id": model_id, "machine_ip": machine_ip,
            "serving_url": serving_url, "task_id": task_id,
            "avg_accuracy": avg_accuracy, "error": error,
            "report_path": str(report_path) if report_path.exists() else None,
        }

    except DeployError as e:
        log.error(f"[{exp_name}] 部署失败: {e}")
        return {"status": "failed", "error": str(e), "model_id": model_id,
                "machine_ip": machine_ip, "task_id": task_id, "avg_accuracy": None}

    except subprocess.TimeoutExpired:
        log.error(f"[{exp_name}] 评测超时")
        return {"status": "failed", "error": f"eval timeout {config['eval_timeout']}s",
                "model_id": model_id, "machine_ip": machine_ip, "task_id": task_id,
                "avg_accuracy": None}

    except Exception as e:
        log.error(f"[{exp_name}] 未知错误: {e}", exc_info=True)
        return {"status": "failed", "error": str(e), "model_id": model_id,
                "machine_ip": machine_ip, "task_id": task_id, "avg_accuracy": None}

    finally:
        # ⑥ 无论成功失败，释放 NPU + 释放槽位
        if model_id:
            log.info(f"[{exp_name}] 卸载模型 {model_id} @ {machine_ip}")
            with machine_lock:
                unload_model(deploy_api, model_id, timeout=config["unload_timeout"])
        pool.release(machine_ip)
