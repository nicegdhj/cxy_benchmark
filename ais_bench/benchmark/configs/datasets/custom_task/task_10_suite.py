from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import RougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_10: 自定义评测任务
# Metric: ROUGE

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '你是一个家宽装维专业人员，需要根据用户问题和数据库中检索出来的结果进行回答。注意如下要点：\n\n用户问题：\n{question}\n检索结果：\n{retrieve_result}\n注意事项：\n{notes}'

task_10_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_10_infer_cfg = dict(
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

task_10_eval_cfg = dict(
    evaluator=dict(type=RougeEvaluator),
)

# 导出数据集配置
task_10_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_10',
        path='data/custom_task/task_10.jsonl',
        reader_cfg=task_10_reader_cfg,
        infer_cfg=task_10_infer_cfg,
        eval_cfg=task_10_eval_cfg,
    )
]
