#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_batch_reports.py - 合并分批评测报告为统一格式

将多个批次的 report_batchN.json 合并为一份完整的 report.md + report.json，
输出格式与 eval_entry.py 生成的单次报告完全一致，下游处理无需修改。

用法:
    python merge_batch_reports.py \
        --task-id mixed_eval_20260314_100000 \
        --output-dir /app/outputs \
        --model local_qwen \
        --batch-jsons \
            /app/outputs/mixed_eval_.../report_batch1.json \
            /app/outputs/mixed_eval_.../report_batch2.json \
            /app/outputs/mixed_eval_.../report_batch3.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def merge_reports(batch_jsons: list, task_id: str, model: str, output_dir: Path) -> Path:
    task_dir = output_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    # ── 收集所有批次的 tasks ──────────────────────────────────────────
    all_tasks = []
    for json_path in batch_jsons:
        p = Path(json_path)
        if not p.exists():
            print(f"  跳过（文件不存在）: {json_path}")
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        all_tasks.extend(data.get("tasks", []))

    if not all_tasks:
        print("没有找到任何批次数据，无法合并")
        sys.exit(1)

    print(f"  共合并 {len(all_tasks)} 个任务")

    # ── 计算汇总统计 ──────────────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    accuracies = [t["accuracy"] for t in all_tasks if t.get("accuracy") is not None]
    avg = sum(accuracies) / len(accuracies) if accuracies else 0.0

    summary_stats = {
        "custom": {"count": 0, "total_duration_sec": 0.0, "accuracies": []},
        "generic": {"count": 0, "total_duration_sec": 0.0, "accuracies": []},
    }
    for t in all_tasks:
        tp = t.get("type", "generic")
        summary_stats[tp]["count"] += 1
        summary_stats[tp]["total_duration_sec"] += t.get("duration_sec", 0)
        if t.get("accuracy") is not None:
            summary_stats[tp]["accuracies"].append(t["accuracy"])

    for tp in ["custom", "generic"]:
        accs = summary_stats[tp].pop("accuracies")
        summary_stats[tp]["avg_accuracy"] = (
            round(sum(accs) / len(accs), 2) if accs else 0.0
        )
        summary_stats[tp]["total_duration_sec"] = round(
            summary_stats[tp]["total_duration_sec"], 1
        )

    # ── 生成 Markdown 报告（与 eval_entry.py generate_report 完全一致）
    lines = [
        "# 评测报告",
        "",
        f"- **Task ID**: `{task_id}`",
        f"- **模型**: `{model}`",
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
        "| 任务 | 类型 | 状态 | 耗时(秒) | 数据量 | 准确率 |",
        "|------|------|------|----------|--------|--------|",
    ]
    for r in all_tasks:
        status = r.get("status", "unknown")
        status_icon = "✅" if status == "success" else "❌"
        acc = r.get("accuracy")
        acc_str = f"{acc:.2f}%" if acc is not None else "-"
        samples = r.get("num_samples")
        samples_str = str(samples) if samples is not None else "-"
        lines.append(
            f"| {r.get('task', '-')} | {r.get('type', '-')} | {status_icon} {status} | {r.get('duration_sec', '-')} | {samples_str} | {acc_str} |"
        )

    md_path = task_dir / "report.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    # ── 生成 JSON 报告（与 eval_entry.py generate_report 完全一致）────
    json_data = {
        "task_id": task_id,
        "model": model,
        "timestamp": now,
        "avg_accuracy": round(avg, 4),
        "summary": summary_stats,
        "tasks": all_tasks,
    }
    json_path = task_dir / "report.json"
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n📄 合并报告已生成:")
    print(f"   Markdown : {md_path}")
    print(f"   JSON     : {json_path}")
    return task_dir


def main():
    parser = argparse.ArgumentParser(description="合并分批评测报告")
    parser.add_argument("--task-id", required=True, help="统一 Task ID")
    parser.add_argument("--output-dir", required=True, help="输出根目录")
    parser.add_argument("--batch-jsons", nargs="+", required=True,
                        help="各批次 report_batchN.json 文件路径")
    parser.add_argument("--model", default="local_qwen", help="模型名称")
    args = parser.parse_args()

    merge_reports(
        batch_jsons=args.batch_jsons,
        task_id=args.task_id,
        model=args.model,
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    main()
