# tests/test_pipeline_daemon.py
import json
import threading
from pathlib import Path


def test_load_state_creates_default_when_missing(tmp_path):
    """state 文件不存在时返回空默认值"""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "pipeline_daemon",
        Path(__file__).parent.parent / "scripts/pipeline_daemon.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pipeline_daemon"] = mod
    spec.loader.exec_module(mod)

    state_file = tmp_path / "pipeline_state.json"
    state = mod.load_state(state_file)
    assert state["models"] == {}
    assert "last_scan" in state


def test_save_and_reload_state(tmp_path):
    """保存后重新加载内容一致"""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "pipeline_daemon",
        Path(__file__).parent.parent / "scripts/pipeline_daemon.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pipeline_daemon"] = mod
    spec.loader.exec_module(mod)

    lock = threading.Lock()
    state_file = tmp_path / "pipeline_state.json"

    state = mod.load_state(state_file)
    state["models"]["exp_001"] = {"status": "queued"}
    mod.save_state(state, state_file, lock)

    reloaded = mod.load_state(state_file)
    assert reloaded["models"]["exp_001"]["status"] == "queued"
