from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_47: 自定义评测任务
# Metric: ROUGE

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """根据提供的信息给我告警描述、处理建议。
你是一位告警处理专家，会严格按照提供的告警相关知识，输出完整内容，并将结果整理成JSON格式的str，具体格式为
```json
{
  "alarm_desc": 告警描述
  "possible_cause": 可能原因
  "service_impact_conclusion": 系统影响
  "handling_measures": 处理建议
}
```

请不要返回think对应内容，只返回json内容，所有字段值必须为字符串，禁止返回数组或对象

提示词-用户提示词：
告警处理专家你好，现在有一个告警信息，需要请你对其进行处理，并整理成结构化JSON对象，并输出最终结果。
告警信息：{{alarmname}}
告警相关知识：{{input}}"""

task_47_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_47_infer_cfg = dict(
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

task_47_eval_cfg = dict(
    evaluator=dict(type=JiebaRougeEvaluator),
)

# 导出数据集配置
task_47_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_47',
        path='data/custom_task/task_47.jsonl',
        reader_cfg=task_47_reader_cfg,
        infer_cfg=task_47_infer_cfg,
        eval_cfg=task_47_eval_cfg,
    )
]
