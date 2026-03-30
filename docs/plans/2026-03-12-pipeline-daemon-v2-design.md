# Pipeline Daemon v2 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构评测流水线守护进程，支持多机 GPU 池化调度（6 台 × 8 卡 = 48 并发）、显式实验组控制、独立输出目录、结果自动归集到 fmt/、管理容器化部署。

**Architecture:** 单 Python 进程（`pipeline_daemon.py`）内运行主轮询循环 + ThreadPoolExecutor（最多 48 worker）。每台 GPU 机器一把 Lock 保证 load/unload 串行（避免代理 API 冲突），不同机器之间并行。Daemon 本身运行在一个轻量管理容器中（挂载 Docker Socket），可在任意共享存储机器上快速迁移恢复。

**Tech Stack:** Python 3.10, `requests`, `concurrent.futures.ThreadPoolExecutor`, `threading.Lock`, `subprocess`, Docker CLI, `shutil`

---

## 与 v1 的关键差异

| 维度 | v1 | v2 |
|------|-----|-----|
| GPU 机器 | 单机（1 个 DEPLOY_API） | 多机池化（可配置 N 台，每台 8 卡） |
| 实验组发现 | 自动扫描 `.done` 文件 | 显式列表 `EXPERIMENT_GROUPS` |
| 最大并发 | 8 | 48（6×8） |
| 输出目录 | 集中 `/dpc/exp/eval_v260306/<exp>/` | 当前工作目录 `./<exp>/outputs/` |
| 结果归集 | 无 | 自动复制到 `fmt/<exp>/` |
| 数据共享 | 每次解压 | 一次部署，共享挂载 |
| 部署方式 | 宿主机直接运行 | 管理容器（Docker-out-of-Docker） |
| load/unload 并发控制 | 无 | 每台机器一把锁，串行化 |
| 启动脚本 | bash `run_one_pipline.sh` | 纯 Python（废弃 bash） |

## 文件清单

| 操作 | 文件路径 | 说明 |
|------|---------|------|
| **重写** | `scripts/pipline_run/pipeline_daemon.py` | 核心守护进程 v2 |
| **重写** | `tests/test_pipeline_daemon.py` | 对应测试 |
| **新增** | `Dockerfile.manager` | 管理容器镜像 |
| **废弃** | `scripts/pipline_run/run_one_pipline.sh` | 启动逻辑合并到 Python |
| **不变** | `eval_entry.py`, `run_mixed_benchmark.sh`, `Dockerfile`, `package_deploy.sh` | 评测核心不变 |

---

### Task 1: 配置模块与 GPU 机器池

**Files:**
- Create: `scripts/pipline_run/pipeline_daemon.py`（从头重写）
- Create: `tests/test_pipeline_daemon.py`（从头重写）

**Step 1: 写失败测试**

```python
# tests/test_pipeline_daemon.py
import importlib.util
import json
import threading
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def daemon():
    """加载 pipeline_daemon 模块"""
    spec = importlib.util.spec_from_file_location(
        "pipeline_daemon",
        Path(__file__).parent.parent / "scripts" / "pipline_run" / "pipeline_daemon.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_config(daemon):
    """默认配置包含必要字段"""
    cfg = daemon.get_default_config()
    assert "gpu_machines" in cfg
    assert "experiment_groups" in cfg
    assert "workspace" in cfg
    assert cfg["max_workers"] == 48


def test_gpu_machines_total_slots(daemon):
    """GPU 机器池总槽位计算正确"""
    cfg = daemon.get_default_config()
    total = sum(m["slots"] for m in cfg["gpu_machines"])
    assert total == 48
```

**Step 2: 运行确认测试失败**

```bash
python3 -m pytest tests/test_pipeline_daemon.py::test_default_config -v
```
Expected: 失败（模块不存在或无 `get_default_config`）

**Step 3: 实现配置模块**

重写 `scripts/pipline_run/pipeline_daemon.py`，先写骨架：

```python
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
        "models_dir": "/dpc/exp/v260306",       # 训练产物根目录（共享存储）
        "model_subpath": "sft",                  # 模型权重子目录
        "workspace": "/opt/eval_workspace",      # Docker 工作区（.env/data/code）
        "work_dir": "/app/workdir",              # daemon 工作目录（状态/输出/fmt）

        # 并发与超时
        "max_workers": 48,
        "poll_interval": 300,                    # 轮询间隔（秒），5 分钟
        "eval_timeout": 14400,                   # 单模型评测超时（秒），4 小时
        "load_timeout": 600,                     # load_model API 超时（秒），10 分钟
        "unload_timeout": 600,                   # unload_model API 超时（秒），10 分钟

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
```

