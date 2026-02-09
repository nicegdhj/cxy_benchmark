#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量执行所有任务并统计结果

逐个执行任务，实时显示输出，收集结果并生成统计报告
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 配置文件目录
CONFIG_DIR = PROJECT_ROOT / "ais_bench" / "benchmark" / "configs" / "datasets" / "custom_task"

# 结果输出目录
RESULT_DIR = PROJECT_ROOT / "outputs" / "batch_run"


def get_all_task_suites():
    """获取所有任务配置文件"""
    task_files = sorted(
        CONFIG_DIR.glob("task_*_suite.py"),
        key=lambda x: int(re.search(r'task_(\d+)_suite', x.stem).group(1))
    )
    return [f.stem for f in task_files]


def run_single_task(task_name: str, model: str = "maas") -> dict:
    """执行单个任务，实时输出"""
    
    cmd = [
        "ais_bench",
        "--models", model,
        "--datasets", task_name,
        "--debug",  # 添加 debug 模式避免交互式进度条卡住
    ]
    
    # 使用实时输出
    process = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    output_lines = []
    try:
        for line in process.stdout:
            print(line, end='')  # 实时打印
            output_lines.append(line)
        
        process.wait()
        output = "".join(output_lines)
        
        # 解析结果 - 查找 accuracy 或其他指标
        accuracy_match = re.search(r"'accuracy':\s*([\d.]+)", output)
        if not accuracy_match:
            # 尝试从表格中匹配
            task_short = task_name.replace("_suite", "")
            table_match = re.search(rf'\|\s*{task_short}\s*\|[^|]+\|[^|]+\|[^|]+\|\s*([\d.]+)', output)
            if table_match:
                accuracy = float(table_match.group(1))
            else:
                accuracy = None
        else:
            accuracy = float(accuracy_match.group(1))
        
        return {
            "task": task_name,
            "status": "success" if process.returncode == 0 else "failed",
            "accuracy": accuracy,
            "returncode": process.returncode
        }
        
    except KeyboardInterrupt:
        process.terminate()
        return {
            "task": task_name,
            "status": "interrupted",
            "accuracy": None,
            "returncode": -1
        }
    except Exception as e:
        return {
            "task": task_name,
            "status": "error",
            "accuracy": None,
            "error": str(e)
        }


def generate_report(results: list, output_file: Path) -> str:
    """生成统计报告"""
    
    total = len(results)
    success_count = sum(1 for r in results if r["status"] == "success")
    accuracies = [r["accuracy"] for r in results if r["accuracy"] is not None]
    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
    
    report = []
    report.append("=" * 80)
    report.append("📊 批量任务执行报告")
    report.append(f"⏰ 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    report.append("")
    report.append("## 总体统计")
    report.append(f"- 总任务数: {total}")
    report.append(f"- 成功: {success_count} ({success_count/total*100:.1f}%)" if total > 0 else "- 成功: 0")
    report.append(f"- 平均准确率: {avg_accuracy:.2f}%")
    report.append("")
    report.append("## 详细结果")
    report.append("")
    report.append("| 任务 | 状态 | 准确率 |")
    report.append("|------|------|--------|")
    
    for r in results:
        status_emoji = {"success": "✅", "failed": "❌", "interrupted": "⏸️", "error": "💥"}.get(r["status"], "❓")
        accuracy_str = f"{r['accuracy']:.2f}%" if r["accuracy"] is not None else "-"
        report.append(f"| {r['task']} | {status_emoji} {r['status']} | {accuracy_str} |")
    
    report_text = "\n".join(report)
    
    # 保存报告
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_text)
    
    # 保存 JSON
    json_file = output_file.with_suffix(".json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return report_text


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="批量执行任务并统计结果")
    parser.add_argument("--model", default="maas", help="模型配置名称")
    parser.add_argument("--tasks", nargs="+", help="指定要执行的任务列表")
    parser.add_argument("--start", type=int, default=1, help="起始任务编号")
    parser.add_argument("--end", type=int, default=85, help="结束任务编号")
    args = parser.parse_args()
    
    # 获取任务列表
    all_tasks = get_all_task_suites()
    
    if args.tasks:
        tasks_to_run = [t for t in args.tasks if t in all_tasks]
    else:
        tasks_to_run = []
        for task in all_tasks:
            task_num = int(re.search(r'task_(\d+)_suite', task).group(1))
            if args.start <= task_num <= args.end:
                tasks_to_run.append(task)
    
    print(f"📋 共找到 {len(tasks_to_run)} 个任务待执行")
    print(f"🔧 使用模型: {args.model}")
    print("=" * 60)
    
    # 逐个执行任务
    results = []
    for i, task in enumerate(tasks_to_run, 1):
        print(f"\n[{i}/{len(tasks_to_run)}] 🚀 执行任务: {task}")
        print("-" * 40)
        
        result = run_single_task(task, args.model)
        results.append(result)
        
        # 打印单任务结果
        status_emoji = "✅" if result["status"] == "success" else "❌"
        accuracy_str = f" (准确率: {result['accuracy']:.2f}%)" if result["accuracy"] is not None else ""
        print(f"\n{status_emoji} 任务 {task} 完成: {result['status']}{accuracy_str}")
        print("-" * 40)
    
    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = RESULT_DIR / f"batch_report_{timestamp}.md"
    
    print("\n" + "=" * 60)
    report = generate_report(results, report_file)
    print(report)
    print("=" * 60)
    print(f"\n📄 报告已保存到: {report_file}")
    print(f"📄 原始数据已保存到: {report_file.with_suffix('.json')}")


if __name__ == "__main__":
    main()
