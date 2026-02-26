from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_62: 自定义评测任务
# Metric: EM + 字段级F1

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """# [角色] 你是一个信息抽取助手
# [任务] 请对用户的[投诉内容]进行分析，抽取故障现象、检测结果、派单建议等信息。
# [输出要求]
结果请使用JSON格式，若[投诉内容]不含这些内容，json中对应的字段返回为"None"。
```json
{
  "故障现象": ...,
  "检测结果": ...,
  "处理建议": ...,
  "派单建议": ...
}
```"""

task_62_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_62_infer_cfg = dict(
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

task_62_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_62_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_62',
        path='data/custom_task/task_62.jsonl',
        reader_cfg=task_62_reader_cfg,
        infer_cfg=task_62_infer_cfg,
        eval_cfg=task_62_eval_cfg,
    )
]