**Step 4: 运行测试确认通过**

```bash
python3 -m pytest tests/test_pipeline_daemon.py::test_default_config \
                  tests/test_pipeline_daemon.py::test_gpu_machines_total_slots -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py tests/test_pipeline_daemon.py
git commit -m "feat(v2): pipeline daemon 骨架与 GPU 机器池配置"
```

---

### Task 2: 状态管理（复用 v1 逻辑，适配新结构）

**Files:**
- Modify: `scripts/pipline_run/pipeline_daemon.py`
- Modify: `tests/test_pipeline_daemon.py`

**Step 1: 写失败测试**

追加到测试文件：

```python
def test_load_state_creates_default(tmp_path, daemon):
    """state 文件不存在时返回空默认值"""
    state = daemon.load_state(tmp_path / "state.json")
    assert state["models"] == {}
    assert "last_scan" in state


def test_save_and_reload_state(tmp_path, daemon):
    """保存后重新加载内容一致"""
    lock = threading.Lock()
    state_file = tmp_path / "state.json"
    state = daemon.load_state(state_file)
    state["models"]["pt14_sft0"] = {"status": "queued", "machine_ip": "188.109.35.159"}
    daemon.save_state(state, state_file, lock)

    reloaded = daemon.load_state(state_file)
    assert reloaded["models"]["pt14_sft0"]["status"] == "queued"
    assert reloaded["models"]["pt14_sft0"]["machine_ip"] == "188.109.35.159"
```

**Step 2: 运行确认失败**

**Step 3: 实现状态读写**

追加到 `pipeline_daemon.py`：

```python
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
```

**Step 4: 运行测试确认通过**

```bash
python3 -m pytest tests/test_pipeline_daemon.py -v -k "state"
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py tests/test_pipeline_daemon.py
git commit -m "feat(v2): 状态读写与原子持久化"
```

---

### Task 3: GPU 机器池调度器（含 per-machine Lock）

**Files:**
- Modify: `scripts/pipline_run/pipeline_daemon.py`
- Modify: `tests/test_pipeline_daemon.py`

**Step 1: 写失败测试**

```python
def test_machine_pool_allocate(daemon):
    """分配槽位：选择有空闲槽位的机器"""
    machines = [
        {"ip": "10.0.0.1", "port": 8090, "slots": 2},
        {"ip": "10.0.0.2", "port": 8090, "slots": 2},
    ]
    pool = daemon.MachinePool(machines)

    # 分配第 1 个：应该从第一台开始
    m1 = pool.allocate()
    assert m1 is not None
    assert m1["ip"] in ("10.0.0.1", "10.0.0.2")

    # 把第一台占满
    pool.allocate()  # 第 1 台第 2 个槽位
    pool.allocate()  # 第 2 台第 1 个槽位
    pool.allocate()  # 第 2 台第 2 个槽位

    # 全满，分配失败
    assert pool.allocate() is None


def test_machine_pool_release(daemon):
    """释放槽位后可以重新分配"""
    machines = [{"ip": "10.0.0.1", "port": 8090, "slots": 1}]
    pool = daemon.MachinePool(machines)

    m = pool.allocate()
    assert m is not None
    assert pool.allocate() is None  # 满了

    pool.release("10.0.0.1")
    m2 = pool.allocate()
    assert m2 is not None  # 释放后可再分配


def test_machine_pool_get_lock(daemon):
    """每台机器有独立的锁"""
    machines = [
        {"ip": "10.0.0.1", "port": 8090, "slots": 2},
        {"ip": "10.0.0.2", "port": 8090, "slots": 2},
    ]
    pool = daemon.MachinePool(machines)
    lock1 = pool.get_lock("10.0.0.1")
    lock2 = pool.get_lock("10.0.0.2")
    assert lock1 is not lock2
    assert isinstance(lock1, type(threading.Lock()))
```

**Step 2: 运行确认失败**

**Step 3: 实现 MachinePool**

```python
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
```

**Step 4: 运行测试确认通过**

