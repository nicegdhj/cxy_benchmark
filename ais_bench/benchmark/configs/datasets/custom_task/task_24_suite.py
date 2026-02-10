from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_24: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """## 任务目标
你是一个意图识别助手，可以精准的识别用户问题属于以下哪一种场景，请直接匹配场景编号。
## 场景描述
0、工单入参查询
功能描述：
查询工单的编号和相关参数。
具体包括：通过地市、时间、状态查询具体有哪些工单。
###请注意：工单入参查询[一定不会]指出明确的参数，参数通常由字母和数字组成，例如CIOT29C13C40。
###请注意：用户问题中包含“工单”且不包含“参数”时，可判定为“工单入参查询”场景。
样例问题：
台州市路桥区进行中的售中工单有哪些？
杭州市西湖区8月28日报结的投诉工单有哪些？

1、数据自服务
功能描述：
通过明确的查询参数，获取指定类型的用户数据。
具体包括：已认证ONU数据、未认证ONU数据、分光器数据、网元数据、客户数据、工单数据6类用户数据的具体信息。
###请注意：只有描述的这6类数据属于数据自服务场景。
###请注意：数据自服务查询[会]指出明确的参数，参数通常由字母和数字组成，例如CIOT29C13C40。
样例问题：
未认证ONU的相关数据，SN是CIOT29C13C40。
请看一下客户的相关数据，专线编号是CMNET-9457880。
请看一下工单数据，工单编号为ZJ-GOV-004-20250528-01023。


2、对话机器人，回复用户问题并提示用户 当前支持的功能



##格式要求
直接输出场景的纯数字编号0-2。
###请再检查一下数字与场景名称的对应关系：
0 入参查询
1 数据自服务
2 对话机器人

###请注意：再次区分一下“数据自服务的工单数据查询”与“工单入参查询”：
“数据自服务的工单数据查询”包含入参
“工单入参查询”不包含入参

用户问题为{{input}}"""

task_24_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_24_infer_cfg = dict(
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

task_24_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_24_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_24',
        path='data/custom_task/task_24.jsonl',
        reader_cfg=task_24_reader_cfg,
        infer_cfg=task_24_infer_cfg,
        eval_cfg=task_24_eval_cfg,
    )
]
