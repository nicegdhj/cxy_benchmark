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