```bash
python3 -m pytest tests/test_pipeline_daemon.py -v -k "machine_pool"
```
Expected: 3 passed

**Step 5: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py tests/test_pipeline_daemon.py
git commit -m "feat(v2): GPU 机器池调度器，per-machine Lock 串行化"
```

---

### Task 4: 部署 API 客户端（串行化 load/unload）

**Files:**
- Modify: `scripts/pipline_run/pipeline_daemon.py`
- Modify: `tests/test_pipeline_daemon.py`

**Step 1: 写失败测试**

```python
def test_load_model_success(daemon):
    """load_model 成功返回 config"""
    from unittest.mock import patch, MagicMock
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "code": 200,
        "config": {
            "model_id": "abc123",
            "model_name": "pt14_sft0",
            "url": "http://188.109.35.159:10051/v1/chat/completions",
        },
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        result = daemon.load_model("http://188.109.35.159:8090",
                                   "/dpc/exp/v260306/pt14_sft0/sft",
                                   timeout=600)
    assert result["model_id"] == "abc123"


def test_load_model_no_npu_raises(daemon):
    """无空闲 NPU 时抛 DeployError"""
    from unittest.mock import patch, MagicMock
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 10000, "message": "无空闲npu"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        with pytest.raises(daemon.DeployError, match="无空闲npu"):
            daemon.load_model("http://188.109.35.159:8090",
                              "/dpc/exp/v260306/pt14_sft0/sft")


def test_unload_model_success(daemon):
    """unload 成功不抛异常"""
    from unittest.mock import patch, MagicMock
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 200, "message": "已卸载"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        daemon.unload_model("http://188.109.35.159:8090", "abc123")


def test_parse_serving_url(daemon):
    """解析推理服务 URL"""
    ip, port = daemon.parse_serving_url("http://188.109.35.159:10051/v1/chat/completions")
    assert ip == "188.109.35.159"
    assert port == "10051"
```

**Step 2: 运行确认失败**

**Step 3: 实现 API 客户端**

```python
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
```

**Step 4: 运行测试确认通过**

```bash
python3 -m pytest tests/test_pipeline_daemon.py -v -k "load_model or unload_model or parse_serving"
```
Expected: 4 passed

**Step 5: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py tests/test_pipeline_daemon.py
git commit -m "feat(v2): 部署 API 客户端，超时 10 分钟"
```

---

### Task 5: Docker 命令构造与 fmt 归集

**Files:**
- Modify: `scripts/pipline_run/pipeline_daemon.py`
- Modify: `tests/test_pipeline_daemon.py`

**Step 1: 写失败测试**

```python
def test_build_docker_cmd(tmp_path, daemon):
    """docker 命令包含正确的挂载和参数"""
    cfg = daemon.get_default_config()
    cmd = daemon.build_docker_cmd(
        exp_name="pt14_sft0",
        task_id="eval_pt14_sft0",
        output_dir=tmp_path / "pt14_sft0" / "outputs",
        host_ip="188.109.35.159",
        host_port="10051",
        workspace=Path("/opt/eval_workspace"),
        config=cfg,
    )
    cmd_str = " ".join(str(c) for c in cmd)
    assert "eval_pt14_sft0" in cmd_str
    assert "LOCAL_HOST_PORT=10051" in cmd_str
    assert "LOCAL_HOST_IP=188.109.35.159" in cmd_str
    assert "/app/data:ro" in cmd_str or "/app/data" in cmd_str
    assert "benchmark-eval:latest" in cmd_str


def test_collect_to_fmt(tmp_path, daemon):
    """评测完成后正确归集到 fmt 目录"""
    # 模拟评测产出
    task_dir = tmp_path / "pt14_sft0" / "outputs" / "eval_pt14_sft0"
    task_dir.mkdir(parents=True)
    (task_dir / "report.json").write_text('{"avg_accuracy": 80.0}')
    (task_dir / "report.md").write_text("# Report")
    details = task_dir / "details" / "20260312_120000"
    details.mkdir(parents=True)
    (details / "summary").mkdir()
    (details / "summary" / "summary.csv").write_text("data")

    fmt_dir = tmp_path / "fmt"
    daemon.collect_to_fmt(
        exp_name="pt14_sft0",
        task_id="eval_pt14_sft0",
        output_dir=tmp_path / "pt14_sft0" / "outputs",
        fmt_dir=fmt_dir,
    )

    assert (fmt_dir / "pt14_sft0" / "report.json").exists()
    assert (fmt_dir / "pt14_sft0" / "report.md").exists()
    assert (fmt_dir / "pt14_sft0" / "details" / "20260312_120000" / "summary" / "summary.csv").exists()
```

