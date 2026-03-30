# 推理与评测分离 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 eval_entry.py 拆分为推理（eval_entry.py）和评测（eval_judge.py）两个独立脚本，支持推理结果复用和评测版本化管理。

**Architecture:** eval_entry.py 只调用 `ais_bench --mode infer` 并生成 infer_meta.json；eval_judge.py 读取 infer_meta.json，通过 `ais_bench --mode eval --work-dir ... --reuse {timestamp}` 复用推理结果，评测产出存入版本化目录 `eval_{version}/`。

**Tech Stack:** Python 3, ais_bench CLI, Docker, Bash

**设计文档:** `docs/specs/2026-03-17-infer-eval-separation-design.md`

---

## 文件结构

| 文件 | 操作 | 职责 |
|:---|:---|:---|
| `eval_entry.py` | 修改 | 去掉评测逻辑，只做推理 + 生成 infer_meta.json |
| `eval_judge.py` | 新增 | 评测专用脚本：读取推理结果、分类排序、调用 eval、生成报告 |
| `run_mixed_benchmark.sh` | 修改 | 两阶段串联（推理 → 评测） |
| `scripts/package_deploy.sh` | 修改 | 打包时包含 eval_judge.py |
| `tests/test_eval_judge.py` | 新增 | eval_judge.py 的核心逻辑单元测试 |

---

## 关键技术细节（供实施参考）

### ais_bench 的 --work-dir 和 --reuse 机制

```python
# config_manager.py 中的 work_dir 解析逻辑：
# 1. base_work_dir = --work-dir 参数值 或 'outputs/default'
# 2. dir_time_str = --reuse 参数值 或 当前时间戳
# 3. 最终 work_dir = base_work_dir / dir_time_str
```

所以 eval_judge.py 调用 eval 时：
```bash
# 推理结果在：outputs/{task_id}/details/{timestamp}/predictions/
# 调用方式：
ais_bench --mode eval \
    --work-dir "outputs/{task_id}/details" \
    --reuse {timestamp} \
    --models {model_config} \
    --datasets {suite}
# → work_dir = outputs/{task_id}/details/{timestamp}/
# → 读取 predictions/ ✓
# → 写入 results/、logs/eval/、summary/ 到同一目录
```

eval 完成后，需要将 results/、logs/eval/、summary/ 从 `details/{timestamp}/` 搬运到 `eval_{version}/`，然后从 details 中删除这些目录。

### 内存控制机制（必须保留）

eval_entry.py 中的 `_cleanup_leaked_shm()` 和 `gc.collect()` 必须在两个脚本中都保留，eval_judge.py 需要复用此逻辑。

### LLM 评估器检测

当前使用 LLMJudgeEvaluator 的 3 个任务：
- `telequad_gen_0_shot` → `TeleQuAD/telequad_gen_0_shot.py`
- `tele_exam_gen_0_shot_str` → `tele_exam/tele_exam_gen_0_shot_str.py`
- `teledata_gen_0_shot` → `Tele-Data/teledata_gen_0_shot.py`

检测方法：扫描 `ais_bench/benchmark/configs/datasets/` 下匹配 suite 名的 .py 文件，检查是否包含 `LLMJudgeEvaluator` 字符串。

---

## Task 1: eval_entry.py — 改为仅推理 + 生成 infer_meta.json

**Files:**
- Modify: `eval_entry.py`

### 核心改动点

1. `run_evaluation()` 中 ais_bench 命令加上 `--mode infer`
2. 去掉 `_parse_latest_task_result()` 中的 results/summary 解析（infer 模式不产出这些）
3. 去掉 `generate_report()` 调用
4. 新增 `generate_infer_meta()` 生成 infer_meta.json
5. 搬运产物时只搬 predictions/ + configs/ + logs/infer/（不再有 results/summary）
6. 保留 `_cleanup_leaked_shm()` 和 `gc.collect()`

- [ ] **Step 1: 修改 run_evaluation() 中的 ais_bench 调用命令**

在构造 cmd 时，始终加上 `"--mode", "infer"`：

```python
# debug 模式
cmd = [
    "ais_bench",
    "--mode", "infer",
    "--models", model_config,
    "--datasets", suite,
    "--debug",
]

# 生产模式
cmd = [
    "ais_bench",
    "--mode", "infer",
    "--models", model_config,
    "--datasets", suite,
    "--max-num-workers", str(concurrency),
]
```

- [ ] **Step 2: 简化结果解析逻辑**

