#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_entry.py - ais_bench 统一评测入口

用法:
    python eval_entry.py \
        --task-id round_3_v2 \
        --tasks 34 36 \
        --generic-datasets mmlu_redux_gen_5_shot_str ceval_gen_0_shot_str \
        --output-dir /results \
        --model qwen-plus \
        --concurrency 10

Docker 用法:
    docker run --rm \
        --env-file .env \
        -v /host/data:/app/data/custom_task \
        -v /host/results:/app/outputs \
        benchmark-eval:latest \
        python eval_entry.py --task-id round_1 --tasks 34 36
"""

import argparse
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
        nargs="*",
        default=[],
        help="要评测的自定义任务编号列表，如 34 36（对应 task_34_suite、task_36_suite）",
    )
    parser.add_argument(
        "--generic-datasets",
        nargs="*",
        default=[],
        help="要评测的通用数据集列表，如 mmlu_redux_gen_5_shot_str telequad_gen_0_shot",
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
        choices=[
            "maas",
            "maas_private",
            "bailian_qwen",
            "bailian_qwen_no_stream",
            "local_qwen",
        ],
        help="指定模型配置文件：maas=私域 MaaSAPI 等（默认 maas）",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="开启调试模式：ais_bench 串行执行任务，日志实时打印到终端（默认关闭，生产环境使用并发模式）",
    )
    parser.add_argument(
        "--num-prompts",
        type=int,
        default=None,
        help="每个任务最多评测多少条数据（默认 None 表示全量）。透传给 ais_bench --num-prompts。",
    )
    args = parser.parse_args()

    if not args.tasks and not args.generic_datasets:
        parser.error("Must specify at least one of --tasks or --generic-datasets")

    return args


# ── 数据文件校验 ────────────────────────────────────────────────────
def validate_data_files(task_nums: list, data_dir: Path):
    if not task_nums:
        return
    missing = []
    for num in task_nums:
        p = data_dir / f"task_{num}.jsonl"
        if not p.exists():
            missing.append(str(p))
    if missing:
        print("❌ 以下自定义任务数据文件不存在，请检查 --data-dir 路径：")
        for f in missing:
            print(f"   {f}")
        sys.exit(1)
    print(f"✅ 自定义任务数据文件校验通过（{len(task_nums)} 个任务）")


# ── 设置数据目录软链（当 data-dir 不是默认路径时） ─────────────────
def setup_data_symlink(data_dir: Path):
    default_dir = ROOT / "data" / "custom_task"
    if data_dir.resolve() == default_dir.resolve():
        return  # 已是默认路径，无需处理

    print(f"🔗 将自定义数据目录软链至: {data_dir}")
    default_dir.parent.mkdir(parents=True, exist_ok=True)
    if default_dir.is_symlink() or default_dir.exists():
        if default_dir.is_symlink():
            default_dir.unlink()
        else:
            shutil.rmtree(default_dir)
    default_dir.symlink_to(data_dir.resolve())


# ── 执行评测 ────────────────────────────────────────────────────────
def run_evaluation(
    task_nums: list,
    generic_datasets: list,
    output_dir: Path,
    task_id: str,
    model_config: str = "maas",
    concurrency: int = 1,
    debug: bool = False,
    num_prompts: int = None,
) -> list:

    # 构造任务队列，格式 (任务名, suite名称, 任务类型)
    queue = []
    for num in task_nums:
        queue.append((f"task_{num}", f"task_{num}_suite", "custom"))
    for dset in generic_datasets:
        queue.append((dset, dset, "generic"))

    ais_bench_output = ROOT / "outputs" / "default"
    results = []

    for i, (task_name, suite, task_type) in enumerate(queue, 1):
        if debug:
            print(
                f"\n[{i}/{len(queue)}] 🐛 执行任务 [{task_type}] (debug串行): {suite}"
            )
            # --debug 模式：ais_bench 串行执行，日志直接打印到终端，便于排查问题
            cmd = [
                "ais_bench",
                "--models",
                model_config,
                "--datasets",
                suite,
                "--debug",
            ]
        else:
            print(
                f"\n[{i}/{len(queue)}] 🚀 执行任务 [{task_type}] (并发={concurrency}): {suite}"
            )
            # 生产模式：去掉 --debug，用 --max-num-workers 开启真正并发
            cmd = [
                "ais_bench",
                "--models",
                model_config,
                "--datasets",
                suite,
                "--max-num-workers",
                str(concurrency),
            ]
        # 若指定了 --num-prompts，追加给 ais_bench（debug 和并发模式均生效）
        if num_prompts is not None:
            cmd += ["--num-prompts", str(num_prompts)]

        start_time = time.time()
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            text=True,
            capture_output=False,  # 实时输出到终端
        )
        duration = time.time() - start_time

        # 解析最新输出目录里的 summary，拿到准确率、对应的 ais_bench 时间戳目录名、以及样本数
        accuracy, ais_bench_dir, num_samples = _parse_latest_task_result(
            ais_bench_output, suite_name_pattern=suite
        )
        results.append(
            {
                "task": task_name,
                "type": task_type,
                "suite": suite,
                "status": "success" if proc.returncode == 0 else "failed",
                "accuracy": accuracy,
                "num_samples": num_samples,
                "duration_sec": round(duration, 1),
                "returncode": proc.returncode,
                "_ais_bench_dir": ais_bench_dir,  # 内部字段，生成报告时转换
            }
        )

    return results


def _parse_latest_task_result(ais_bench_output: Path, suite_name_pattern: str) -> tuple:
    """从最新 summary txt 里解析准确率和条数，同时返回对应的时间戳目录名。

    Returns:
        (accuracy: float | None, dir_name: str | None, num_samples: int | None)
            dir_name 即 outputs/default/ 下的时间戳目录名，如 '20260228_075043'
    """
    try:
        summaries = sorted(
            ais_bench_output.glob("*/summary/summary_*.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for summary_path in summaries:
            try:
                text = summary_path.read_text(encoding="utf-8")

                # 寻找 csv format 以下的行
                lines = text.splitlines()
                csv_start = -1
                for idx, line in enumerate(lines):
                    if line.strip() == "csv format":
                        csv_start = idx
                        break

                if csv_start != -1:
                    # 约 csv_start + 2 行是 header, csv_start + 3 是正式数据
                    data_lines = []
                    for i in range(csv_start + 3, len(lines)):
                        if lines[i].startswith("$") or not lines[i].strip():
                            break
                        data_lines.append(lines[i].strip())

                    if data_lines:
                        dataset_abbr = ""
                        total_acc = 0.0
                        for line in data_lines:
                            parts = line.split(",")
                            if len(parts) >= 5:
                                dataset_abbr = parts[0]
                                total_acc += float(parts[-1])

                        accuracy_val = total_acc / len(data_lines)
                        dir_name = summary_path.parent.parent.name

                        # 寻找对应的 jsonl 获取条目数
                        num_samples = None
                        pred_dir = summary_path.parent.parent / "predictions"
                        jsonl_files = list(pred_dir.glob(f"**/{dataset_abbr}.jsonl"))
                        if not jsonl_files:
                            jsonl_files = list(
                                pred_dir.glob(
                                    f"**/*{suite_name_pattern.replace('_suite', '')}*.jsonl"
                                )
                            )
                        if not jsonl_files:
                            jsonl_files = list(pred_dir.glob(f"**/*.jsonl"))

                        if jsonl_files:
                            try:
                                num_samples = sum(
                                    1
                                    for _ in open(jsonl_files[0], "r", encoding="utf-8")
                                )
                            except Exception:
                                pass

                        return round(accuracy_val, 2), dir_name, num_samples
            except Exception:
                pass
    except Exception:
        pass
    return None, None, None


# ── 生成综合报告 ────────────────────────────────────────────────────
def generate_report(results: list, task_id: str, model: str, output_dir: Path) -> Path:
    task_dir = output_dir / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    accuracies = [r["accuracy"] for r in results if r["accuracy"] is not None]
    avg = sum(accuracies) / len(accuracies) if accuracies else 0.0

    # ── 计算分类汇总
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

    # ── Markdown 报告
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
    for r in results:
        status_icon = "✅" if r["status"] == "success" else "❌"
        acc_str = f"{r['accuracy']:.2f}%" if r["accuracy"] is not None else "-"
        samples_str = str(r["num_samples"]) if r["num_samples"] is not None else "-"
        lines.append(
            f"| {r['task']} | {r['type']} | {status_icon} {r['status']} | {r['duration_sec']} | {samples_str} | {acc_str} |"
        )

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
        "summary": summary_stats,
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
    # local_qwen 的 batch_size 读取 LOCAL_CONCURRENCY，同步注入保证两层并发一致
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
    report_dir = generate_report(results, args.task_id, args.model, output_dir)

    # 打印摘要
    print("\n" + "=" * 60)
    print("📊 评测完成摘要")
    print("=" * 60)
    for r in results:
        icon = "✅" if r["status"] == "success" else "❌"
        acc = f"{r['accuracy']:.2f}%" if r["accuracy"] is not None else "N/A"
        print(
            f"  {icon} [{r['type'][:3]}] {r['task']:15s} 耗时: {r['duration_sec']}s  准确率: {acc}"
        )

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
