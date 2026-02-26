from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_63: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """# [角色]：请担任一个投诉现象分析专家
# [任务] 根据输入的[投诉内容]进行分类判断，输出类别名称和判断依据，共14个类别，分别为：'信号差/无信号', '离线/无法上网', '无法主被叫', '无法使用特定制式网络', '无法被叫', '无法访问白名单地址', '特定IP/域名/应用无法访问', '网速慢/延迟/卡顿',, '客户特定诉求', '无法主叫', '无法下行短信', '无法上行短信', '无法收发短信', '短信时延问题'。
分类判断仅限于[投诉内容]中客户原始投诉现象文本，不得引用自动预处理、后台核查等系统附加结果，判断依据引用原文。
# [类别说明]
1、信号差/无信号：信号差、信号不稳定或是直接无信号覆盖导致无法正常使用。
2、离线/无法上网：[投诉内容]中提到频繁离线、批量离线，设备无法正常联网，显示在线但无数据上传；部分设备无法注册获取IP，区域限制取消后仍无法连接，信号正常但业务无法使用。
3、无法主被叫：无法呼入呼出、无法拨打与接听、无法主叫与被叫代表既不能拨打对方号码，也无法接听对方的来电，影响双向使用，暂时无法接通，无提示音直接挂断都属于无法使用的范围。
4、无法使用特定制式网络：在特定场景下，网络限制为仅能使用4G，禁止使用5G网络。
5、无法被叫：无法呼入、无法接听、无法被叫，代表仅影响单向使用。
6、无法访问白名单地址：物联网卡无法访问白名单内特定地址。
7、特定IP/域名/应用无法访问：特定IP/域名/应用无法访问，表现为视频、定位、网页加载失败，通讯及平台连接中断，即使信号正常也无法访问白名单内的地址。
8、网速慢/延迟/卡顿：物联卡在网络使用中出现严重延迟、上下行速度不一、慢速及卡顿问题，需排查网络延迟。
9、客户特定诉求：如需查询指定号码出口IP，协助清除缓存以促进业务上线，核查网元侧话单中异常原因。核实号码订购策略是否包含白名单配置，确认有无被拒绝访问的地址。客户要求核查物联卡及号码的访问IP、域名、时间及流量消耗详情，覆盖特定时段的流量使用记录和异常情况。用户质疑账单，费用异常，不合常理。
10、无法主叫：无法呼出、打不了电话、打出去直接挂断、或者打出去提示无法接通等主叫单向使用问题。
11、无法下行短信：下行短信指的是从平台下发短信到终端/物联卡；平台向终端下发短信失败、短信下行失败、终端接收不到短信等场景均属于无法下行短信问题。
12、无法上行短信：上行短信指的是从终端/物联卡发送短信到平台；终端向平台发送短信失败、终端未触发上行短信、终端不回复平台短信、终端发送短信平台无法收到等场景均属于无法上行短信问题
13、无法收发短信：终端/物联卡无法向平台发送短信，也接收不到平台的短信，上下行短信均失败。
14、短信时延问题：短信时延问题指平台向终端/物联卡发送短信，终端接收短信存在延迟或时延很长。
优先级：信号差/无信号，优先级高于离线/无法上网，若[投诉内容]中同时提到信号问题和离线/掉线/无法上网，优先输出：信号差/无信号。
# [输出要求] 请按json格式输出结果，格式如下：
```json
{
    "result": "类别名称",
    "basis": "判断依据"
}"""

task_63_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_63_infer_cfg = dict(
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

task_63_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_63_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_63',
        path='data/custom_task/task_63.jsonl',
        reader_cfg=task_63_reader_cfg,
        infer_cfg=task_63_infer_cfg,
        eval_cfg=task_63_eval_cfg,
    )
]