`--mode infer` 不产出 summary 和 results，因此 `_parse_latest_task_result()` 需要简化。只需要：
- 找到本次产出的 ais_bench 时间戳目录名
- 从 predictions/ 统计样本数

将 `_parse_latest_task_result()` 替换为更简单的 `_find_infer_output()`：

```python
def _find_infer_output(
    ais_bench_output: Path, suite_name_pattern: str, run_start_time: float = None
) -> tuple:
    """查找本次推理产出的时间戳目录和样本数。

    Returns:
        (dir_name: str | None, num_samples: int | None)
    """
    try:
        # infer 模式下没有 summary，直接查找最新的含 predictions 的目录
        candidates = []
        for d in ais_bench_output.iterdir():
            if not d.is_dir():
                continue
            pred_dir = d / "predictions"
            if not pred_dir.exists():
                continue
            # 时间过滤
            if run_start_time is not None and d.stat().st_mtime <= (run_start_time - 300):
                continue
            # config 匹配
            for cfg in d.glob("configs/*.py"):
                try:
                    cfg_text = cfg.read_text(encoding="utf-8")
                    if f"'{suite_name_pattern}'" in cfg_text or f'"{suite_name_pattern}"' in cfg_text:
                        candidates.append(d)
                        break
                except Exception:
                    pass

        if not candidates:
            return None, None

        # 取最新的
        target = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        dir_name = target.name

        # 统计样本数
        num_samples = None
        jsonl_files = list((target / "predictions").glob("**/*.jsonl"))
        if jsonl_files:
            try:
                num_samples = sum(
                    sum(1 for _ in open(f, "r", encoding="utf-8"))
                    for f in jsonl_files
                )
            except Exception:
                pass

        return dir_name, num_samples
    except Exception:
        return None, None
```

- [ ] **Step 3: 修改 run_evaluation() 中的结果收集和搬运逻辑**

```python
# 替换原来的 accuracy 解析调用
ais_bench_dir, num_samples = _find_infer_output(
    ais_bench_output, suite_name_pattern=suite, run_start_time=start_time
)
results.append(
    {
        "task_name": task_name,
        "type": task_type,
        "suite": suite,
        "status": "success" if proc.returncode == 0 else "failed",
        "num_samples": num_samples,
        "duration_sec": round(duration, 1),
        "returncode": proc.returncode,
        "timestamp": ais_bench_dir,
    }
)

# 搬运逻辑不变（从 outputs/default/ 移到 outputs/{task_id}/details/）
```

- [ ] **Step 4: 新增 generate_infer_meta() 函数**

```python
def generate_infer_meta(results: list, task_id: str, model_config: str, model_name: str, output_dir: Path):
    """生成 infer_meta.json，记录每个任务的推理时间戳映射。"""
    meta = {
        "task_id": task_id,
        "model_config": model_config,
        "model_name": model_name,
        "infer_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tasks": {}
    }
    for r in results:
        meta["tasks"][r["suite"]] = {
            "timestamp": r["timestamp"],
            "task_name": r["task_name"],
            "type": r["type"],
            "num_samples": r["num_samples"],
            "duration_sec": r["duration_sec"],
            "status": r["status"],
        }

    meta_path = output_dir / task_id / "infer_meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📄 推理元数据已生成: {meta_path}")
```

- [ ] **Step 5: 修改 main() 函数**

去掉 `generate_report()` 调用，改为调用 `generate_infer_meta()`：

```python
def main():
    args = parse_args()

    os.environ["EVAL_MODEL_NAME"] = args.model
    os.environ["EVAL_CONCURRENCY"] = str(args.concurrency)
    os.environ.setdefault("LOCAL_CONCURRENCY", str(args.concurrency))

    data_dir = Path(args.data_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    print("=" * 60)
    print(f"📋 task_id          : {args.task_id}")
    print(f"📋 custom tasks     : {args.tasks}")
    print(f"📋 generic datasets : {args.generic_datasets}")
    print(f"📋 model            : {args.model} (并发 {args.concurrency})")
    print(f"📋 data_dir         : {data_dir}")
    print(f"📋 output_dir       : {output_dir / args.task_id}")
    print("=" * 60)

    validate_data_files(args.tasks, data_dir)
    setup_data_symlink(data_dir)

    results = run_evaluation(
        task_nums=args.tasks,
        generic_datasets=args.generic_datasets,
        output_dir=output_dir,
        task_id=args.task_id,
        model_config=args.model_config,
        concurrency=args.concurrency,
        debug=args.debug,
        num_prompts=args.num_prompts,
    )

    generate_infer_meta(results, args.task_id, args.model_config, args.model, output_dir)

    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 推理完成摘要")
    print("=" * 60)
    for r in results:
        icon = "✅" if r["status"] == "success" else "❌"
        samples = r["num_samples"] if r["num_samples"] else "N/A"
        print(
            f"  {icon} [{r['type'][:3]}] {r['task_name']:15s} 耗时: {r['duration_sec']}s  样本数: {samples}"
        )
    print(f"\n  📁 结果目录: {output_dir / args.task_id}")
    print("=" * 60)

    failed = [r for r in results if r["status"] != "success"]
    sys.exit(1 if failed else 0)
```

