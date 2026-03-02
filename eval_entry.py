#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_entry.py - ais_bench 统一评测入口

用法:
    python eval_entry.py \\
        --task-id round_3_v2 \\
        --tasks 34 36 \\
        --output-dir /results \\
        --model qwen-plus \\
        --concurrency 10

Docker 用法:
    docker run --rm \\
        --env-file .env \\
        -v /host/data:/app/data/custom_task \\
        -v /host/results:/app/outputs \\
        benchmark-eval:latest \\
        python eval_entry.py --task-id round_1 --tasks 34 36
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# ── 项目根目录 ──────────────────────────────────────────────────────
ROOT = Path(__file__).parent.resolve()
load_dotenv(ROOT / ".env", override=False)


# ── 参数解析 ────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="ais_bench 统一评测入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--task-id",
        required=True,
        help="本次评测唯一标识，用于输出目录和报告命名（如 round_3_v2）",
    )
    parser.add_argument(
        "--tasks",
        nargs="+",
        required=True,
        help="要评测的任务编号列表，如 34 36（对应 task_34_suite、task_36_suite）",
    )
    parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data" / "custom_task"),
        help="测试数据目录，需包含 task_XX.jsonl 文件（默认 data/custom_task）",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "outputs"),
        help="评测结果输出根目录（默认 outputs/）",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("EVAL_MODEL_NAME", "qwen-plus"),
        help="模型名称，透传给 EVAL_MODEL_NAME 环境变量（默认 qwen-plus）",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.environ.get("EVAL_CONCURRENCY", "5")),
        help="并发请求数，透传给 EVAL_CONCURRENCY 环境变量（默认 5）",
    )
    parser.add_argument(
        "--model-config",
        default="maas",
        choices=["maas", "maas_private"],
        help="指定模型配置文件：maas=私域 MaaSAPI，maas_private=备用配置（默认 maas）",
    )
    return parser.parse_args()


# ── 数据文件校验 ────────────────────────────────────────────────────
def validate_data_files(task_nums: list, data_dir: Path):
    missing = []
    for num in task_nums:
        p = data_dir / f"task_{num}.jsonl"
        if not p.exists():
            missing.append(str(p))
    if missing:
        print("❌ 以下数据文件不存在，请检查 --data-dir 路径：")
        for f in missing:
            print(f"   {f}")
        sys.exit(1)
    print(f"✅ 数据文件校验通过（{len(task_nums)} 个任务）")


# ── 设置数据目录软链（当 data-dir 不是默认路径时） ─────────────────
def setup_data_symlink(data_dir: Path):
    default_dir = ROOT / "data" / "custom_task"
    if data_dir.resolve() == default_dir.resolve():
        return  # 已是默认路径，无需处理

    print(f"🔗 将数据目录软链至: {data_dir}")
    default_dir.parent.mkdir(parents=True, exist_ok=True)
    if default_dir.is_symlink() or default_dir.exists():
        if default_dir.is_symlink():
            default_dir.unlink()
        else:
            shutil.rmtree(default_dir)
    default_dir.symlink_to(data_dir.resolve())


# ── 执行评测 ────────────────────────────────────────────────────────
def run_evaluation(
    task_nums: list, output_dir: Path, task_id: str, model_config: str = "maas"
) -> dict:
    task_suites = [f"task_{n}_suite" for n in task_nums]
    ais_bench_output = ROOT / "outputs" / "default"

    results = []
    for i, (num, suite) in enumerate(zip(task_nums, task_suites), 1):
        print(f"\n[{i}/{len(task_nums)}] 🚀 执行任务: {suite}")

        cmd = ["ais_bench", "--models", model_config, "--datasets", suite, "--debug"]
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            text=True,
            capture_output=False,  # 实时输出到终端
        )

        # 解析最新输出目录里的 summary，同时拿到对应的 ais_bench 时间戳目录名
        accuracy, ais_bench_dir = _parse_latest_task_result(
            ais_bench_output, suite=f"task_{num}"
        )
        results.append(
            {
                "task": f"task_{num}",
                "suite": suite,
                "status": "success" if proc.returncode == 0 else "failed",
                "accuracy": accuracy,
                "returncode": proc.returncode,
                "_ais_bench_dir": ais_bench_dir,  # 内部字段，生成报告时转换
            }
        )

    return results


