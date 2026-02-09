from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_32: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '你是一个问题识别助手，你可以精准识别用户问题属于以下场景的哪一种。\n\n## 任务目标\n请你根据用户的问题，精准的识别属于以下场景的哪一种，并以纯数字格式返回。用户的问题可能是场景描述的直接表达，也可能是相似的语义表达需要理解。请直接回答场景的编号。\n\n## 各类场景描述\n0、工单数据查询（例如：台州市路桥区进行中的售中工单有哪些？）\n1、宽带无法使用；宽带中断；宽带不稳定；互联网客户反应网速慢；上网专线中断；上网专线无法使用；上网专线卡顿；上网专线丢包。\n2、传输专线中断；传输专线无法使用；专线电路中断。\n3、电路质量不稳定；电路卡顿；电路丢包。\n4、悦享专线上网不稳定；悦享专线上网卡顿。\n5、电路无法透传多个VLAN。\n6、PON专线的ONU注册失败。\n7、语音固话号码提示尚未登录。\n8、语音固话号码提示空号。\n9、部分电话无法呼出，呼叫听到“嘟嘟嘟”的挂断音。\n10、所有号码无法呼出，呼叫听到“嘟嘟嘟”的挂断音。\n11、语音业务正常，但短号来显不正常。\n12、特殊号段无法外呼。\n13、无法访问特定网站。\n14、视频监控无法看到画面。\n15、其他。\n\n## 格式要求\n以纯数字的格式返回\n\n数字为1-15，代表你的识别结果。\n\n用户问题为{{input}}'

task_32_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_32_infer_cfg = dict(
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

task_32_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_32_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_32',
        path='data/custom_task/task_32.jsonl',
        reader_cfg=task_32_reader_cfg,
        infer_cfg=task_32_infer_cfg,
        eval_cfg=task_32_eval_cfg,
    )
]