**Step 2: 运行确认失败**

**Step 3: 实现**

```python
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
```

**Step 4: 运行测试确认通过**

```bash
python3 -m pytest tests/test_pipeline_daemon.py -v -k "docker_cmd or collect_to_fmt"
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py tests/test_pipeline_daemon.py
git commit -m "feat(v2): Docker 命令构造（data 只读共享）与 fmt 归集"
```

---

### Task 6: Worker 线程（完整 load → eval → unload → collect 生命周期）

**Files:**
- Modify: `scripts/pipline_run/pipeline_daemon.py`
- Modify: `tests/test_pipeline_daemon.py`

**Step 1: 写失败测试**

```python
def test_eval_worker_success(tmp_path, daemon):
    """完整流程：allocate → lock → load → docker run → unload → release → collect"""
    from unittest.mock import patch, MagicMock
    import argparse

    # 准备 report.json
    task_id = "eval_pt14_sft0"
    report_dir = tmp_path / "pt14_sft0" / "outputs" / task_id
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(json.dumps({"avg_accuracy": 80.0}))
    (report_dir / "report.md").write_text("# Test")

    cfg = daemon.get_default_config()
    cfg["work_dir"] = str(tmp_path)
    cfg["workspace"] = str(tmp_path)
    cfg["eval_timeout"] = 60
    cfg["dry_run"] = False

    machines = [{"ip": "10.0.0.1", "port": 8090, "slots": 8}]
    pool = daemon.MachinePool(machines)

    mock_config = {
        "model_id": "abc123",
        "model_name": "pt14_sft0",
        "url": "http://10.0.0.1:10051/v1/chat/completions",
    }

    with patch.object(daemon, 'load_model', return_value=mock_config), \
         patch.object(daemon, 'unload_model') as mock_unload, \
         patch('subprocess.run', return_value=MagicMock(returncode=0)):
        result = daemon.eval_worker("pt14_sft0", cfg, pool)

    assert result["status"] == "done"
    assert result["avg_accuracy"] == 80.0
    assert result["machine_ip"] == "10.0.0.1"
    mock_unload.assert_called_once()
    # 确认槽位已释放
    assert pool.status()["10.0.0.1"]["used"] == 0


def test_eval_worker_dry_run(tmp_path, daemon):
    """dry-run 不调用 API 也不启动容器"""
    cfg = daemon.get_default_config()
    cfg["work_dir"] = str(tmp_path)
    cfg["workspace"] = str(tmp_path)
    cfg["dry_run"] = True

    machines = [{"ip": "10.0.0.1", "port": 8090, "slots": 8}]
    pool = daemon.MachinePool(machines)

    result = daemon.eval_worker("pt14_sft0", cfg, pool)
    assert result["status"] == "done"
    assert result["model_id"] == "dry-run"
```

**Step 2: 运行确认失败**

**Step 3: 实现 eval_worker**

```python
def read_report_accuracy(report_path: Path) -> Optional[float]:
    """读取 report.json，返回 avg_accuracy。"""
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        return data.get("avg_accuracy")
    except Exception:
        return None


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
```

**Step 4: 运行测试确认通过**

```bash
python3 -m pytest tests/test_pipeline_daemon.py -v -k "eval_worker"
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py tests/test_pipeline_daemon.py
git commit -m "feat(v2): eval_worker 完整生命周期（串行 load/unload + fmt 归集）"
```

---

### Task 7: 批量报告与崩溃恢复

**Files:**
- Modify: `scripts/pipline_run/pipeline_daemon.py`
- Modify: `tests/test_pipeline_daemon.py`

**Step 1: 写失败测试**

