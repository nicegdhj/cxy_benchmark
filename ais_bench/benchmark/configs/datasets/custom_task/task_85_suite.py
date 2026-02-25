from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_85: 自定义评测任务
# Metric: ROUGE

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """你的任务是根据用户的问题和召回的数据，进行总结润色回复，要参考回答样例中的回答进行回答(不要输出用户的问题和“回答”字样)。并且注意如果可能，回答要提到数据对应的时间

###
回答要求：
1.请结合回答样例里面回答模板和根据用户问题进行回答
2.严格以markdown格式输出
3.如果用户问的指标是一个时间范围，请不要直接分析召回的数据，先按时间维度回答出数据后再分析，如果用户问题里不包含一个时间范围，请回答召回数据里面时间最新的那一条数据
"""

task_85_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_85_infer_cfg = dict(
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
