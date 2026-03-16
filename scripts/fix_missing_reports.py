import json
import re
from pathlib import Path
from datetime import datetime
import argparse

def fix_report(report_dir_path: str):
    report_dir = Path(report_dir_path)
    json_path = report_dir / "report.json"
    md_path = report_dir / "report.md"
    details_dir = report_dir / "details"
    
    if not json_path.exists():
        print(f"❌ 错误: 找不到文件 {json_path}")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    tasks = data.get("tasks", [])
    if not tasks:
        print("❌ 错误: report.json 中没有找到任务信息。")
        return
    
    # 提前预加载所有 details 里的配置信息，映射 suite -> details子目录
    suite_to_dir = {}
    if details_dir.exists():
        for detail_sub in details_dir.iterdir():
            if detail_sub.is_dir():
                config_files = list(detail_sub.glob("configs/*.py"))
                if config_files:
                    try:
                        cfg_text = config_files[0].read_text(encoding="utf-8")
                        # 正则提取 datasets=['task_36_suite']
                        m = re.search(r"datasets=\[\s*['\"]([^'\"]+)['\"]", cfg_text)
                        if m:
                            suite_name = m.group(1)
                            suite_to_dir[suite_name] = detail_sub.name
                    except Exception as e:
                        pass

    fixed_count = 0
    for task in tasks:
        # 只修复未拿到 accuracy 且状态为 success 的任务
        if task.get("accuracy") is None and task.get("status") == "success":
            suite = task.get("suite")
            dir_name = suite_to_dir.get(suite)
            
            # 如果没有直接匹配上，尝试子串匹配
            if not dir_name:
                for s, d in suite_to_dir.items():
                    if suite in s or s in suite:
                        dir_name = d
                        break

            if dir_name:
                target_detail_dir = details_dir / dir_name
                summary_files = list(target_detail_dir.glob("summary/summary_*.txt"))
                
                accuracy_val = None
                num_samples = None
                dataset_abbr = ""
                
                if summary_files:
                    summary_path = summary_files[0]
                    text = summary_path.read_text(encoding="utf-8")
                    lines = text.splitlines()
                    csv_start = -1
                    for idx, line in enumerate(lines):
                        if line.strip() == "csv format":
                            csv_start = idx
                            break
                            
                    if csv_start != -1:
                        data_lines = []
                        for i in range(csv_start + 3, len(lines)):
                            if lines[i].startswith("$") or not lines[i].strip():
                                break
                            data_lines.append(lines[i].strip())
                            
                        if data_lines:
                            total_acc = 0.0
                            valid_count = 0
                            for line in data_lines:
                                parts = line.split(",")
                                if len(parts) >= 5:
                                    dataset_abbr = parts[0]
                                    try:
                                        total_acc += float(parts[-1])
                                        valid_count += 1
                                    except ValueError:
                                        pass
                            if valid_count > 0:
                                accuracy_val = round(total_acc / valid_count, 2)
                                
                # 统计样本数
                details_files = list((target_detail_dir / "results").glob("**/*_details.jsonl"))
                if details_files:
                    try:
                        num_samples = sum(sum(1 for _ in open(f, "r", encoding="utf-8")) for f in details_files)
                    except Exception:
                        pass
                        
                if num_samples is None:
                    pred_dir = target_detail_dir / "predictions"
                    jsonl_files = list(pred_dir.glob(f"**/{dataset_abbr}.jsonl"))
                    if not jsonl_files:
                        # 退回正则或全部 jsonl 搜索
                        jsonl_files = list(pred_dir.glob(f"**/*.jsonl"))
                    if jsonl_files:
                        try:
                            num_samples = sum(sum(1 for _ in open(f, "r", encoding="utf-8")) for f in jsonl_files)
                        except Exception:
                            pass
                
                # 如果成功解析出 accuracy，更新 task 信息
                if accuracy_val is not None:
                    task["accuracy"] = accuracy_val
                    task["num_samples"] = num_samples
                    task["details_dir"] = f"details/{dir_name}"
                    fixed_count += 1
                    print(f"✅ 修复成功: {task['task']} | 目录: {dir_name} | Accuracy: {accuracy_val}% | 样本数: {num_samples}")
                else:
                    print(f"⚠️ 无法解析准确率: {task['task']} | 目录: {dir_name}")
            else:
                print(f"⚠️ 找不到对应的 details 目录: {task['task']} (suite: {suite})")

    if fixed_count > 0:
        # 重新计算所有的统计数据
        accuracies = [r["accuracy"] for r in tasks if r.get("accuracy") is not None]
        avg = sum(accuracies) / len(accuracies) if accuracies else 0.0
        data["avg_accuracy"] = round(avg, 4)
        
        summary_stats = {
            "custom": {"count": 0, "total_duration_sec": 0.0, "accuracies": []},
            "generic": {"count": 0, "total_duration_sec": 0.0, "accuracies": []},
        }

        for r in tasks:
            t = r.get("type", "generic")
            if t not in summary_stats:
                t = "generic"
            summary_stats[t]["count"] += 1
            summary_stats[t]["total_duration_sec"] += r.get("duration_sec", 0.0)
            if r.get("accuracy") is not None:
                summary_stats[t]["accuracies"].append(r["accuracy"])

        for tp in ["custom", "generic"]:
            accs = summary_stats[tp].pop("accuracies")
            summary_stats[tp]["avg_accuracy"] = round(sum(accs) / len(accs), 2) if accs else 0.0
            summary_stats[tp]["total_duration_sec"] = round(summary_stats[tp]["total_duration_sec"], 1)
            
        data["summary"] = summary_stats
        
        # 写回 json
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # 重写 Markdown 报告，保持和 eval_entry.py 完全一致的格式
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# 评测报告",
            "",
            f"- **Task ID**: `{data.get('task_id', 'unknown')}`",
            f"- **模型**: `{data.get('model', 'unknown')}`",
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
        for r in tasks:
            status = r.get("status", "failed")
            status_icon = "✅" if status == "success" else "❌"
            acc_str = f"{r['accuracy']:.2f}%" if r.get("accuracy") is not None else "-"
            samples_str = str(r.get("num_samples")) if r.get("num_samples") is not None else "-"
            lines.append(
                f"| {r.get('task', '-')} | {r.get('type', '-')} | {status_icon} {status} | {r.get('duration_sec', '-')} | {samples_str} | {acc_str} |"
            )
            
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
            
        print(f"\n🎉 恭喜！已成功修复 {fixed_count} 个任务的数据。")
        print(f"📄 重新生成了 {json_path}")
        print(f"📄 重新生成了 {md_path}")
    else:
        print("ℹ️ 没有发现需要修复的为空结果（或者无法在 details 中找到对应日志）。")