- [ ] **Step 6: 清理不再需要的代码**

删除以下函数和相关 import：
- `_parse_latest_task_result()` → 已被 `_find_infer_output()` 替代
- `generate_report()` → 报告生成移至 eval_judge.py

- [ ] **Step 7: 验证 eval_entry.py 修改**

Run: `python eval_entry.py --help` 确认参数无误。

如果有可用的模型服务，可执行小规模验证：
```bash
python eval_entry.py --task-id test_infer --model-config bailian_qwen --tasks 1 --num-prompts 2 --debug
```

验证：
- `outputs/test_infer/infer_meta.json` 存在且内容正确
- `outputs/test_infer/details/{timestamp}/predictions/` 存在
- `outputs/test_infer/details/{timestamp}/configs/` 存在
- `outputs/test_infer/details/{timestamp}/logs/infer/` 存在
- 不存在 `results/`、`summary/`、`report.*`

- [ ] **Step 8: Commit**

```bash
git add eval_entry.py
git commit -m "refactor: eval_entry.py 改为仅推理模式，生成 infer_meta.json"
```

---

## Task 2: eval_judge.py — 新增评测脚本

**Files:**
- Create: `eval_judge.py`

### 整体结构

```
eval_judge.py
├── parse_args()                    # 参数解析
├── detect_evaluator_type()         # 自动检测 LLM/规则型评估器
├── sort_tasks_by_eval_type()       # 规则型优先排序
├── run_eval_for_task()             # 单任务评测（调用 ais_bench + 搬运结果）
├── _cleanup_leaked_shm()           # 内存清理（复用自 eval_entry.py）
├── _parse_eval_result()            # 解析单任务评测结果
├── generate_eval_report()          # 生成 report.md + report.json
└── main()                          # 主流程
```

- [ ] **Step 1: 创建 eval_judge.py 基础框架（参数解析 + main 骨架）**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_judge.py - 评测专用脚本

基于 eval_entry.py 推理阶段产出的 infer_meta.json，
复用推理结果执行评测，支持版本化管理和按需重跑。

用法:
    # 评测所有任务（规则型优先，LLM 型靠后）
    python eval_judge.py --infer-task round_1

    # 只评测指定任务，按传入顺序执行
    python eval_judge.py --infer-task round_1 --eval-tasks telequad_gen_0_shot task_1_suite

    # 指定评测版本号
    python eval_judge.py --infer-task round_1 --eval-version v2_fix_weight
