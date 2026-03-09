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


def test_scan_done_experiments(tmp_path, daemon_mod):
    """只返回有 .done 且有 sft/ 子目录的实验名"""
    # 实验 A：训练完成（有 .done 且有 sft/）
    exp_a = tmp_path / "pt0_sft0"
    (exp_a / "sft").mkdir(parents=True)
    (exp_a / ".done").touch()

    # 实验 B：训练未完成（有 sft/ 但无 .done）
    exp_b = tmp_path / "pt0_sft1"
    (exp_b / "sft").mkdir(parents=True)

    # 实验 C：有 .done 但无 sft/（训练产物不完整，跳过）
    exp_c = tmp_path / "pt0_sft2"
    exp_c.mkdir()
    (exp_c / ".done").touch()

    found = daemon_mod.scan_done_experiments(tmp_path)
    assert found == {"pt0_sft0"}


def test_parse_serving_url(daemon_mod):
    """解析返回 URL 为 (host_ip, host_port)"""
    ip, port = daemon_mod.parse_serving_url("http://188.109.35.159:10051/v1/chat/completions")
    assert ip == "188.109.35.159"
    assert port == "10051"


def test_scan_done_experiments_nonexistent_dir(daemon_mod, tmp_path):
    """models_dir 不存在时返回空 set"""
    found = daemon_mod.scan_done_experiments(tmp_path / "nonexistent")
    assert found == set()


def test_scan_done_experiments_ignores_files(tmp_path, daemon_mod):
    """普通文件被跳过（只处理目录）"""
    # 放一个普通文件
    (tmp_path / "some_file.log").write_text("content")
    # 放一个真正完成的实验
    exp = tmp_path / "pt0_sft0"
    (exp / "sft").mkdir(parents=True)
    (exp / ".done").touch()

    found = daemon_mod.scan_done_experiments(tmp_path)
    assert found == {"pt0_sft0"}


def test_parse_serving_url_raises_on_missing_port(daemon_mod):
    """URL 没有端口号时应抛出 ValueError"""
    try:
        daemon_mod.parse_serving_url("http://188.109.35.159/v1/chat/completions")
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "端口" in str(e) or "port" in str(e).lower()


def test_build_docker_cmd_contains_key_args(tmp_path, daemon_mod):
    """docker 命令包含隔离输出目录、动态端口、正确的 task-id"""
    from pathlib import Path
    cmd = daemon_mod.build_docker_cmd(
        exp_name="pt0_sft0",
        task_id="eval_pt0_sft0",
        output_dir=tmp_path / "pt0_sft0",
        host_ip="188.109.35.159",
        host_port="10051",
        workspace=Path("/opt/eval_workspace"),
    )

    cmd_str = " ".join(str(c) for c in cmd)
    assert "eval_pt0_sft0" in cmd_str          # task-id 正确
    assert "LOCAL_HOST_PORT=10051" in cmd_str   # 动态端口注入
    assert "LOCAL_HOST_IP=188.109.35.159" in cmd_str
    assert str(tmp_path / "pt0_sft0") in cmd_str  # 独立输出目录挂载
    assert "benchmark-eval:latest" in cmd_str
    assert "--model-config" in cmd_str
    assert "local_qwen" in cmd_str


def test_load_model_returns_config_on_success(daemon_mod):
    from unittest.mock import patch, MagicMock
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "code": 200,
        "message": "模型已启动",
        "config": {
            "model_id": "2378437c",
            "model_name": "pt0_sft0",
            "url": "http://188.109.35.159:10051/v1/chat/completions",
        },
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        result = daemon_mod.load_model("http://188.109.35.159:8080",
                                       "/dpc/exp/v260306/pt0_sft0/sft")

    assert result["model_id"] == "2378437c"
    assert result["url"] == "http://188.109.35.159:10051/v1/chat/completions"


def test_load_model_raises_on_no_npu(daemon_mod):
    from unittest.mock import patch, MagicMock
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 10000, "message": "无空闲npu"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        try:
            daemon_mod.load_model("http://188.109.35.159:8080",
                                  "/dpc/exp/v260306/pt0_sft0/sft")
            assert False, "应该抛出 DeployError"
        except daemon_mod.DeployError as e:
            assert "无空闲npu" in str(e)


def test_unload_model_success(daemon_mod):
    from unittest.mock import patch, MagicMock
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"code": 200, "message": "模型 2378437c 已卸载"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp):
        daemon_mod.unload_model("http://188.109.35.159:8080", "2378437c")
        # 不抛异常即通过
