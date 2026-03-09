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
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "last_scan": datetime.now().isoformat(timespec="seconds"),
        "stats": {},
        "models": {},
    }


def save_state(state: dict, state_file: Path, lock: threading.Lock) -> None:
    """将状态原子写入 state_file（先写临时文件再 rename，防止写坏）。"""
    state["last_scan"] = datetime.now().isoformat(timespec="seconds")
    tmp = state_file.with_suffix(".tmp")
    with lock:
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