"""

import argparse
import gc
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.resolve()
load_dotenv(ROOT / ".env", override=False)

CONFIGS_DIR = ROOT / "ais_bench" / "benchmark" / "configs" / "datasets"


def parse_args():
    parser = argparse.ArgumentParser(
        description="评测专用脚本：基于已有推理结果执行评测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--infer-task",
        required=True,
        help="推理批次标识，对应 outputs/{infer-task}/infer_meta.json",
    )
    parser.add_argument(
        "--eval-version",
        default=None,
        help="评测版本标识。不传则自动生成 eval_{YYYYMMDD_HHMMSS}",
    )
    parser.add_argument(
        "--eval-tasks",
        nargs="*",
        default=None,
        help="指定要评测的任务（suite 名称），按传入顺序执行。不传则评测所有任务",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "outputs"),
        help="输出根目录（默认 outputs/）",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    infer_task_dir = output_dir / args.infer_task

    # 1. 读取 infer_meta.json
    meta_path = infer_task_dir / "infer_meta.json"
    if not meta_path.exists():
        print(f"❌ 找不到推理元数据: {meta_path}")
        print(f"   请先执行 eval_entry.py --task-id {args.infer_task}")
        sys.exit(1)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    model_config = meta["model_config"]
    model_name = meta["model_name"]

    # 2. 确定评测版本
    eval_version = args.eval_version or f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    eval_dir = infer_task_dir / eval_version
    if eval_dir.exists():
        print(f"❌ 评测版本目录已存在: {eval_dir}")
        print(f"   请指定新的 --eval-version 或删除已有目录")
        sys.exit(1)

    # 3. 确定待评测任务列表
    if args.eval_tasks:
        # 按用户指定顺序，校验是否存在于 infer_meta 中
        task_suites = []
        for suite in args.eval_tasks:
            if suite not in meta["tasks"]:
                print(f"⚠️  任务 {suite} 不在 infer_meta 中，跳过")
            else:
                task_suites.append(suite)
    else:
        # 自动排序：规则型优先，LLM 型靠后
        task_suites = sort_tasks_by_eval_type(list(meta["tasks"].keys()))

    if not task_suites:
        print("❌ 没有可评测的任务")
        sys.exit(1)

    print("=" * 60)
    print(f"📋 infer_task    : {args.infer_task}")
    print(f"📋 eval_version  : {eval_version}")
    print(f"📋 model         : {model_name} ({model_config})")
    print(f"📋 tasks ({len(task_suites)})")
    for s in task_suites:
        eval_type = detect_evaluator_type(s)
        print(f"   - {s} [{eval_type}]")
    print("=" * 60)

    # 4. 逐任务执行评测
    results = []
    for i, suite in enumerate(task_suites, 1):
        task_info = meta["tasks"][suite]
        timestamp = task_info["timestamp"]
        eval_type = detect_evaluator_type(suite)

        print(f"\n[{i}/{len(task_suites)}] 🔍 评测 [{eval_type}]: {suite} (reuse={timestamp})")

        result = run_eval_for_task(
            suite=suite,
            timestamp=timestamp,
            task_info=task_info,
            eval_type=eval_type,
            model_config=model_config,
            infer_task_dir=infer_task_dir,
            eval_dir=eval_dir,
        )
        results.append(result)

    # 5. 生成报告
    generate_eval_report(
        results=results,
        infer_task=args.infer_task,
        eval_version=eval_version,
        model_name=model_name,
        eval_dir=eval_dir,
    )

    # 6. 打印摘要
    print("\n" + "=" * 60)
    print("📊 评测完成摘要")
    print("=" * 60)
    for r in results:
        icon = "✅" if r["status"] == "success" else "❌"
        acc = f"{r['accuracy']:.2f}%" if r["accuracy"] is not None else "N/A"
        print(
            f"  {icon} [{r['eval_type'][:3]}] {r['task']:20s} 耗时: {r['duration_sec']}s  准确率: {acc}"
        )

    accuracies = [r["accuracy"] for r in results if r["accuracy"] is not None]
    if accuracies:
        print(f"\n  🏆 综合平均: {sum(accuracies) / len(accuracies):.2f}%")
    print(f"\n  📁 结果目录: {eval_dir}")
    print("=" * 60)

    failed = [r for r in results if r["status"] != "success"]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 实现 detect_evaluator_type() 和 sort_tasks_by_eval_type()**

```python
def detect_evaluator_type(suite_name: str) -> str:
    """扫描 suite 配置文件，检测 evaluator 是否为 LLMJudgeEvaluator。

    搜索 ais_bench/benchmark/configs/datasets/ 下匹配 {suite_name}.py 的文件。

    Returns:
        'llm' 或 'rule'
    """
    for py_file in CONFIGS_DIR.rglob(f"{suite_name}.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            if "LLMJudgeEvaluator" in content:
                return "llm"
        except Exception:
            pass
    return "rule"


def sort_tasks_by_eval_type(suites: list) -> list:
    """将任务按评估器类型排序：规则型优先，LLM 型靠后。"""
    rule_tasks = []
    llm_tasks = []
    for suite in suites:
        if detect_evaluator_type(suite) == "llm":
            llm_tasks.append(suite)
        else:
            rule_tasks.append(suite)
    return rule_tasks + llm_tasks
```

- [ ] **Step 3: 实现 _cleanup_leaked_shm()（从 eval_entry.py 复用）**

```python
def _cleanup_leaked_shm():
    """清理 /dev/shm 中残留的 Python 共享内存段，防止 OOM。"""
    shm_dir = Path("/dev/shm")
    if not shm_dir.exists():
        return
    cleaned = 0
    for f in shm_dir.iterdir():
        if f.name.startswith(("psm_", "wnsm_")):
            try:
                f.unlink()
                cleaned += 1
            except OSError:
                pass
    if cleaned:
        print(f"   🧹 已清理 {cleaned} 个残留共享内存段")
```

- [ ] **Step 4: 实现 run_eval_for_task()（核心评测逻辑）**

```python
def run_eval_for_task(
    suite: str,
    timestamp: str,
    task_info: dict,
    eval_type: str,
    model_config: str,
    infer_task_dir: Path,
    eval_dir: Path,
) -> dict:
    """对单个任务执行评测，搬运结果到 eval_dir。"""

    # ais_bench --mode eval 使用 --work-dir 和 --reuse 定位推理结果
    # work_dir = infer_task_dir/details, reuse = timestamp
    # → 实际 work_dir = infer_task_dir/details/{timestamp}/
    # → 读取 predictions/ ✓
    # → 写入 results/、logs/eval/、summary/ 到同一目录
    details_base = str(infer_task_dir / "details")

    cmd = [
        "ais_bench",
        "--mode", "eval",
        "--work-dir", details_base,
        "--reuse", timestamp,
        "--models", model_config,
        "--datasets", suite,
    ]

    start_time = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=False,
    )
    duration = time.time() - start_time

    # 解析评测结果
    work_dir = infer_task_dir / "details" / timestamp
    accuracy, num_samples = _parse_eval_result(work_dir, suite)

    # 搬运 results/、logs/eval/、summary/ 到 eval_dir
    _move_eval_outputs(work_dir, eval_dir)

    # 内存清理
    _cleanup_leaked_shm()
    gc.collect()

    return {
        "task": task_info["task_name"],
        "suite": suite,
        "type": task_info["type"],
        "eval_type": eval_type,
        "status": "success" if proc.returncode == 0 else "failed",
        "accuracy": accuracy,
        "num_samples": num_samples or task_info.get("num_samples"),
        "duration_sec": round(duration, 1),
        "returncode": proc.returncode,
    }
```

- [ ] **Step 5: 实现 _parse_eval_result() 和 _move_eval_outputs()**

```python
def _parse_eval_result(work_dir: Path, suite: str) -> tuple:
    """从评测产出中解析准确率和样本数。

    Returns:
        (accuracy: float | None, num_samples: int | None)
    """
    accuracy = None
    num_samples = None

    # 从 summary 解析准确率
    for summary_path in work_dir.glob("summary/summary_*.txt"):
        try:
            text = summary_path.read_text(encoding="utf-8")
            lines = text.splitlines()
            csv_start = -1
            for idx, line in enumerate(lines):
                if line.strip() == "csv format":
                    csv_start = idx
                    break

            if csv_start == -1:
                continue

            total_acc = 0.0
            valid_count = 0
            for i in range(csv_start + 3, len(lines)):
                if lines[i].startswith("$") or not lines[i].strip():
                    break
                parts = lines[i].strip().split(",")
                if len(parts) >= 5:
                    try:
                        total_acc += float(parts[-1])
                        valid_count += 1
                    except (ValueError, TypeError):
                        pass

            if valid_count > 0:
                accuracy = round(total_acc / valid_count, 2)
        except Exception:
            pass

    # 从 results 的 details.jsonl 统计样本数
    details_files = list((work_dir / "results").glob("**/*_details.jsonl"))
    if details_files:
        try:
            num_samples = sum(
                sum(1 for _ in open(f, "r", encoding="utf-8"))
                for f in details_files
            )
        except Exception:
            pass

    return accuracy, num_samples


def _move_eval_outputs(work_dir: Path, eval_dir: Path):
    """将 ais_bench eval 产出（results/、logs/eval/、summary/）从 work_dir 搬运到 eval_dir。"""
    for subdir in ["results", "summary"]:
        src = work_dir / subdir
        if src.exists():
            dest = eval_dir / subdir
            # 合并模式：多任务结果累积到同一 eval_dir
            if dest.exists():
                # 逐文件复制，避免覆盖
                for item in src.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(src)
                        target = dest / rel
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, target)
            else:
                shutil.copytree(src, dest)
            shutil.rmtree(src)

    # logs/eval/ 特殊处理
    eval_log_src = work_dir / "logs" / "eval"
    if eval_log_src.exists():
        eval_log_dest = eval_dir / "logs" / "eval"
        if eval_log_dest.exists():
            for item in eval_log_src.rglob("*"):
                if item.is_file():
                    rel = item.relative_to(eval_log_src)
                    target = eval_log_dest / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
        else:
            shutil.copytree(eval_log_src, eval_log_dest)
        shutil.rmtree(eval_log_src)
        # 如果 logs/ 目录空了，清理掉
        logs_dir = work_dir / "logs"
        if logs_dir.exists() and not any(logs_dir.iterdir()):
            logs_dir.rmdir()
```

- [ ] **Step 6: 实现 generate_eval_report()（报告生成）**

```python
def generate_eval_report(
    results: list,
    infer_task: str,
    eval_version: str,
    model_name: str,
    eval_dir: Path,
):
    """生成 report.md 和 report.json。"""
    eval_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    accuracies = [r["accuracy"] for r in results if r["accuracy"] is not None]
    avg = sum(accuracies) / len(accuracies) if accuracies else 0.0

    # 分类汇总
    summary_stats = {
        "custom": {"count": 0, "total_duration_sec": 0.0, "accuracies": []},
        "generic": {"count": 0, "total_duration_sec": 0.0, "accuracies": []},
    }
    for r in results:
        t = r["type"]
        summary_stats[t]["count"] += 1
        summary_stats[t]["total_duration_sec"] += r["duration_sec"]
        if r["accuracy"] is not None:
            summary_stats[t]["accuracies"].append(r["accuracy"])

    for t in ["custom", "generic"]:
        accs = summary_stats[t].pop("accuracies")
        summary_stats[t]["avg_accuracy"] = (
            round(sum(accs) / len(accs), 2) if accs else 0.0
        )
        summary_stats[t]["total_duration_sec"] = round(
            summary_stats[t]["total_duration_sec"], 1
        )

    # Markdown 报告
    lines = [
        "# 评测报告",
        "",
        f"- **Infer Task**: `{infer_task}`",
        f"- **Eval Version**: `{eval_version}`",
        f"- **模型**: `{model_name}`",
        f"- **时间**: {now}",
        f"- **综合准确率**: {avg:.2f}%",
        "",
        "## 统计摘要",
        "",
        "| 任务类型 | 任务数量 | 总耗时 (秒) | 平均准确率 |",
        "|----------|----------|-------------|------------|",
        f"| 自定义 (Custom) | {summary_stats['custom']['count']} | {summary_stats['custom']['total_duration_sec']} | {summary_stats['custom']['avg_accuracy']}% |",
        f"| 通用 (Generic)  | {summary_stats['generic']['count']} | {summary_stats['generic']['total_duration_sec']} | {summary_stats['generic']['avg_accuracy']}% |",
        "",
        "## 各任务明细",
        "",
        "| 任务 | 类型 | 评估方式 | 状态 | 耗时(秒) | 数据量 | 准确率 |",
        "|------|------|----------|------|----------|--------|--------|",
    ]
    for r in results:
        status_icon = "✅" if r["status"] == "success" else "❌"
        acc_str = f"{r['accuracy']:.2f}%" if r["accuracy"] is not None else "-"
        samples_str = str(r["num_samples"]) if r["num_samples"] is not None else "-"
        lines.append(
            f"| {r['task']} | {r['type']} | {r['eval_type']} | {status_icon} {r['status']} | {r['duration_sec']} | {samples_str} | {acc_str} |"
        )

    md_path = eval_dir / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # JSON 报告
    json_data = {
        "infer_task": infer_task,
        "eval_version": eval_version,
        "model": model_name,
        "timestamp": now,
        "avg_accuracy": round(avg, 4),
        "summary": summary_stats,
        "tasks": results,
    }
    json_path = eval_dir / "report.json"
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n📄 评测报告已生成:")
    print(f"   Markdown : {md_path}")
    print(f"   JSON     : {json_path}")
```

- [ ] **Step 7: 验证 eval_judge.py**

Run: `python eval_judge.py --help` 确认参数无误。

如果 Task 1 的验证已跑通（有 infer_meta.json），可执行：
```bash
python eval_judge.py --infer-task test_infer --eval-version test_v1
```

验证：
- `outputs/test_infer/eval_test_v1/report.json` 存在
- `outputs/test_infer/eval_test_v1/results/` 包含评测结果
- `outputs/test_infer/eval_test_v1/logs/eval/` 包含评测日志
- `outputs/test_infer/details/{timestamp}/` 中不再有 results/、summary/、logs/eval/

- [ ] **Step 8: Commit**

```bash
git add eval_judge.py
git commit -m "feat: 新增 eval_judge.py 评测脚本，支持推理结果复用和版本化管理"
```

---

## Task 3: run_mixed_benchmark.sh — 两阶段串联

**Files:**
- Modify: `run_mixed_benchmark.sh`

- [ ] **Step 1: 修改 docker run 部分为两阶段**

将现有的单个 `docker run` 替换为两阶段调用，保留 `LOCAL_CONCURRENCY=20` 等内存控制参数。

替换从 `# ── 以下是真正的评测逻辑` 开始到文件末尾的内容：

```bash
# ── 以下是真正的评测逻辑（在 nohup 后台中执行） ────────────────────
echo "🚀 开始执行混合评测任务，Task ID: ${TASK_ID}"
echo "---------------------------------------------------"

# ── 阶段 1：推理 ──────────────────────────────────────────────────────
echo ""
echo "📌 阶段 1/2：执行推理..."
echo "---------------------------------------------------"

docker run --rm \
    --env-file "${ENV_FILE}" \
    -e LOCAL_CONCURRENCY=20 \
    -v "${DATA_DIR}:/app/data" \
    -v "${OUTPUT_DIR}:/app/outputs" \
    -v "${CODE_DIR}/eval_entry.py:/app/eval_entry.py" \
    -v "${CODE_DIR}/eval_judge.py:/app/eval_judge.py" \
    -v "${CODE_DIR}/scripts:/app/scripts" \
    "${IMAGE_TAG}" \
    python eval_entry.py \
        --task-id "${TASK_ID}" \
        --model-config local_qwen \
        --tasks 1 34 36 43 44 60 \
        --generic-datasets \
            ceval_gen_0_shot_str \
            mmlu_redux_gen_5_shot_str \
            teledata_gen_0_shot \
            gpqa_gen_0_shot_str \
            bbh_gen_3_shot_cot_chat \
            BFCL_gen_simple \
            ifeval_0_shot_gen_str \
            math500_gen_0_shot_cot_chat_prompt \
            aime2025_gen_0_shot_chat_prompt \
            humaneval_gen_0_shot \
            livecodebench_0_shot_chat_v6 \
            telemath_gen_0_cot_shot \
            teleqna_gen_0_shot \
            tspec_gen_0_shot \
            telequad_gen_0_shot \
            tele_exam_gen_0_shot \
            tele_exam_gen_0_shot_str

INFER_RC=$?
if [ $INFER_RC -ne 0 ]; then
    echo "==================================================="
    echo "❌ 推理阶段出现异常（退出码: $INFER_RC），跳过评测阶段。"
    echo "==================================================="
    exit $INFER_RC
fi

echo ""
echo "✅ 推理阶段完成"

# ── 阶段 2：评测 ──────────────────────────────────────────────────────
echo ""
echo "📌 阶段 2/2：执行评测..."
echo "---------------------------------------------------"

docker run --rm \
    --env-file "${ENV_FILE}" \
    -e LOCAL_CONCURRENCY=20 \
    -v "${DATA_DIR}:/app/data" \
    -v "${OUTPUT_DIR}:/app/outputs" \
    -v "${CODE_DIR}/eval_entry.py:/app/eval_entry.py" \
    -v "${CODE_DIR}/eval_judge.py:/app/eval_judge.py" \
    -v "${CODE_DIR}/scripts:/app/scripts" \
    "${IMAGE_TAG}" \
    python eval_judge.py \
        --infer-task "${TASK_ID}"

if [ $? -eq 0 ]; then
    echo "==================================================="
    echo "✅ 评测流水线全部执行完成！"
    echo "📊 报告路径: ${OUTPUT_DIR}/${TASK_ID}/eval_*/report.md"
    echo "==================================================="
else
    echo "==================================================="
    echo "❌ 评测阶段出现异常，请检查详情日志。"
    echo "==================================================="
    exit 1
fi
```

- [ ] **Step 2: Commit**

```bash
git add run_mixed_benchmark.sh
git commit -m "refactor: run_mixed_benchmark.sh 改为推理+评测两阶段串联"
```

---

## Task 4: scripts/package_deploy.sh — 打包包含 eval_judge.py

**Files:**
- Modify: `scripts/package_deploy.sh`

- [ ] **Step 1: 添加 eval_judge.py 检查和打包**

在 Step 1 检查部分（约第 53 行后）添加：
```bash
[ -f "$PROJECT_ROOT/eval_judge.py" ]          || { echo "❌ 缺少 eval_judge.py"; exit 1; }
```

在 Step 4 复制业务代码部分（约第 97 行后）添加：
```bash
echo "  复制 eval_judge.py → code/..."
cp "$PROJECT_ROOT/eval_judge.py" "$TMP_DIR/eval_workspace/code/eval_judge.py"
```

更新 README.txt 中的目录结构说明，添加 eval_judge.py。

- [ ] **Step 2: Commit**

```bash
git add scripts/package_deploy.sh
git commit -m "chore: package_deploy.sh 打包时包含 eval_judge.py"
```

---

## Task 5: 用旧数据进行集成测试

**Files:**
- 测试数据来源: `/Users/jia/MyProjects/pythonProjects/cmcc_cxy/Bprocss/fmt/pt0_sft0/`

此任务验证 eval_judge.py 可以基于已有推理结果成功产出评测，不需要实际运行模型推理。

- [ ] **Step 1: 准备测试数据——构造 infer_meta.json**

从 `fmt/pt0_sft0/report.json` 中提取任务列表和时间戳映射，复制 predictions + configs + logs/infer 到测试目录：

```bash
# 创建测试目录
mkdir -p outputs/test_pt0/details

# 从旧数据复制推理产物（只复制 predictions、configs、logs/infer）
for dir in ../fmt/pt0_sft0/details/*/; do
    ts=$(basename "$dir")
    mkdir -p "outputs/test_pt0/details/$ts"
    cp -r "$dir/predictions" "outputs/test_pt0/details/$ts/"
    cp -r "$dir/configs" "outputs/test_pt0/details/$ts/"
    if [ -d "$dir/logs/infer" ]; then
        mkdir -p "outputs/test_pt0/details/$ts/logs"
        cp -r "$dir/logs/infer" "outputs/test_pt0/details/$ts/logs/"
    fi
done
```

然后用脚本生成 infer_meta.json（或手动编写）。可用 Python 一行脚本：

```python
# 运行于项目根目录
import json
from pathlib import Path

old_report = json.loads(Path("../fmt/pt0_sft0/report.json").read_text())
meta = {
    "task_id": "test_pt0",
    "model_config": "local_qwen",
    "model_name": old_report["model"],
    "infer_time": old_report["timestamp"],
    "tasks": {}
}
for t in old_report["tasks"]:
    ts = t["details_dir"].replace("details/", "")
    meta["tasks"][t["suite"]] = {
        "timestamp": ts,
        "task_name": t["task"],
        "type": t["type"],
        "num_samples": t["num_samples"],
        "duration_sec": t["duration_sec"],
        "status": t["status"],
    }
Path("outputs/test_pt0/infer_meta.json").write_text(
    json.dumps(meta, ensure_ascii=False, indent=2)
)
```

- [ ] **Step 2: 执行 eval_judge.py 对旧数据评测**

```bash
python eval_judge.py --infer-task test_pt0 --eval-version test_v1
```

- [ ] **Step 3: 验证结果**

检查：
- `outputs/test_pt0/eval_test_v1/report.json` 存在且可解析
- `outputs/test_pt0/eval_test_v1/results/` 包含各任务的评测结果文件
- `outputs/test_pt0/eval_test_v1/logs/eval/` 包含评测日志
- `outputs/test_pt0/details/` 中各任务目录只剩 predictions/ + configs/ + logs/infer/
- report.json 中的准确率与 `fmt/pt0_sft0/report.json` 基本一致

- [ ] **Step 4: 测试多版本并存**

```bash
# 先恢复 details 中的 results/summary（因为 Step 2 已搬走）
# 重新从旧数据复制一份 predictions
# 然后执行第二个版本
python eval_judge.py --infer-task test_pt0 --eval-version test_v2 --eval-tasks task_1_suite telequad_gen_0_shot
```

检查：
- `outputs/test_pt0/eval_test_v1/` 和 `outputs/test_pt0/eval_test_v2/` 并存
- test_v2 的 report.json 只包含 2 个任务

- [ ] **Step 5: 清理测试数据**

```bash
rm -rf outputs/test_pt0
```

- [ ] **Step 6: Commit**

```bash
git add eval_entry.py eval_judge.py run_mixed_benchmark.sh scripts/package_deploy.sh
git commit -m "feat: 推理与评测分离——完整实现，通过旧数据集成测试"
```

---

## 实施顺序总结

```
Task 1: eval_entry.py 改造（仅推理 + infer_meta.json）
    ↓
Task 2: eval_judge.py 新增（评测脚本）
    ↓
Task 3: run_mixed_benchmark.sh 改造（两阶段串联）
    ↓
Task 4: package_deploy.sh 更新（打包包含 eval_judge.py）
    ↓
Task 5: 旧数据集成测试（验证端到端流程）
```
