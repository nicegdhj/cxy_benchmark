from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_59: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """# [角色]：请担任一个服务隐患分析专家
# [任务] 根据输入的[投诉内容]判断是否存在服务隐患。
当[投诉内容]中提到：投诉升级、工信部投诉、12345投诉、换运营商、紧急投诉、重大故障、重大舆情等，属于存在服务隐患。
若存在，则输出“是”，并输出判断依据，判断依据请使用[投诉内容]的原文；若不存在则输出“否”，可以不输出判断依据。
# [说明]
换运营商：客户提到由于故障不再使用移动的物联卡等。
投诉升级：[投诉内容]只有明确提及升级的是投诉的，才属于投诉升级；其他设备、网络升级、关联集团工单，都不属于投诉升级。
紧急投诉：客户提出的紧急不属于紧急投诉。
# [输出要求] 请按json格式输出结果，格式如下：
```json
{
    "result": "是/否",
    "basis": "判断依据"
}
```"""

task_59_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_59_infer_cfg = dict(
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

task_59_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_59_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_59',
        path='data/custom_task/task_59.jsonl',
        reader_cfg=task_59_reader_cfg,
        infer_cfg=task_59_infer_cfg,
        eval_cfg=task_59_eval_cfg,
    )
]
