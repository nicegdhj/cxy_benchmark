#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_fmt_to_infer_meta.py - 将旧格式 report.json 转换为 infer_meta.json

旧目录结构（fmt/ptXX/）：
    pt0_sft0/
    ├── report.json          # 旧格式报告
    ├── report.md
    └── details/
        └── {timestamp}/    # predictions + configs + results + summary + logs

新结构只需在同目录下生成：
    pt0_sft0/
    └── infer_meta.json      # eval_judge.py 所需元数据

生成后即可直接调用 eval_judge.py：
    python eval_judge.py --infer-task pt0_sft0 --output-dir /path/to/fmt

用法:
    # 转换单个目录
    python scripts/migrate_fmt_to_infer_meta.py /path/to/fmt/pt0_sft0 --model-config local_qwen

    # 批量转换 fmt/ 下所有 ptXX 目录
    python scripts/migrate_fmt_to_infer_meta.py /path/to/fmt --all --model-config local_qwen
"""

import argparse
import json
import sys
from pathlib import Path


def convert_one(pt_dir: Path, model_config: str, overwrite: bool = False) -> bool:
    """将单个 ptXX/ 目录的 report.json 转换为 infer_meta.json。"""
    report_path = pt_dir / "report.json"
    meta_path = pt_dir / "infer_meta.json"

    if not report_path.exists():
        print(f"  ⚠️  跳过 {pt_dir.name}：找不到 report.json")
        return False

    if meta_path.exists() and not overwrite:
        print(f"  ⏭️  跳过 {pt_dir.name}：infer_meta.json 已存在（--overwrite 可强制覆盖）")
        return False

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ❌ {pt_dir.name}：读取 report.json 失败：{e}")
        return False

    meta = {
        "task_id": report.get("task_id", pt_dir.name),
        "model_config": model_config,
        "model_name": report.get("model", "unknown"),
        "infer_time": report.get("timestamp", ""),
        "tasks": {},
    }

    for t in report.get("tasks", []):
        suite = t.get("suite")
        details_dir = t.get("details_dir", "")
        # details_dir 格式为 "details/20260309_140520"，取最后一段
        timestamp = details_dir.split("/")[-1] if details_dir else None

        if not suite or not timestamp:
            print(f"    ⚠️  任务缺少 suite 或 details_dir，跳过：{t}")
            continue

        # 校验 predictions 目录是否存在
        pred_dir = pt_dir / "details" / timestamp / "predictions"
        if not pred_dir.exists():
            print(f"    ⚠️  {suite}：predictions 目录不存在（{pred_dir}），仍写入 meta")

        meta["tasks"][suite] = {
            "timestamp": timestamp,
            "task_name": t.get("task", suite),
            "type": t.get("type", "custom"),
            "num_samples": t.get("num_samples"),
            "duration_sec": t.get("duration_sec"),
            "status": t.get("status", "success"),
        }

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ {pt_dir.name}：生成 infer_meta.json（{len(meta['tasks'])} 个任务）")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="将旧格式 report.json 转换为 eval_judge.py 所需的 infer_meta.json",
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        help="单个 ptXX 目录，或 --all 时为包含多个 ptXX 的父目录（如 fmt/）",
    )
    parser.add_argument(
        "--model-config",
        default="local_qwen",
        choices=["maas", "maas_private", "bailian_qwen", "bailian_qwen_no_stream", "local_qwen"],
        help="模型配置名（默认 local_qwen），用于 eval_judge.py 调用 ais_bench --models",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="批量处理：将 path 下所有包含 report.json 的子目录都转换",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="强制覆盖已存在的 infer_meta.json",
    )
    args = parser.parse_args()

    base = Path(args.path).resolve()

    if args.all:
        if not base.is_dir():
            print(f"❌ {base} 不是目录")
            sys.exit(1)
        candidates = sorted(
            [d for d in base.iterdir() if d.is_dir() and (d / "report.json").exists()]
        )
        if not candidates:
            print(f"❌ {base} 下找不到包含 report.json 的子目录")
            sys.exit(1)
        print(f"找到 {len(candidates)} 个目录，开始批量转换...\n")
        ok = sum(convert_one(d, args.model_config, args.overwrite) for d in candidates)
        print(f"\n完成：{ok}/{len(candidates)} 个目录成功生成 infer_meta.json")
    else:
        if not base.is_dir():
            print(f"❌ {base} 不是目录")
            sys.exit(1)
        convert_one(base, args.model_config, args.overwrite)
        print(f"\n现在可以运行：")
        print(f"  python eval_judge.py --infer-task {base.name} --output-dir {base.parent}")


if __name__ == "__main__":
    main()
