from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_61: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """# [角色]：请担任一个投诉类别分析专家
# [任务] 根据输入的[投诉内容]进行分类判断，输出类别名称和判断依据，共12个类别，分别为：投诉处理、要求抓包实时跟踪/分析、语音投诉处理、查询原始话单、核实APN配置情况、核实公网NAT地址、核实特定地址无法访问原因、核实白名单未生效原因、核实覆盖频段、核实访问记录/日志、要求派人到现场测速/测试、短信投诉处理。
# [类别说明] 
1、投诉处理：用户反映安装地点4G信号弱或无信号，信号时好时坏，不稳定，强度差，多家运营商信号均不佳；无法访问应用系统、无法连接定向网络、监控画面无法加载，虽然描述了特定应用/系统无法访问但是未提供地址；反映无法上网、频繁离线及网络卡顿问题，尽管信号正常，但仍出现数据传输失败、设备无法注册联网等现象；反映网速慢、视频卡顿，下载速度慢，高延迟，需查当地设备负荷情况。
2、核实特定地址无法访问原因：无法访问多个白名单地址、IP地址段及定向域名，涉及多种网络资源，具体原因待查，需要包含具体的IP/URL。
3、语音投诉处理：白名单号码无法拨打物联卡及手表，部分特定号码无法接通。物联卡与白名单号码互拨失败，主被叫均无法接通，提示服务器错误或直接挂断。
4、查询原始话单：用户提及原始话单、话单文件描述，需查询原始话单以确认NB流量产生的原因，并反馈东区、北区话单存在上传问题。
5、核实APN配置情况：核实APN配置，重点排查PGW侧业务配置及PAP、CHAP信息，需申请大区协助对端配置检查。
6、核实公网NAT地址：核实公网NAT地址，需获取公网卡动态IP地址段及NAT后的公网IP地址详情。
7、要求抓包实时跟踪/分析：需实时抓包跟踪与分析，包括故障复现、服务器拦截核实、平台数据传输及访问路由排查，要求多方配合24小时持续抓包。
8、核实白名单未生效原因：白名单已添加但仍无法访问指定域名，多个设备显示升级下载失败，网络故障未解决。
9、核实覆盖频段：要求核实浙江台州市域S1线全线路基站频段，查询2G基站退网情况，核查现场网络频段不支持的原因。
10、核实访问记录/日志：仅要求查询用户面单据属于历史访问记录查询，核实访问记录场景下，主要需求为核查特定时间段内用户访问的IP、域名及流量使用情况，以确认流量消耗异常的原因。
11、要求派人到现场测速/测试：提到要求现场测试、要求上门、核实当前区域信号等描述。
12、短信投诉处理：无法收/发短信，短信上/下行失败，终端向平台发送短信失败、终端未触发上行短信、终端不回复平台短信、平台向终端下发短信失败、短信收/发存在延迟等问题
优先级：要求派人到现场测速/测试>投诉处理>核实特定地址无法访问原因>语音投诉处理>短信投诉处理>要求抓包实时跟踪/分析
# [输出要求] 请按json格式输出结果，格式如下：
```json
{
    "result": "类别名称",
    "basis": "判断依据"
}"""

task_61_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_61_infer_cfg = dict(
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

task_61_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_61_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_61',
        path='data/custom_task/task_61.jsonl',
        reader_cfg=task_61_reader_cfg,
        infer_cfg=task_61_infer_cfg,
        eval_cfg=task_61_eval_cfg,
    )
]
