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