```python
def test_generate_batch_report(tmp_path, daemon):
    """生成 batch_report.md"""
    state = {
        "last_scan": "2026-03-12T10:00:00",
        "stats": {"total": 2, "done": 1, "failed": 1, "evaluating": 0, "queued": 0},
        "models": {
            "pt14_sft0": {"status": "done", "avg_accuracy": 80.0,
                          "machine_ip": "188.109.35.159",
                          "eval_start": "2026-03-12T08:00:00",
                          "eval_end": "2026-03-12T09:00:00"},
            "pt15_sft0": {"status": "failed", "error": "timeout"},
        },
    }
    path = tmp_path / "batch_report.md"
    daemon.generate_batch_report(state, path)
    content = path.read_text()
    assert "pt14_sft0" in content
    assert "80.0" in content or "80.00" in content
    assert "pt15_sft0" in content


def test_recover_evaluating_state(daemon):
    """崩溃恢复：evaluating → queued"""
    state = {
        "models": {
            "pt14_sft0": {"status": "evaluating", "model_id": "abc"},
            "pt15_sft0": {"status": "done"},
        }
    }
    daemon.recover_evaluating_state(state, logging.getLogger())
    assert state["models"]["pt14_sft0"]["status"] == "queued"
    assert state["models"]["pt15_sft0"]["status"] == "done"
```

**Step 2: 运行确认失败**

**Step 3: 实现**

```python
def generate_batch_report(state: dict, report_path: Path) -> None:
    """生成 batch_report.md 横向对比报告。"""
    stats = state.get("stats", _compute_stats(state))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# 批量评测对比报告",
        "",
        f"**更新时间**: {now}",
        f"**进度**: {stats.get('done',0)}/{stats.get('total',0)} 完成 | "
        f"{stats.get('evaluating',0)} 评测中 | {stats.get('queued',0)} 排队 | "
        f"{stats.get('failed',0)} 失败",
        "",
    ]

    # 已完成
    done_models = {n: m for n, m in state["models"].items() if m.get("status") == "done"}
    if done_models:
        lines += [
            "## 已完成模型对比", "",
            "| 模型 | 平均准确率 | 机器 | 耗时(min) |",
            "|------|-----------|------|----------|",
        ]
        sorted_models = sorted(done_models.items(),
                                key=lambda kv: kv[1].get("avg_accuracy") or 0, reverse=True)
        for name, info in sorted_models:
            acc = info.get("avg_accuracy")
            acc_str = f"{acc:.2f}%" if acc is not None else "-"
            ip = info.get("machine_ip", "-")
            try:
                s = datetime.fromisoformat(info["eval_start"])
                e = datetime.fromisoformat(info["eval_end"])
                dur = round((e - s).total_seconds() / 60, 1)
            except Exception:
                dur = "-"
            lines.append(f"| {name} | {acc_str} | {ip} | {dur} |")
        lines.append("")

    # 评测中
    running = {n: m for n, m in state["models"].items() if m.get("status") == "evaluating"}
    if running:
        lines += ["## 当前进行中", "",
                  "| 模型 | 机器 | 开始时间 |", "|------|------|---------|"]
        for name, info in running.items():
            lines.append(f"| {name} | {info.get('machine_ip','-')} | {info.get('eval_start','-')} |")
        lines.append("")

    # 失败
    failed = {n: m for n, m in state["models"].items() if m.get("status") == "failed"}
    if failed:
        lines += ["## 失败列表", "", "| 模型 | 原因 |", "|------|------|"]
        for name, info in failed.items():
            lines.append(f"| {name} | {info.get('error','未知')} |")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def recover_evaluating_state(state: dict, logger: logging.Logger) -> None:
    """崩溃恢复：evaluating → queued。"""
    for name, info in state["models"].items():
        if info.get("status") == "evaluating":
            info["status"] = "queued"
            for key in ("model_id", "serving_url", "eval_start", "machine_ip"):
                info.pop(key, None)
            logger.warning(f"[恢复] {name}: evaluating → queued")
```

**Step 4: 运行测试确认通过**

```bash
python3 -m pytest tests/test_pipeline_daemon.py -v -k "batch_report or recover"
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py tests/test_pipeline_daemon.py
git commit -m "feat(v2): 批量报告生成与崩溃恢复"
```

---

### Task 8: 主轮询循环与 CLI 入口

**Files:**
- Modify: `scripts/pipline_run/pipeline_daemon.py`

这部分涉及无限循环和 ThreadPoolExecutor，不写单元测试，在 Task 9 进行冒烟验证。

**Step 1: 实现主循环与 CLI**

