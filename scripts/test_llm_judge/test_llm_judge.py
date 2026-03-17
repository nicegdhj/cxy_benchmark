#!/usr/bin/env python3
"""
LLMJudgeEvaluator 本地集成测试
================================
在启动 mock_eval_server.py 之后运行此脚本，验证评估器完整代码路径。

包含三类测试：
  Test 1 - 环境变量缺失时的降级行为（不需要 mock server）
  Test 2 - EVAL_* 环境变量完整时自动构建模型（需要 mock server）
  Test 3 - 显式传入 model_cfg 时走原有路径（需要 mock server）

用法：
    # 先在另一个终端启动 mock server：
    python scripts/test_llm_judge/mock_eval_server.py --port 19999

    # 然后运行本测试：
    python scripts/test_llm_judge/test_llm_judge.py [--port 19999]
"""

import sys
import os
import argparse

# 确保项目包在路径中
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.abspath(PROJECT_ROOT))


# ─── 颜色输出工具 ─────────────────────────────────────────────────────────────

def green(s): return f"\033[92m{s}\033[0m"
def red(s):   return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def bold(s):  return f"\033[1m{s}\033[0m"

PASS = green("  [PASS]")
FAIL = red("  [FAIL]")
SKIP = yellow("  [SKIP]")


def assert_eq(desc, actual, expected):
    if actual == expected:
        print(f"{PASS} {desc}: {actual!r}")
    else:
        print(f"{FAIL} {desc}: expected {expected!r}, got {actual!r}")


def assert_not_none(desc, val):
    if val is not None:
        print(f"{PASS} {desc}: {val!r}")
    else:
        print(f"{FAIL} {desc}: expected non-None but got None")


def assert_none(desc, val):
    if val is None:
        print(f"{PASS} {desc}: value is None as expected")
    else:
        print(f"{FAIL} {desc}: expected None but got {val!r}")


def assert_keys_in(desc, d: dict, keys: list):
    missing = [k for k in keys if k not in d]
    if not missing:
        print(f"{PASS} {desc}: all keys present {keys}")
    else:
        print(f"{FAIL} {desc}: missing keys {missing} in {list(d.keys())}")


# ─── 测试用的最小 Dataset 替身 ────────────────────────────────────────────────

class FakeDataset:
    """模拟 HuggingFace Dataset 的最小接口"""
    def __init__(self, records):
        self._records = records
        self.features = {k: None for k in records[0]} if records else {}

    def __len__(self):
        return len(self._records)

    def __getitem__(self, idx):
        return self._records[idx]


# ─── 测试用例 ─────────────────────────────────────────────────────────────────

def test_env_missing():
    """Test 1: 所有 EVAL_* 均未设置，model 应为 None，evaluate 应返回 error"""
    print(bold("\n─── Test 1: EVAL_* 环境变量全部缺失 ───"))

    # 清空相关变量
    for k in ("EVAL_MODEL_NAME", "EVAL_HOST_IP", "EVAL_HOST_PORT", "EVAL_URL"):
        os.environ.pop(k, None)

    from ais_bench.benchmark.openicl.icl_evaluator.llm_judge_evaluator import LLMJudgeEvaluator
    import importlib
    import ais_bench.benchmark.openicl.icl_evaluator.llm_judge_evaluator as mod
    importlib.reload(mod)
    LLMJudgeEvaluator = mod.LLMJudgeEvaluator

    ev = LLMJudgeEvaluator()
    assert_none("model 应为 None", ev.model)

    # evaluate 应返回 error 字段
    ds = FakeDataset([{"subdivision": "test", "idx": 0}])
    result = ev.evaluate(1, 1, ds, predictions=["答案A"], references=["参考答案"])
    assert_keys_in("结果包含 error 字段", result, ["error"])
    print(f"  error message: {result.get('error')}")


def test_env_partial_missing():
    """Test 2: 只设置部分 EVAL_* 变量，应仍回退为 None"""
    print(bold("\n─── Test 2: EVAL_* 部分缺失（只设 IP，缺 PORT/NAME）───"))

    os.environ["EVAL_HOST_IP"] = "127.0.0.1"
    os.environ.pop("EVAL_HOST_PORT", None)
    os.environ.pop("EVAL_MODEL_NAME", None)

    import importlib
    import ais_bench.benchmark.openicl.icl_evaluator.llm_judge_evaluator as mod
    importlib.reload(mod)
    LLMJudgeEvaluator = mod.LLMJudgeEvaluator

    ev = LLMJudgeEvaluator()
    assert_none("model 应为 None（部分变量缺失）", ev.model)
    os.environ.pop("EVAL_HOST_IP", None)


