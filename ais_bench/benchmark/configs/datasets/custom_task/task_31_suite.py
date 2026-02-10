from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_31: 自定义评测任务
# Metric: rouge/llm

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """一、信息抽取
# [角色] 请担任一个信息提取专家
# [任务] 根据[用户输入]，请帮我提取关键信息，信息包括产品名称、政企客户级别、带宽要求、客户名称、工单号、计费号。
# [说明]
1、产品名称，抽取产品名称请按如下枚举值输出，不要修改，产品名称枚举：网吧专线套餐（2019版）、集团CMNET专线接入业务套餐2、集团CMNET专线接入业务套餐1、互联网专线套餐、国际快线、BGP专线套餐、企业光宽带包年套餐、悦享专线、悦享专线动态IP版、商务专线、APN专用套餐、新APN专用套餐、短彩信专用专线套餐、跨省互联网专线主办省套餐、视频监控专线套餐、行业视频集团套餐、地区间精品电路、地区间数字电路出租套餐、数字电路出租（跨国）、数字电路出租（跨省）、智能专线、地区内数字电路出租套餐、地区内精品电路、光纤出租套餐、地区内SPN电路出租、地区间SPN电路出租、地区内MPLS VPN套餐、省内MPLS VPN套餐、MPLS VPN专线（跨省）、MPLS VPN专线、有限公司MPLS-VPN（主办省）、国际公司MPLS-VPN（主办省）、MPLS-VPN专线（主办省）、集团WLAN专线套餐、行业WLAN、WLAN星巴克专用套餐
2、政企客户级别，抽取客户等级情感如下枚举值输出，不要修改，政企客户级别枚举：A+客户、A类客户、B类客户、C类客户、D类客户、未定义
3、带宽要求，包含具体带宽数值，如“300M，用于日常办公上网”、“1024M”
4、客户名称，包含具体公司、企业名称，如“嘉兴博云网络科技有限公司”
5、工单号，开头为大写ZJ的字符串，如ZJ-DM-20250425-00014，如果不存在请输出空字符串
6、计费号，如e5513056969，如果不存在请输出空字符串
# [输出要求]
结果请以json格式输出，格式如下：
```json
{
    "产品名称": "",
    "政企客户级别": "",
    "带宽要求": "",
    "客户名称": "",
    "工单号": "",
    "计费号": "",
}
# [用户输入]
{{input}}

二、方案内容生成
1.1 产品定义
互联网专线是指依托国内骨干网及宽带城域网资源，提供多种专线接入方式，满足集团客户接入Internet互联网络、开展各种应用的业务。
中国移动当前互联网专线主要分为：PON接入专线、PTN接入专线两类。
互联网专线按业务应用场景可分为标准互联网专线、视频专线、网吧专线和国际快线。
1.2 目标客户
适用于所有有接入互联网需求的集团客户；已使用竞争对手互联网专线产品的集团客户。
互联网专线为集团客户提供各种速率的专用链路，直接连接中国移动CMNet网络，实现方便快捷的高速互联网上网服务。互联网专线除提供基本高速上网功能外，还可承载多种新型互联网综合应用，如多媒体信息查询、IP电话、视频会议、网上银行、电子商务等。
1.3 产品优势
中国移动互联网专线的产品特点如下：
1. 带宽灵活选择：客户可以根据实际需要，以端口独享或共享方式在10M－10G甚至更高的带宽间进行自由选择。
2. 网络覆盖广，接入方便：客户接入地点无限制。
3. 高质量的电信级服务：以新一代宽带IP技术为核心的电信级网络为基础，网络容量大、安全性能高、业务功能强，提供电信级QoS保障和SLA服务标准。
产品优势
1. 覆盖范围广，有基站的地方就有光网络。
2. 安全等级高，和中国移动自有网络具有同等级别的网络安全等级。
3. 全网轻载，当前承载网负荷仅有20-30%。
4. 没有老旧基础资源包袱，中国移动现网部署均为光缆网络，不存在双绞线等铜线资源。双绞线等铜线传输受限于距离（一般不超过1km），速率（一般不超过100M），并且上下行速率不对称，其他固网运营商都在进行“光进铜退”的改造。

请根据上述提供信息，生成一段方案目标，内容包括：
- 提供稳定、安全、高速的移动互联网专线接入服务
- 满足客户业务对带宽、时延、可靠性的要求
请直接生成内容，不需要解释说明，不要采用md格式，字数300字以内。"""

task_31_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_31_infer_cfg = dict(
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

task_31_eval_cfg = dict(
    evaluator=dict(type=JiebaRougeEvaluator),
)

# 导出数据集配置
task_31_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_31',
        path='data/custom_task/task_31.jsonl',
        reader_cfg=task_31_reader_cfg,
        infer_cfg=task_31_infer_cfg,
        eval_cfg=task_31_eval_cfg,
    )
]
