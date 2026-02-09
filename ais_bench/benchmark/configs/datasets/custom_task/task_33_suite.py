from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_33: 自定义评测任务
# Metric: Acc

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '你是一个参数提取助手，你可以精准识别用户问题中的参数。\n\n## 任务目标\n请从用户问题中提取SN号\nSN号格式通常为字母加数字组合\n注意，SN号必须为明确的“SN号”描述，其他相似表达均不是SN号\n\n## 格式要求\n输出只需要提取后的SN号，不需要额外的文字解释；\n如果用户问题中不存在SN号，直接返回”null“。\n\n用户问题为{{input}}'

task_33_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_33_infer_cfg = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template=dict(
            begin=[
                dict(role='SYSTEM', fallback_role='HUMAN', prompt=SYSTEM_INSTRUCTION),
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

task_33_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_33_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_33',
        path='data/custom_task/task_33.jsonl',
        reader_cfg=task_33_reader_cfg,
        infer_cfg=task_33_infer_cfg,
        eval_cfg=task_33_eval_cfg,
    )
]
