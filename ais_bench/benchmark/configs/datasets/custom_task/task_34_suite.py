from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_34: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '## 任务目标\n你是一个意图识别助手，可以精准的识别用户问题属于以下哪一种场景，请直接匹配场景编号。\n## 场景描述\n0、工单入参查询\n功能描述：\n查询工单的编号和相关参数。\n具体包括：通过地市、时间、状态查询具体有哪些工单。\n###请注意：工单入参查询[一定不会]指出明确的参数，参数通常由字母和数字组成，例如CIOT29C13C40。\n###请注意：用户问题中包含“工单”且不包含“参数”时，可判定为“工单入参查询”场景。\n样例问题：\n台州市路桥区进行中的售中工单有哪些？\n杭州市西湖区8月28日报结的投诉工单有哪些？\n\n1、智能设计\n功能描述：\n实现点位“方案生成”，自动规划多个路径方案；\n确认采纳1个接入方案。\n请注意：问题中会明确直接的出现“方案生成”的意图。\n样例问题：\n给杭州市滨江区经纬度为（120.1835，30.2048）的点位拉一条数字电路专线，接入资源为光交，生成方案。\n嘉兴科技有限公司需要开通悦享专线，带宽300M，用于日常办公，政企客户级别为B类客户，请生成一个方案。\n采纳方案1。\n\n2、数据自服务\n功能描述：\n通过明确的查询参数，获取指定类型的用户数据。\n具体包括：已认证ONU数据、未认证ONU数据、分光器数据、网元数据、客户数据、工单数据6类用户数据的具体信息。\n###请注意：只有描述的这6类数据属于数据自服务场景。\n###请注意：数据自服务查询[会]指出明确的参数，参数通常由字母和数字组成，例如CIOT29C13C40。\n样例问题：\n请看一下未认证ONU的相关数据，SN是CIOT29C13C40。\n请看一下客户的相关数据，专线编号是CMNET-9457880。\n请看一下工单数据，工单编号为ZJ-GOV-004-20250528-01023。\n\n3、智能排障\n功能描述：\n排查用户故障问题。\n具体包括宽带不稳定，互联网客户反映网速慢，专线中断，电路卡顿、丢包，悦享专线上网不稳定卡顿，无法透传多个VLAN，PON专线的ONU注册失败，语音固话提示未登录或空号，部分电话无法呼出，所有号码无法呼出，短号来显不正常，特殊号段无法呼出，无法访问特定网站，视频监控无画面等15类故障。\n###请注意：其余的故障描述，不在上述15类数据中，就算与故障相关，也不属于该场景。\n样例问题：\n当前宽带无法上网，请查看计费号为e5539632365的情况。\n部分电话无法呼出，呼叫听到“嘟嘟嘟”的挂断音，无法打电话，请查看一下。\n\n4、智能问答\n功能描述：\n提供基于专业知识的智能解答。\n不属于智能设计、数据自服务、智能排障的问题，都归为智能问答场景。\n样例问题：\n政企AAA专线组网标准是什么？\n室外光缆施工规范有哪些要求？\n\n##格式要求\n直接输出场景的纯数字编号0-4。\n###请再检查一下数字与场景名称的对应关系：\n0 工单入参查询\n1 智能设计\n2 数据自服务\n3 智能排障\n4 智能问答\n\n###请注意：再次区分一下“数据自服务的工单数据查询”与“工单入参查询”：\n“数据自服务的工单数据查询”包含入参\n“工单入参查询”不包含入参\n\n用户问题为{{input}}'

task_34_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_34_infer_cfg = dict(
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

task_34_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_34_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_34',
        path='data/custom_task/task_34.jsonl',
        reader_cfg=task_34_reader_cfg,
        infer_cfg=task_34_infer_cfg,
        eval_cfg=task_34_eval_cfg,
    )
]
