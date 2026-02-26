#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量生成任务配置脚本

读取 mydata/task_info 目录下的任务模板，生成：
1. 数据集配置文件：ais_bench/benchmark/configs/datasets/custom_task/task_X_suite.py
2. 数据文件：data/custom_task/task_X.jsonl
"""

import json
import os
import re
from pathlib import Path


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 输入目录
TASK_INFO_DIR = PROJECT_ROOT / "mydata" / "task_info"

# 输出目录
CONFIG_OUTPUT_DIR = (
    PROJECT_ROOT / "ais_bench" / "benchmark" / "configs" / "datasets" / "custom_task"
)
DATA_OUTPUT_DIR = PROJECT_ROOT / "data" / "custom_task"


def normalize_metric(metric: str) -> tuple:
    """
    归一化 metric 到评估器类型

    返回: (evaluator_class, evaluator_import)
    """
    if not metric:
        return "AccEvaluator", "AccEvaluator"

    metric_lower = metric.lower().strip()

    # 精确匹配类
    if any(
        x in metric_lower
        for x in ["em", "acc", "准确率", "f1", "实体", "字段", "execution"]
    ):
        return "AccEvaluator", "AccEvaluator"

    # ROUGE 类 - 使用 JiebaRougeEvaluator 支持中文
    if "rouge" in metric_lower:
        return "JiebaRougeEvaluator", "JiebaRougeEvaluator"

    # AST 类
    if "ast" in metric_lower:
        return "CodeASTEvaluator", "CodeASTEvaluator"

    # Pass@k 类
    if "pass" in metric_lower:
        return "CustomPassAtKEvaluator", "CustomPassAtKEvaluator"

    # 默认
    return "AccEvaluator", "AccEvaluator"


def generate_config_file(task_id: str, task_data: dict) -> str:
    """生成配置文件内容"""

    system_instruction = task_data.get("system_instruction", "").strip()
    metric = task_data.get("metric", "")

    evaluator_class, _ = normalize_metric(metric)

    # 处理有/无 system_instruction 的情况
    has_system_instruction = bool(system_instruction)

    # 根据评估器类型确定导入
    evaluator_imports = {
        "AccEvaluator": "AccEvaluator",
        "JiebaRougeEvaluator": "JiebaRougeEvaluator",
        "CodeASTEvaluator": "CodeASTEvaluator",
        "CustomPassAtKEvaluator": "CustomPassAtKEvaluator",
    }

    evaluator_import = evaluator_imports.get(evaluator_class, "AccEvaluator")

    # 生成模板部分
    if has_system_instruction:
        # 转义三引号，使用多行字符串格式
        escaped_instruction = system_instruction.replace('"""', r'\"\"\"')
        template_section = f'''
# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """{escaped_instruction}"""'''

        infer_template = """dict(
            begin=[
                dict(role='SYSTEM', fallback_role='HUMAN', prompt=SYSTEM_INSTRUCTION),
            ],
            round=[
                dict(role='HUMAN', prompt='{input}'),
                dict(role='BOT', prompt=''),
            ],
        )"""
    else:
        template_section = """
# 该任务无系统提示词，input 自带完整提示"""

        infer_template = """dict(
            round=[
                dict(role='HUMAN', prompt='{input}'),
                dict(role='BOT', prompt=''),
            ],
        )"""

    # 生成配置文件内容
    config_content = f"""from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import {evaluator_import}
from ais_bench.benchmark.datasets.custom import CustomDataset

# {task_id}: 自定义评测任务
# Metric: {metric or "默认 ACC"}
{template_section}

{task_id}_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

{task_id}_infer_cfg = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template={infer_template},
    ),
    retriever=dict(type=ZeroRetriever),
    inferencer=dict(type=GenInferencer),
)

{task_id}_eval_cfg = dict(
    evaluator=dict(type={evaluator_class}),
)

# 导出数据集配置
{task_id}_datasets = [
    dict(
        type=CustomDataset,
        abbr='{task_id}',
        path='data/custom_task/{task_id}.jsonl',
        reader_cfg={task_id}_reader_cfg,
        infer_cfg={task_id}_infer_cfg,
        eval_cfg={task_id}_eval_cfg,
    )
]
"""
    return config_content


def generate_data_file(task_data: dict) -> str:
    """生成数据文件内容（JSONL 格式）"""
    input_text = task_data.get("input", "")
    output_text = task_data.get("output", "")

    data_line = json.dumps(
        {"input": input_text, "output": output_text}, ensure_ascii=False
    )

    return data_line + "\n"


def process_task(task_file: Path) -> dict:
    """处理单个任务文件"""
    with open(task_file, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    task_id = task_data.get("task_id", task_file.stem)

    # 检查是否为空任务
    if (
        not task_data.get("input")
        and not task_data.get("output")
        and not task_data.get("metric")
    ):
        return {
            "task_id": task_id,
            "skipped": True,
            "reason": "空任务（无 input/output/metric）",
        }

    # 生成配置文件
    config_content = generate_config_file(task_id, task_data)
    config_file = CONFIG_OUTPUT_DIR / f"{task_id}_suite.py"

    # 生成数据文件
    data_content = generate_data_file(task_data)
    data_file = DATA_OUTPUT_DIR / f"{task_id}.jsonl"

    # 写入文件
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(config_content)

    with open(data_file, "w", encoding="utf-8") as f:
        f.write(data_content)

    return {
        "task_id": task_id,
        "skipped": False,
        "config_file": str(config_file),
        "data_file": str(data_file),
        "metric": task_data.get("metric", ""),
        "has_system_instruction": bool(task_data.get("system_instruction", "").strip()),
    }


def main():
    """主函数"""
    # 确保输出目录存在
    CONFIG_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 获取所有任务文件
    task_files = sorted(
        TASK_INFO_DIR.glob("task_*.json"),
        key=lambda x: int(re.search(r"\d+", x.stem).group()),
    )

    print(f"找到 {len(task_files)} 个任务文件")
    print(f"配置文件输出目录: {CONFIG_OUTPUT_DIR}")
    print(f"数据文件输出目录: {DATA_OUTPUT_DIR}")
    print("-" * 50)

    results = {"processed": [], "skipped": []}

    for task_file in task_files:
        result = process_task(task_file)

        if result["skipped"]:
            results["skipped"].append(result)
            print(f"⏭️  跳过 {result['task_id']}: {result['reason']}")
        else:
            results["processed"].append(result)
            print(
                f"✅ 生成 {result['task_id']}: metric={result['metric'] or '默认ACC'}, system_instruction={'有' if result['has_system_instruction'] else '无'}"
            )

    print("-" * 50)
    print(
        f"完成: 成功处理 {len(results['processed'])} 个任务, 跳过 {len(results['skipped'])} 个任务"
    )

    # 生成 __init__.py
    init_file = CONFIG_OUTPUT_DIR / "__init__.py"
    if not init_file.exists():
        init_file.touch()
        print(f"✅ 创建 {init_file}")


if __name__ == "__main__":
    main()
