#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_eval_v3_into_v2.py

将 fmt 目录下各实验组的 eval_v3 合并进 eval_v2：
  - logs / results / summary 子目录：直接复制（跳过已存在项）
  - report.json：tasks 追加 + summary 重新统计

用法：
    python merge_eval_v3_into_v2.py --fmt-dir /path/to/fmt
"""

import argparse
import json
import os
import shutil
from pathlib import Path


def recalc_summary(tasks: list) -> dict:
    """根据 tasks 列表重新计算 summary（simple mean of accuracy）。"""
    custom = [t for t in tasks if t.get("type") == "custom"]
    generic = [t for t in tasks if t.get("type") != "custom"]

    def _group_stat(group):
        count = len(group)
        total_dur = sum(t.get("duration_sec", 0) or 0 for t in group)
        avg_acc = (
            round(sum(t.get("accuracy", 0) or 0 for t in group) / count, 2)
            if count else 0.0
        )
        return {"count": count, "total_duration_sec": round(total_dur, 1), "avg_accuracy": avg_acc}

    return {"custom": _group_stat(custom), "generic": _group_stat(generic)}


def merge_dirs(src: Path, dst: Path):
    """把 src 下的子目录/文件递归合并到 dst，跳过已存在的条目。"""
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        dst_item = dst / item.name
        if dst_item.exists():
            print(f"    ⚠️  跳过（已存在）: {dst_item}")
            continue
        if item.is_dir():
            shutil.copytree(str(item), str(dst_item))
        else:
            shutil.copy2(str(item), str(dst_item))
        print(f"    ✅ 复制: {item} → {dst_item}")


def merge_report(v2_report_path: Path, v3_report_path: Path):
    """将 v3 的 tasks 追加进 v2 的 report.json，并重算 summary。"""
    v2 = json.loads(v2_report_path.read_text(encoding="utf-8"))
    v3 = json.loads(v3_report_path.read_text(encoding="utf-8"))

    existing_suites = {t.get("suite") for t in v2.get("tasks", [])}
    new_tasks = [t for t in v3.get("tasks", []) if t.get("suite") not in existing_suites]

    if not new_tasks:
        print("    ⚠️  report.json：无新任务可追加（全部已存在），跳过")
        return

    merged_tasks = v2.get("tasks", []) + new_tasks
    new_summary = recalc_summary(merged_tasks)

    # 重算整体 avg_accuracy（所有任务的简单均值）
    all_acc = [t.get("accuracy", 0) or 0 for t in merged_tasks]
    new_avg = round(sum(all_acc) / len(all_acc), 4) if all_acc else 0.0

    v2["tasks"] = merged_tasks
    v2["summary"] = new_summary
    v2["avg_accuracy"] = new_avg

    v2_report_path.write_text(
        json.dumps(v2, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"    ✅ report.json 追加 {len(new_tasks)} 个任务: "
          f"{[t.get('suite') for t in new_tasks]}")
    print(f"    📊 新 avg_accuracy={new_avg}, summary={new_summary}")


def merge_group(group_dir: Path):
    v2 = group_dir / "eval_v2"
    v3 = group_dir / "eval_v3"

    if not v2.exists():
        print(f"  ⚠️  eval_v2 不存在，跳过 {group_dir.name}")
        return
    if not v3.exists():
        print(f"  ⚠️  eval_v3 不存在，跳过 {group_dir.name}")
        return

    print(f"\n🔀 处理: {group_dir.name}")

    for subdir in ("logs", "results", "summary"):
        print(f"  📁 合并 {subdir}/")
        merge_dirs(v3 / subdir, v2 / subdir)

    v3_report = v3 / "report.json"
    v2_report = v2 / "report.json"
    if not v3_report.exists():
        print("  ⚠️  eval_v3/report.json 不存在，跳过 report 合并")
        return
    if not v2_report.exists():
        print("  ⚠️  eval_v2/report.json 不存在，无法合并 report")
        return

    print("  📄 合并 report.json")
    merge_report(v2_report, v3_report)


def main():
    parser = argparse.ArgumentParser(description="将 eval_v3 合并进 eval_v2")
    parser.add_argument(
        "--fmt-dir",
        default="/Users/jia/windowsShare/newfmt_2",
        help="fmt 根目录（各实验组的父目录）",
    )
    args = parser.parse_args()

    fmt_dir = Path(args.fmt_dir)
    if not fmt_dir.exists():
        print(f"❌ 目录不存在: {fmt_dir}")
        return

    groups = sorted(e for e in fmt_dir.iterdir() if e.is_dir())
    print(f"找到 {len(groups)} 个实验组: {[g.name for g in groups]}")

    for group in groups:
        merge_group(group)

    print("\n✅ 全部合并完成")


if __name__ == "__main__":
    main()
