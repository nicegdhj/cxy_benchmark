from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_38: 自定义评测任务
# Metric: EM + 字段级F1

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """请识别并提取用户提供的最长地点或最长地址信息，忽略其他无关内容。只返回提取出的地点或地址，不要解释，不要输出别的任何内容"""

task_38_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_38_infer_cfg = dict(
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

task_38_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_38_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_38',
        path='data/custom_task/task_38.jsonl',
        reader_cfg=task_38_reader_cfg,
        infer_cfg=task_38_infer_cfg,
        eval_cfg=task_38_eval_cfg,
    )
]
