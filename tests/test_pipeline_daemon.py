# tests/test_pipeline_daemon.py
import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def daemon_mod():
    """加载 pipeline_daemon 模块（绕开非标准包结构）"""
    spec = importlib.util.spec_from_file_location(
        "pipeline_daemon",
        Path(__file__).parent.parent / "scripts/pipeline_daemon.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_load_state_creates_default_when_missing(tmp_path, daemon_mod):
    """state 文件不存在时返回空默认值"""
    state_file = tmp_path / "pipeline_state.json"
    state = daemon_mod.load_state(state_file)
    assert state["models"] == {}
    assert "last_scan" in state


def test_save_and_reload_state(tmp_path, daemon_mod):
    """保存后重新加载内容一致"""
    lock = threading.Lock()
    state_file = tmp_path / "pipeline_state.json"

    state = daemon_mod.load_state(state_file)
    state["models"]["exp_001"] = {"status": "queued"}
    daemon_mod.save_state(state, state_file, lock)

    reloaded = daemon_mod.load_state(state_file)
    assert reloaded["models"]["exp_001"]["status"] == "queued"