def main():
    parser = argparse.ArgumentParser(description="根据 details 目录修复 report.json 和 report.md 中丢失的结果，支持批量处理")
    parser.add_argument(
        "base_dir", 
        type=str, 
        help="包含多个任务目录的父路径（如 outputs/fmt），或单个任务的路径"
    )
    args = parser.parse_args()
    
    base_path = Path(args.base_dir)
    
    if not base_path.exists():
        print(f"❌ 错误: 路径不存在 {base_path}")
        return
        
    # 判断是指向了单个任务目录（存在 report.json）还是一个包含多个任务的父目录
    if (base_path / "report.json").exists():
        print(f"\n🚀 开始处理单个任务目录: {base_path.name}")
        fix_report(base_path)
    else:
        # 遍历所有子目录
        sub_dirs = [d for d in base_path.iterdir() if d.is_dir() and (d / "report.json").exists()]
        if not sub_dirs:
            print(f"⚠️ 在 {base_path} 下没有找到任何包含 report.json 的任务目录。")
            return
            
        print(f"\n🔍 找到 {len(sub_dirs)} 个任务目录，准备批量处理...")
        for i, sub_dir in enumerate(sub_dirs, 1):
            print(f"\n" + "="*50)
            print(f"🚀 [{i}/{len(sub_dirs)}] 正在处理: {sub_dir.name}")
            fix_report(sub_dir)

if __name__ == '__main__':
    main()
