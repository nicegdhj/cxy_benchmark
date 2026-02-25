from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_42: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """任务要求
你需要识别提取接下来的问题中的时间信息，以JSON字典的形式返回。

## 注意事项
返回结果只返回一个json字典，不需要其他分析内容。

## 返回要求
返回字段为2个：
`vague 时间信息是否明确
`time 时间信息

## 返回字段说明
`vague 
    主要是判断提取到的时间是否明确，如\"近期\"，\"最近\"是不明确的；\"今天\"，\"昨天\"，\"2025年05月28号\"是明确的。
    返回\"是\"或\"否\"，如果没有提取到时间信息，则返回\"无\"
`time
    返回问题中的原始时间信息，不需要进行处理转换。


## 输入输出示例：
输入 - \"查询昨天5g设备序列号为2102311CUW9WG4001125的关联小区列表\"
{{\"vague\": \"是\", \"time\": \"昨天\"}}

## 问题
{}\\ """

task_42_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_42_infer_cfg = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template=dict(
            begin=[
                dict(role="SYSTEM", fallback_role="HUMAN", prompt=SYSTEM_INSTRUCTION),
            ],
            round=[
                dict(role='HUMAN', prompt='{input}'),
                dict(role='BOT', prompt=''),
            ],
        ),
    ),
    retriever=dict(type=ZeroRetriever),
    inferencer=dict(type=GenInferencer),
)

task_42_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_42_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_42',
        path='data/custom_task/task_42.jsonl',
        reader_cfg=task_42_reader_cfg,
        infer_cfg=task_42_infer_cfg,
        eval_cfg=task_42_eval_cfg,
    )
]