```python
def run_daemon(config: dict) -> None:
    """主守护进程入口。"""
    work_dir = Path(config["work_dir"])
    state_file = work_dir / "pipeline_state.json"
    report_file = work_dir / "batch_report.md"
    pid_file = work_dir / "pipeline_daemon.pid"

    work_dir.mkdir(parents=True, exist_ok=True)

    # PID 文件
    pid_file.write_text(str(os.getpid()))

    # 日志
    log_file = work_dir / "pipeline_daemon.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger(__name__)
    state_lock = threading.Lock()

    logger.info("=" * 60)
    logger.info("Pipeline Daemon v2 启动")
    logger.info(f"  GPU 机器数: {len(config['gpu_machines'])} 台, 总槽位: {sum(m['slots'] for m in config['gpu_machines'])}")
    logger.info(f"  实验组数: {len(config['experiment_groups'])} 组")
    logger.info(f"  工作目录: {work_dir}")
    logger.info(f"  工作区:   {config['workspace']}")
    logger.info(f"  dry-run:  {config.get('dry_run', False)}")
    logger.info("=" * 60)

    # 初始化机器池
    pool = MachinePool(config["gpu_machines"])

    # 加载状态（断点续跑）
    state = load_state(state_file)
    recover_evaluating_state(state, logger)

    # 将实验组列表注入 state（只添加不在 state 中的新组）
    for exp_name in config["experiment_groups"]:
        if exp_name not in state["models"]:
            state["models"][exp_name] = {
                "status": "queued",
                "model_path": f"{config['models_dir']}/{exp_name}/{config['model_subpath']}",
                "added_at": datetime.now().isoformat(timespec="seconds"),
            }
            logger.info(f"加入调度队列: {exp_name}")
        elif state["models"][exp_name].get("status") == "done":
            logger.info(f"跳过已完成: {exp_name}")

    save_state(state, state_file, state_lock)

    running_futures: Dict[str, Future] = {}

    with ThreadPoolExecutor(max_workers=config["max_workers"]) as executor:
        while True:
            # Step 1: 回收已完成 worker
            for exp_name in list(running_futures.keys()):
                fut = running_futures[exp_name]
                if fut.done():
                    result = fut.result()
                    now_str = datetime.now().isoformat(timespec="seconds")
                    state["models"][exp_name].update({
                        "status": result["status"],
                        "eval_end": now_str,
                        "avg_accuracy": result.get("avg_accuracy"),
                        "machine_ip": result.get("machine_ip"),
                        "model_id": result.get("model_id"),
                        "report_path": result.get("report_path"),
                        "error": result.get("error"),
                    })
                    icon = "✅" if result["status"] == "done" else "❌"
                    acc = result.get("avg_accuracy")
                    acc_str = f"{acc:.2f}%" if acc is not None else "N/A"
                    logger.info(f"{icon} [{exp_name}] {result['status'].upper()} | 准确率: {acc_str} | 机器: {result.get('machine_ip', '-')}")
                    del running_futures[exp_name]

            # Step 2: 派发新任务
            queued = [n for n, m in state["models"].items() if m.get("status") == "queued"]
            for exp_name in queued:
                if pool.allocate() is None:
                    break  # 注意：这里先 peek 不 allocate，worker 内部 allocate
                else:
                    # 刚才 allocate 成功了但 worker 内部会再 allocate，所以这里要 release
                    # 更好的做法：直接在这里检查是否有空闲，不做 allocate
                    pass

            # 重新实现：检查空闲槽位数，按数量派发
            pool_status = pool.status()
            free_total = sum(s["total"] - s["used"] for s in pool_status.values())
            dispatched = 0
            for exp_name in queued:
                if dispatched >= free_total:
                    break
                state["models"][exp_name]["status"] = "evaluating"
                state["models"][exp_name]["eval_start"] = datetime.now().isoformat(timespec="seconds")
                fut = executor.submit(eval_worker, exp_name, config, pool)
                running_futures[exp_name] = fut
                dispatched += 1
                logger.info(f"▶ 派发: {exp_name} (剩余空闲: {free_total - dispatched})")

            # Step 3: 更新状态和报告
            save_state(state, state_file, state_lock)
            generate_batch_report(state, report_file)

            stats = state["stats"]
            logger.info(
                f"📊 完成:{stats.get('done',0)} 评测中:{stats.get('evaluating',0)} "
                f"排队:{stats.get('queued',0)} 失败:{stats.get('failed',0)} 总计:{stats.get('total',0)}"
            )

            # 打印机器池状态
            for ip, s in pool.status().items():
                logger.info(f"   GPU {ip}: {s['used']}/{s['total']} 使用中")

            # Step 4: 退出条件
            total = stats.get("total", 0)
            terminal = stats.get("done", 0) + stats.get("failed", 0)
            if total > 0 and terminal >= total and not running_futures:
                logger.info("🏁 所有实验组评测完成！")
                logger.info(f"   报告: {report_file}")
                logger.info(f"   fmt 目录: {work_dir / 'fmt'}")
                break

            # Step 5: 等待下次轮询
            logger.info(f"⏳ 等待 {config['poll_interval']} 秒...")
            time.sleep(config["poll_interval"])

    pid_file.unlink(missing_ok=True)
    logger.info("守护进程正常退出。")


def parse_args() -> dict:
    """解析命令行参数，合并到默认配置中返回。"""
    parser = argparse.ArgumentParser(description="Pipeline Daemon v2 - 多机 GPU 池化评测流水线")
    parser.add_argument("--work-dir", default=None, help="工作目录（状态/输出/fmt）")
    parser.add_argument("--workspace", default=None, help="Docker 工作区（.env/data/code）")
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--poll-interval", type=int, default=None)
    parser.add_argument("--eval-timeout", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = get_default_config()
    if args.work_dir:
        config["work_dir"] = args.work_dir
    if args.workspace:
        config["workspace"] = args.workspace
    if args.max_workers is not None:
        config["max_workers"] = args.max_workers
    if args.poll_interval is not None:
        config["poll_interval"] = args.poll_interval
    if args.eval_timeout is not None:
        config["eval_timeout"] = args.eval_timeout
    config["dry_run"] = args.dry_run
    return config


if __name__ == "__main__":
    config = parse_args()
    run_daemon(config)
```

