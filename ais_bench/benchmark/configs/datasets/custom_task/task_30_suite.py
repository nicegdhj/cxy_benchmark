from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_30: 自定义评测任务
# Metric: rouge/llm

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """一、信息抽取
# [角色] 请担任一个语义理解专家
# [要求] 从[用户输入]中分析提取关键信息，包括背景、痛点描述、客户等级等信息
# [说明]
背景：[用户输入]描述需求的背景情况，如果不存在请输出空字符串
痛点描述：[用户输入]描述需求的痛点问题，如果不存在请输出空字符串
客户等级：[用户输入]中抽取客户等级，如下枚举值输出：A+客户、A类客户、B类客户、C类客户、D类客户、未定义，如果不存在请输出空字符串
# [输出格式] 结果请以json格式输出，格式如下：
```json
{
    "背景": "...",
    "痛点描述": "...",
    "客户等级": "A+客户"
}
```
[用户输入]
客户名称：{{customer}}
{{input}}

二、方案内容生成部分
# [参考内容]
## 高并发业务架构上云解决方案
在数字化浪潮中，互联网应用的用户规模与业务复杂度呈爆发式增长，高并发场景已成为众多企业面临的常态挑战。以电商行业为例，“双十一”“618” 等大型促销活动期间，瞬间涌入的海量用户请求，对系统的处理能力构成严峻考验。从社交平台到在线游戏，从金融交易到在线教育，各类应用在高并发时段均需保障系统稳定运行与用户体验流畅。
## 智算业务上云解决方案
算力中心有多种，可分为数据中心、高性能计算中心(即超算中心)、智算中心等，它们都以云的形式提供服务。从智算中心的定位和内涵来看，它是一种新型算力公共设施平台，实现了算力、算法和数据的高效融合，更加适合的当前的人工智能时代。
移动云以一体化为原则，构建技术领先、绿色节能的智算中心，让全域智能算力服务触手可及。依托算网大脑，实现跨地域、跨层级、跨主体的智能一体化调度，协同智算集群产品、震泽智算平台、模型服务平台完成“资源+平台+模型”的高效一体化运营，为人工智能发展注入新动力。
## 迁移通用解决方案
XXX公司当前信息化系统部署在本地，由于设备老旧、性能不足、业务发展等客观因素，需要将业务系统迁移至公有云平台。
XXX客户不满足当下云服务商，或者需要满足多云战略时，需要将一个云厂商的部分资源或全部资源迁移其他公有云平台。
## 移动云云电脑专线解决方案
中国移动云专线通过强大的网络布局和广泛的链路资源，为用户本地数据中心与移动云VPC虚拟私有云之间提供安全、可靠、稳定、高速的连接服务，云专线的启用便捷无比，而且网络服务稳定且优质。
# [用户输入]
客户名称：{{customer}}
{{input}}
# [要求]
请根据[参考内容]中的解决方案项目概述，结合[用户输入]生成一段项目概述，请直接生成内容，不需要解释说明，不要采用md格式，字数160字以内。}"""

task_30_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_30_infer_cfg = dict(
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

task_30_eval_cfg = dict(
    evaluator=dict(type=JiebaRougeEvaluator),
)

# 导出数据集配置
task_30_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_30',
        path='data/custom_task/task_30.jsonl',
        reader_cfg=task_30_reader_cfg,
        infer_cfg=task_30_infer_cfg,
        eval_cfg=task_30_eval_cfg,
    )
]