def test_env_full(port: int):
    """Test 3: EVAL_* 齐全，连接 mock server，验证完整 evaluate 流程"""
    print(bold(f"\n─── Test 3: 完整 EVAL_* 环境变量 → mock server 127.0.0.1:{port} ───"))

    os.environ["EVAL_MODEL_NAME"] = "mock-72b"
    os.environ["EVAL_HOST_IP"]    = "127.0.0.1"
    os.environ["EVAL_HOST_PORT"]  = str(port)
    os.environ.pop("EVAL_URL", None)

    import importlib
    import ais_bench.benchmark.openicl.icl_evaluator.llm_judge_evaluator as mod
    importlib.reload(mod)
    LLMJudgeEvaluator = mod.LLMJudgeEvaluator

    try:
        ev = LLMJudgeEvaluator()
    except Exception as e:
        print(f"{FAIL} 构建评估器失败: {e}")
        return

    assert_not_none("model 实例已创建", ev.model)

    # 构造测试数据集
    ds = FakeDataset([
        {"subdivision": "传输与接入", "idx": 0, "score": "5"},
        {"subdivision": "互联网技术",  "idx": 1, "score": "3"},
    ])
    predictions = ["这是学生答案A", "这是学生答案B"]
    references  = ["标准答案A",     "标准答案B"]

    try:
        result = ev.evaluate(2, 2, ds, predictions=predictions, references=references)
    except Exception as e:
        print(f"{FAIL} evaluate() 抛出异常: {e}")
        import traceback; traceback.print_exc()
        return

    if "error" in result:
        print(f"{FAIL} evaluate() 返回 error: {result['error']}")
        return

    print(f"{PASS} evaluate() 正常返回，keys: {list(result.keys())}")

    details = result.get("details", [])
    assert_eq("details 条数", len(details), 2)

    for i, d in enumerate(details):
        score = d.get("llm_score", -1)
        max_score = d.get("max_score", -1)
        judge_output = d.get("judge_output", "")
        print(f"  [item {i}] score={score}/{max_score}  judge_output={judge_output!r:.60s}")
        if not (0.0 <= score <= max_score):
            print(f"  {FAIL} score {score} 超出范围 [0, {max_score}]")
        else:
            print(f"  {PASS} score 在有效范围内")

    # 检查百分比字段
    pct_keys = [k for k in result if k.endswith("/llm_judge_percentage")]
    assert_not_none("存在百分比汇总字段", pct_keys or None)
    for k in pct_keys:
        print(f"  {k} = {result[k]}%")


def test_explicit_model_cfg(port: int):
    """Test 4: 显式传入 model_cfg（原有路径），验证与隐式路径等效"""
    print(bold(f"\n─── Test 4: 显式 model_cfg → mock server 127.0.0.1:{port} ───"))

    # 清空 EVAL_* 避免干扰
    for k in ("EVAL_MODEL_NAME", "EVAL_HOST_IP", "EVAL_HOST_PORT"):
        os.environ.pop(k, None)

    from ais_bench.benchmark.models import MaaSAPI

    explicit_cfg = dict(
        type=MaaSAPI,
        attr="service",
        abbr="test_judge_model",
        path="",
        model="mock-72b",
        stream=False,
        request_rate=0,
        retry=1,
        host_ip="127.0.0.1",
        host_port=port,
        url=f"http://127.0.0.1:{port}/v1/chat/completions",
        max_out_len=128,
        batch_size=4,
        trust_remote_code=False,
        verbose=False,
        generation_kwargs=dict(temperature=0.01, ignore_eos=False),
    )

    import importlib
    import ais_bench.benchmark.openicl.icl_evaluator.llm_judge_evaluator as mod
    importlib.reload(mod)
    LLMJudgeEvaluator = mod.LLMJudgeEvaluator

    try:
        ev = LLMJudgeEvaluator(model_cfg=explicit_cfg)
    except Exception as e:
        print(f"{FAIL} 显式 model_cfg 构建失败: {e}")
        return

    assert_not_none("model 实例已创建（显式路径）", ev.model)

    ds = FakeDataset([{"subdivision": "explicit_test", "idx": 0}])
    result = ev.evaluate(1, 1, ds, predictions=["答案"], references=["参考"])
    if "error" in result:
        print(f"{FAIL} evaluate() 返回 error: {result['error']}")
    else:
        print(f"{PASS} 显式 model_cfg 路径正常，result keys: {list(result.keys())}")


# ─── 入口 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=19999,
                        help="mock_eval_server.py 的监听端口（默认 19999）")
    parser.add_argument("--skip-server-tests", action="store_true",
                        help="跳过需要 mock server 的测试（Test 3/4）")
    args = parser.parse_args()

    print(bold("=" * 60))
    print(bold("  LLMJudgeEvaluator 本地集成测试"))
    print(bold("=" * 60))

    # 无需 mock server 的测试
    test_env_missing()
    test_env_partial_missing()

    # 需要 mock server 的测试
    if args.skip_server_tests:
        print(f"\n{SKIP} Test 3/4 已跳过（--skip-server-tests）")
    else:
        print(f"\n{yellow('提示')}：以下测试需要 mock_eval_server.py 在 127.0.0.1:{args.port} 运行。")
        print(f"       若尚未启动，请在另一终端运行：")
        print(f"       python scripts/test_llm_judge/mock_eval_server.py --port {args.port}\n")
        try:
            test_env_full(args.port)
            test_explicit_model_cfg(args.port)
        except Exception as e:
            print(f"{FAIL} 连接 mock server 失败，请确认其是否已启动: {e}")

    print(bold("\n" + "=" * 60))
    print(bold("  测试完成"))
    print(bold("=" * 60))


if __name__ == "__main__":
    main()