**Step 2: 运行全量测试（确保无回归）**

```bash
python3 -m pytest tests/test_pipeline_daemon.py -v
```
Expected: 所有已有测试通过

**Step 3: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py
git commit -m "feat(v2): 主轮询循环、CLI 入口、显式实验组调度"
```

---

### Task 9: 管理容器 Dockerfile

**Files:**
- Create: `Dockerfile.manager`

**Step 1: 实现 Dockerfile**

```dockerfile
# Dockerfile.manager - 流水线管理容器
# 轻量镜像：Python + requests + Docker CLI
# 用途：运行 pipeline_daemon.py，通过挂载 Docker Socket 管理评测容器

FROM python:3.10-slim

# 安装 Docker CLI（仅客户端，不需要 daemon）
RUN apt-get update \
    && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
RUN pip install --no-cache-dir requests

# 复制守护进程脚本
COPY scripts/pipline_run/pipeline_daemon.py /app/pipeline_daemon.py

WORKDIR /app

ENTRYPOINT ["python3", "pipeline_daemon.py"]
CMD ["--help"]
```

**Step 2: 验证 Dockerfile 语法**

```bash
docker build -f Dockerfile.manager -t pipeline-manager:latest --dry-run . 2>&1 || \
docker build -f Dockerfile.manager -t pipeline-manager:latest . 2>&1 | head -5
```

**Step 3: Commit**

```bash
git add Dockerfile.manager
git commit -m "feat(v2): 管理容器 Dockerfile（Python + Docker CLI）"
```

---

### Task 10: 冒烟测试（dry-run 验证端到端流程）

**Step 1: 准备模拟环境**

```bash
# 创建模拟目录结构
mkdir -p /tmp/test_v2_workspace/data
mkdir -p /tmp/test_v2_workspace/code/scripts
touch /tmp/test_v2_workspace/.env
touch /tmp/test_v2_workspace/code/eval_entry.py
mkdir -p /tmp/test_v2_workdir
```

**Step 2: 运行 dry-run**

```bash
python3 scripts/pipline_run/pipeline_daemon.py \
    --work-dir /tmp/test_v2_workdir \
    --workspace /tmp/test_v2_workspace \
    --max-workers 4 \
    --poll-interval 1 \
    --dry-run
```

预期输出（几秒内退出）：
```
Pipeline Daemon v2 启动
  GPU 机器数: 6 台, 总槽位: 48
  实验组数: 6 组
