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

    # 把两台都占满
    pool.allocate()
    pool.allocate()
    pool.allocate()

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
