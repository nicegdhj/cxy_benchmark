from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_65: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

task_65_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_65_infer_cfg = dict(
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

task_65_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_65_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_65',
        path='data/custom_task/task_65.jsonl',
        reader_cfg=task_65_reader_cfg,
        infer_cfg=task_65_infer_cfg,
        eval_cfg=task_65_eval_cfg,
    )
]