加入调度队列: pt14_sft0
加入调度队列: pt15_sft0
...
▶ 派发: pt14_sft0
▶ 派发: pt15_sft0
...
✅ [pt14_sft0] DONE | 准确率: N/A
✅ [pt15_sft0] DONE | 准确率: N/A
...
🏁 所有实验组评测完成！
```

**Step 3: 验证产出文件**

```bash
# state 文件
cat /tmp/test_v2_workdir/pipeline_state.json | python3 -m json.tool | head -20

# batch report
cat /tmp/test_v2_workdir/batch_report.md

# 确认目录结构
ls -la /tmp/test_v2_workdir/pt14_sft0/
# 应有 outputs/ 和 logs/
```

**Step 4: 验证断点续跑（重新运行不重复已完成的组）**

```bash
python3 scripts/pipline_run/pipeline_daemon.py \
    --work-dir /tmp/test_v2_workdir \
    --workspace /tmp/test_v2_workspace \
    --poll-interval 1 \
    --dry-run

# 预期：所有组状态为 done，直接打印"跳过已完成"后退出
```

**Step 5: 清理**

```bash
rm -rf /tmp/test_v2_workdir /tmp/test_v2_workspace
```

**Step 6: 运行全量测试**

```bash
python3 -m pytest tests/test_pipeline_daemon.py -v
```

**Step 7: Commit**

```bash
git add scripts/pipline_run/pipeline_daemon.py tests/test_pipeline_daemon.py
git commit -m "feat(v2): Pipeline Daemon v2 完整实现"
```

---

### Task 11: 更新文档

**Files:**
- Modify: `scripts/pipline_run/eval-pipeline-design.md`
- Modify: `scripts/pipline_run/pipeline-daemon.md`

**Step 1: 更新设计文档**

在 `eval-pipeline-design.md` 头部追加 v2 变更摘要，将关键配置和使用方式更新为 v2 的内容。

**Step 2: 更新操作手册**

更新 `pipeline-daemon.md` 中的启动命令、机器池配置说明、实验组列表说明。

包含管理容器的启动命令：

```bash
# 构建管理容器
docker build -f Dockerfile.manager -t pipeline-manager:latest .

# 启动管理容器
docker run -d --name pipeline-manager \
    --restart unless-stopped \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /dpc/exp:/dpc/exp \
    -v /opt/eval_workspace:/opt/eval_workspace \
    -v $(pwd)/workdir:/app/workdir \
    pipeline-manager:latest \
    --work-dir /app/workdir \
    --workspace /opt/eval_workspace \
    --max-workers 48

# 查看日志
docker logs -f pipeline-manager

# 查看状态
cat workdir/pipeline_state.json | python3 -m json.tool

# 查看对比报告
cat workdir/batch_report.md

# 停止
docker stop pipeline-manager
```

**Step 3: Commit**

```bash
git add scripts/pipline_run/eval-pipeline-design.md scripts/pipline_run/pipeline-daemon.md
git commit -m "docs(v2): 更新设计文档与操作手册"
```

---

## 验收标准

1. `python3 -m pytest tests/test_pipeline_daemon.py -v` → 全部通过
2. `--dry-run` 模式能正确调度全部实验组并退出
3. 断点续跑：重启后已 `done` 的不重复评测
4. 每台机器的 load/unload 串行化（不会并发冲突）
5. 评测完成后结果自动归集到 `fmt/<exp_name>/`
6. `Dockerfile.manager` 能正常构建
7. 管理容器通过 Docker Socket 能启动评测容器

## 使用指南（快速参考）

```bash
# 1. 修改实验组列表（编辑 pipeline_daemon.py 头部的 get_default_config）
#    只需修改 experiment_groups 列表

# 2. 构建管理容器
docker build -f Dockerfile.manager -t pipeline-manager:latest .

# 3. 启动（在任意共享存储机器上）
docker run -d --name pipeline-manager \
    --restart unless-stopped \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /dpc/exp:/dpc/exp \
    -v /opt/eval_workspace:/opt/eval_workspace \
    -v $(pwd)/workdir:/app/workdir \
    pipeline-manager:latest \
    --work-dir /app/workdir \
    --max-workers 48

# 4. 监控
docker logs -f pipeline-manager
cat workdir/batch_report.md

# 5. 迁移到其他机器
docker stop pipeline-manager  # 在旧机器
# 在新机器上执行同样的 docker run 命令（state 在共享存储，自动续跑）

# 6. 查看 fmt 汇总结果
ls workdir/fmt/
```
