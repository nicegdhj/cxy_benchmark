#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_bfcl_details_xlsx.py

修复 BFCL v3 明细 Excel 中 origin_prompt 缺失的问题。

原因：aggregate_eval_reports.py 从 prediction.origin_prompt 字段读取，
      但 BFCL 的 origin_prompt 存储在
      prediction.inference_log[0].single_turn_inference_data.message（user role）中。

本脚本直接从各实验组的 eval_version/results/BFCL_gen_simple/_details.jsonl
重新生成 Excel，并覆盖 aggregated_reports 目录中对应的 xlsx 文件。

用法：
    python scripts/fix_bfcl_details_xlsx.py \
        --fmt-dir ~/windowsShare/newfmt_2 \
        --eval-version eval_v2 \
        --reports-dir outputs/newfmt_2_aggregated_reports_20260403_153903 \
        --task-name "BFCL v3-单轮任务子集"
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd


def extract_origin_prompt(pred: dict) -> str:
    """从 BFCL prediction 中提取 origin_prompt（user 消息内容）。"""
    logs = pred.get("inference_log", [])
    if logs:
        msg_list = logs[0].get("single_turn_inference_data", {}).get("message", [])
        for m in msg_list:
            if m.get("role") == "user":
                return m.get("content", "")
    return ""


def clean(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False, indent=2)
    else:
        s = str(v)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)


def fix_model(jsonl_path: Path, xlsx_path: Path):
    rows = []
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            pred_raw = obj.get("prediction", {})
            eval_res = obj.get("eval_res")
            eval_details = obj.get("eval_details")

            origin_prompt = extract_origin_prompt(pred_raw)
            prediction_val = pred_raw.get("prediction", "")
            gold = pred_raw.get("gold", "")

            rows.append({
                "eval_res": clean(eval_res),
                "eval_details": clean(eval_details),
                "origin_prompt": clean(origin_prompt),
                "prediction": clean(prediction_val),
                "gold": clean(gold),
            })

    df = pd.DataFrame(rows)
    df.to_excel(xlsx_path, index=False)
    missing_after = df["origin_prompt"].apply(lambda v: str(v).strip() in ("", "null", "nan") or len(str(v)) < 4).sum()
    print(f"    ✅ {xlsx_path.name}  {len(rows)} 行  修复后缺失: {missing_after}")


def main():
    parser = argparse.ArgumentParser(description="修复 BFCL details xlsx 中 origin_prompt 缺失")
    parser.add_argument("--fmt-dir", required=True, help="fmt 根目录")
    parser.add_argument("--eval-version", default="eval_v2", help="评测版本目录名")
    parser.add_argument("--reports-dir", required=True, help="aggregated_reports 输出目录")
    parser.add_argument("--task-name", default="BFCL v3-单轮任务子集", help="reports-dir 下的任务目录名")
    parser.add_argument("--suite", default="BFCL_gen_simple", help="eval results 中的 suite 目录名")
    parser.add_argument("--jsonl-stem", default="BFCL-v3-simple", help="details jsonl 文件名（不含 _details.jsonl）")
    args = parser.parse_args()

    fmt_dir = Path(args.fmt_dir).expanduser()
    reports_dir = Path(args.reports_dir)
    task_reports_dir = reports_dir / args.task_name

    if not task_reports_dir.exists():
        print(f"❌ 找不到任务目录: {task_reports_dir}")
        return

    for model_dir in sorted(fmt_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        model_name = model_dir.name

        jsonl_path = model_dir / args.eval_version / "results" / args.suite / f"{args.jsonl_stem}_details.jsonl"
        if not jsonl_path.exists():
            print(f"  ⚠️  {model_name}: 找不到 {jsonl_path.name}，跳过")
            continue

        xlsx_path = task_reports_dir / model_name / f"{args.jsonl_stem}_details.xlsx"
        if not xlsx_path.exists():
            print(f"  ⚠️  {model_name}: 找不到 xlsx {xlsx_path}，跳过")
            continue

        print(f"  🔧 {model_name}")
        fix_model(jsonl_path, xlsx_path)

    print("\n✅ BFCL details xlsx 修复完成")


if __name__ == "__main__":
    main()
