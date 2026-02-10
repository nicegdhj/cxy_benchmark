from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_85: 自定义评测任务
# Metric: ROUGE

# 该任务无系统提示词，input 自带完整提示

task_85_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_85_infer_cfg = dict(
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

task_85_eval_cfg = dict(
    evaluator=dict(type=JiebaRougeEvaluator),
)

# 导出数据集配置
task_85_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_85',
        path='data/custom_task/task_85.jsonl',
        reader_cfg=task_85_reader_cfg,
        infer_cfg=task_85_infer_cfg,
        eval_cfg=task_85_eval_cfg,
    )
]
