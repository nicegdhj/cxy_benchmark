from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_84: 自定义评测任务
# Metric: 默认 ACC

# 该任务无系统提示词，input 自带完整提示

task_84_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_84_infer_cfg = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template=dict(
            round=[
                dict(role='HUMAN', prompt='{input}'),
                dict(role='BOT', prompt=''),
            ],
        ),
    ),
    retriever=dict(type=ZeroRetriever),
    inferencer=dict(type=GenInferencer),
)

task_84_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_84_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_84',
        path='data/custom_task/task_84.jsonl',
        reader_cfg=task_84_reader_cfg,
        infer_cfg=task_84_infer_cfg,
        eval_cfg=task_84_eval_cfg,
    )
]
