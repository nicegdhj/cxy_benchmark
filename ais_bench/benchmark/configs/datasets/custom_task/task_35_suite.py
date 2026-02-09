from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import RougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_35: 自定义评测任务
# Metric: ROUGE

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = "你是一个智能问答助手。\n    以下已知信息：\n      {{info}}}\n    以下是用户问题：\n      {{input}}}\n    （1）若用户问题与已知信息中的问题相似度较高，则直接根据已知信息的答案进行原文输出；（2）若已知信息和用户提问并不相关，则在回答中直接输出'没有相关信息'；（3）提供简洁、准确的回答与分析;（4）最后选取用户提问最相关的已知信息中filename字段列出参考文献。"

task_35_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_35_infer_cfg = dict(
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

task_35_eval_cfg = dict(
    evaluator=dict(type=RougeEvaluator),
)

# 导出数据集配置
task_35_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_35',
        path='data/custom_task/task_35.jsonl',
        reader_cfg=task_35_reader_cfg,
        infer_cfg=task_35_infer_cfg,
        eval_cfg=task_35_eval_cfg,
    )
]
