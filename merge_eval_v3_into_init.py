#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_eval_v3_into_init.py

将 fmt 目录下各实验组的 eval_v3 合并进 eval_init：
  - logs / results / summary 子目录：覆盖写入（已存在则覆盖）
  - report.json：eval_v3 涉及的任务替换或追加，重算 summary
  - report.md：根据合并后的 report.json 重新生成

用法：
    python merge_eval_v3_into_init.py --fmt-dir /path/to/fmt
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


def recalc_summary(tasks: list) -> dict:
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


def generate_report_md(report: dict) -> str:
    infer_task = report.get("infer_task", "-")
    eval_version = report.get("eval_version", "-")
    model = report.get("model", "-")
    timestamp = report.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    avg_accuracy = report.get("avg_accuracy", 0.0)
    summary = report.get("summary", {})
    tasks = report.get("tasks", [])

    custom_s = summary.get("custom", {})
    generic_s = summary.get("generic", {})

    lines = [
        "# 评测报告",
        "",
        f"- **Infer Task**: `{infer_task}`",
        f"- **Eval Version**: `{eval_version}`",
        f"- **模型**: `{model}`",
        f"- **时间**: {timestamp}",
        f"- **综合准确率**: {avg_accuracy:.2f}%",
        "",
        "## 统计摘要",
        "",
        "| 任务类型 | 任务数量 | 总耗时 (秒) | 平均准确率 |",
        "|----------|----------|-------------|------------|",
        f"| 自定义 (Custom) | {custom_s.get('count', 0)} | {custom_s.get('total_duration_sec', 0)} | {custom_s.get('avg_accuracy', 0)}% |",
        f"| 通用 (Generic)  | {generic_s.get('count', 0)} | {generic_s.get('total_duration_sec', 0)} | {generic_s.get('avg_accuracy', 0)}% |",
        "",
        "## 各任务明细",
        "",
        "| 任务 | 类型 | 评估方式 | 状态 | 耗时(秒) | 数据量 | 准确率 |",
        "|------|------|----------|------|----------|--------|--------|",
    ]

    for t in tasks:
        status_icon = "✅" if t.get("status") == "success" else "❌"
        lines.append(
            f"| {t.get('task', t.get('suite', '-'))} "
            f"| {t.get('type', '-')} "
            f"| {t.get('eval_type', '-')} "
            f"| {status_icon} {t.get('status', '-')} "
            f"| {t.get('duration_sec', '-')} "
            f"| {t.get('num_samples', '-')} "
            f"| {t.get('accuracy', 0):.2f}% |"
        )

    return "\n".join(lines) + "\n"


def merge_dirs_overwrite(src: Path, dst: Path):
    """把 src 下的子目录/文件递归合并到 dst，已存在则覆盖。"""
    if not src.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        dst_item = dst / item.name
        if item.is_dir():
            if dst_item.exists():
                shutil.rmtree(str(dst_item))
                print(f"    🔄 覆盖目录: {dst_item.name}")
            shutil.copytree(str(item), str(dst_item))
        else:
            action = "🔄 覆盖" if dst_item.exists() else "✅ 复制"
            shutil.copy2(str(item), str(dst_item))
            print(f"    {action} 文件: {dst_item.name}")


def merge_report(init_report_path: Path, v3_report_path: Path):
    """将 eval_v3 的 tasks 替换/追加进 eval_init 的 report.json，并重算 summary 和 report.md。"""
    init = json.loads(init_report_path.read_text(encoding="utf-8"))
    v3 = json.loads(v3_report_path.read_text(encoding="utf-8"))

    v3_tasks = v3.get("tasks", [])
    v3_suites = {t.get("suite") for t in v3_tasks}

    # 过滤掉 init 中与 v3 重复的任务，再追加 v3 的任务
    base_tasks = [t for t in init.get("tasks", []) if t.get("suite") not in v3_suites]
    replaced = [t.get("suite") for t in init.get("tasks", []) if t.get("suite") in v3_suites]
    added = [t.get("suite") for t in v3_tasks if t.get("suite") not in {t2.get("suite") for t2 in init.get("tasks", [])}]

    merged_tasks = base_tasks + v3_tasks
    new_summary = recalc_summary(merged_tasks)
    all_acc = [t.get("accuracy", 0) or 0 for t in merged_tasks]
    new_avg = round(sum(all_acc) / len(all_acc), 4) if all_acc else 0.0

    init["tasks"] = merged_tasks
    init["summary"] = new_summary
    init["avg_accuracy"] = new_avg

    init_report_path.write_text(
        json.dumps(init, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if replaced:
        print(f"    🔄 替换任务: {replaced}")
    if added:
        print(f"    ➕ 新增任务: {added}")
    print(f"    📊 新 avg_accuracy={new_avg}")

    # 同步更新 report.md
    report_md_path = init_report_path.parent / "report.md"
    report_md_path.write_text(generate_report_md(init), encoding="utf-8")
    print(f"    📝 report.md 已更新")


def merge_group(group_dir: Path, src_version: str, dst_version: str):
    src = group_dir / src_version
    dst = group_dir / dst_version

    if not dst.exists():
        print(f"  ⚠️  {dst_version} 不存在，跳过 {group_dir.name}")
        return
    if not src.exists():
        print(f"  ⚠️  {src_version} 不存在，跳过 {group_dir.name}")
        return

    print(f"\n🔀 处理: {group_dir.name}")

    for subdir in ("logs", "results", "summary"):
        print(f"  📁 合并 {subdir}/")
        merge_dirs_overwrite(src / subdir, dst / subdir)

    src_report = src / "report.json"
    dst_report = dst / "report.json"
    if not src_report.exists():
        print(f"  ⚠️  {src_version}/report.json 不存在，跳过 report 合并")
        return
    if not dst_report.exists():
        print(f"  ⚠️  {dst_version}/report.json 不存在，无法合并 report")
        return

    print("  📄 合并 report.json / report.md")
    merge_report(dst_report, src_report)


def main():
    parser = argparse.ArgumentParser(description="将 src_version 合并进 dst_version（覆盖模式）")
    parser.add_argument(
        "--fmt-dir",
        default="/Users/jia/windowsShare/newfmt",
        help="fmt 根目录（各实验组的父目录）",
    )
    parser.add_argument("--src-version", default="eval_v3", help="来源版本目录名")
    parser.add_argument("--dst-version", default="eval_init", help="目标版本目录名")
    parser.add_argument("--filter", default="", help="只处理包含该字符串的实验组名（为空则处理全部）")
    parser.add_argument("--exclude", default="", help="排除包含该字符串的实验组名")
    args = parser.parse_args()

    fmt_dir = Path(args.fmt_dir)
    if not fmt_dir.exists():
        print(f"❌ 目录不存在: {fmt_dir}")
        return

    groups = sorted(e for e in fmt_dir.iterdir() if e.is_dir())
    if args.filter:
        groups = [g for g in groups if args.filter in g.name]
    if args.exclude:
        groups = [g for g in groups if args.exclude not in g.name]

    print(f"找到 {len(groups)} 个实验组: {[g.name for g in groups]}")
    print(f"合并方向: {args.src_version} → {args.dst_version}")

    for group in groups:
        merge_group(group, args.src_version, args.dst_version)

    print("\n✅ 全部合并完成")


if __name__ == "__main__":
    main()
