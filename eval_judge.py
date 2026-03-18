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


# ── 参数解析 ────────────────────────────────────────────────────────
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


# ── LLM 评估器检测 ───────────────────────────────────────────────────
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


# ── 内存清理（与 eval_entry.py 保持一致） ───────────────────────────
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


# ── 单任务评测 ───────────────────────────────────────────────────────
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
            if dest.exists():
                # 合并模式：多任务结果累积到同一 eval_dir
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


# ── 生成评测报告 ─────────────────────────────────────────────────────
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


# ── 主流程 ──────────────────────────────────────────────────────────
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