def _parse_latest_task_result(ais_bench_output: Path, suite: str) -> tuple:
    """从最新 summary txt 里解析准确率，同时返回对应的时间戳目录名。

    Returns:
        (accuracy: float | None, dir_name: str | None)
            dir_name 即 outputs/default/ 下的时间戳目录名，如 '20260228_075043'
    """
    try:
        summaries = sorted(
            ais_bench_output.glob("*/summary/summary_*.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for summary_path in summaries:
            text = summary_path.read_text(encoding="utf-8")
            # 格式: task_36    3d4148     accuracy  gen              100.00
            m = re.search(rf"{suite}\s+\S+\s+accuracy\s+\S+\s+([\d.]+)", text)
            if m:
                dir_name = summary_path.parent.parent.name  # e.g. '20260228_075043'
                return float(m.group(1)), dir_name
    except Exception:
        pass
    return None, None


# ── 生成综合报告 ────────────────────────────────────────────────────
def generate_report(results: list, task_id: str, model: str, output_dir: Path) -> Path:
    task_dir = output_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    accuracies = [r["accuracy"] for r in results if r["accuracy"] is not None]
    avg = sum(accuracies) / len(accuracies) if accuracies else 0.0

    # ── Markdown 报告
    lines = [
        "# 评测报告",
        "",
        f"- **Task ID**: `{task_id}`",
        f"- **模型**: `{model}`",
        f"- **时间**: {now}",
        f"- **综合准确率**: {avg:.2f}%",
        "",
        "## 各任务得分",
        "",
        "| 任务 | 状态 | 准确率 |",
        "|------|------|--------|",
    ]
    for r in results:
        status_icon = "✅" if r["status"] == "success" else "❌"
        acc_str = f"{r['accuracy']:.2f}%" if r["accuracy"] is not None else "-"
        lines.append(f"| {r['task']} | {status_icon} {r['status']} | {acc_str} |")

    md_content = "\n".join(lines)
    md_path = task_dir / "report.md"
    md_path.write_text(md_content, encoding="utf-8")

    # ── JSON 报告（供训练框架解析）
    # 把内部字段 _ais_bench_dir 转成用户可读的 details_dir，并排除内部字段
    tasks_for_json = []
    for r in results:
        ais_dir = r.get("_ais_bench_dir")
        entry = {k: v for k, v in r.items() if not k.startswith("_")}
        entry["details_dir"] = f"details/{ais_dir}" if ais_dir else None
        tasks_for_json.append(entry)

    json_data = {
        "task_id": task_id,
        "model": model,
        "timestamp": now,
        "avg_accuracy": round(avg, 4),
        "tasks": tasks_for_json,
    }
    json_path = task_dir / "report.json"
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── 复制 ais_bench 原始输出
    ais_out = ROOT / "outputs" / "default"
    dest_details = task_dir / "details"
    if ais_out.exists():
        if dest_details.exists():
            shutil.rmtree(dest_details)
        shutil.copytree(ais_out, dest_details)

    print("\n📄 报告已生成:")
    print(f"   Markdown : {md_path}")
    print(f"   JSON     : {json_path}")
    print(f"   原始输出 : {dest_details}")
    return task_dir


# ── 主流程 ──────────────────────────────────────────────────────────
def main():
    args = parse_args()

    # 注入到环境变量（子进程 ais_bench 会继承）
    os.environ["EVAL_MODEL_NAME"] = args.model
    os.environ["EVAL_CONCURRENCY"] = str(args.concurrency)

    data_dir = Path(args.data_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    print("=" * 60)
    print(f"📋 task_id     : {args.task_id}")
    print(f"📋 tasks       : {args.tasks}")
    print(f"📋 model       : {args.model} (并发 {args.concurrency})")
    print(f"📋 data_dir    : {data_dir}")
    print(f"📋 output_dir  : {output_dir / args.task_id}")
    print("=" * 60)

    validate_data_files(args.tasks, data_dir)
    setup_data_symlink(data_dir)

    results = run_evaluation(args.tasks, output_dir, args.task_id)
    report_dir = generate_report(results, args.task_id, args.model, output_dir)

    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 评测完成摘要")
    print("=" * 60)
    for r in results:
        icon = "✅" if r["status"] == "success" else "❌"
        acc = f"{r['accuracy']:.2f}%" if r["accuracy"] is not None else "N/A"
        print(f"  {icon} {r['task']:10s}  准确率: {acc}")

    accuracies = [r["accuracy"] for r in results if r["accuracy"] is not None]
    if accuracies:
        print(f"\n  🏆 综合平均: {sum(accuracies) / len(accuracies):.2f}%")
    print(f"\n  📁 结果目录: {report_dir}")
    print("=" * 60)

    # 外部调用时返回非 0 表示有任务失败
    failed = [r for r in results if r["status"] != "success"]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
