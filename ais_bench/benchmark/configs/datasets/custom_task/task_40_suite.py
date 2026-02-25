from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_40: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """## 任务要求
你是一个无线通信网络专家,可以根据已知类别相关内容，首先提取句子主干，再根据主干内容识别所属问题类别是查询无线通信网络的配置，还是性能信息或是其他，以JSON字典的形式返回。

## 已知类别相关内容
性能：
5G私有性能统计-RRU级(天),LTE基础性能统计_小区(流量自忙时),LTE基础性能统计_小区(天),LTE私有性能统计_RRU(天),NRCUDU性能统计表-小区(天),NRCUDU性能统计-小区(流量自忙时),4G劣于竞对,4G室分RRU级业务异常,5G劣于竞对,5G室分RRU级业务异常,5G室分双流异常,LTE室内用户占用室外信号问题楼宇,SEQ异常,楼宇常驻用户质差,5G常驻用户5-4回落小区指标_小区(天),5G常驻用户频繁占用4G小区指标_小区(天),5G网络MRO指标表-小区(天),5G驻留比小区详单(天)表,LTE的运营商MRO竞对指标(小区\/天),LTE高干扰小区清单(天级),LTE网络MRO数据-小区(天),LTE网络MRO指标统计-RRU(天),NR的整体MRO竞对指标_小区(天),SEQ_ATTACH室分小区数据_小区(小时),SEQ_VOLTE基础性能_小区(天),SEQ_VONR_5G语音感知指标_小区(天),SEQ_异常信令定位局部弱覆盖_小区(天),浙江创新院-华为5G私有性能指标_RRU(小时),浙江创新院-中兴5G私有性能指标_RRU(小时)
配置：
5G资源大表,LTE资源大表,RRU-5G,LTE_RRU硬件信息,LTE到LTE邻区配置表,LTE小区配置表,NR_AAU硬件信息,RRU-4G
其他：
工单查询库全量导出,天面物理站,主设备告警,ATTACH异常,白名单导出,低驻留,室分天线监测,室分投诉,图纸清单,5G驻留比基站-天,AAU,疑难故障申报

## 注意事项
返回结果只返回一个json字典，不需要其他分析内容。

## 返回要求
返回1个字段
`types 类别

## 返回字段说明
`types 
    只有有限的3类：\"性能\"，\"配置\"，\"其他\"


## 输出示例：
- {{\"types\": \"性能\"}}

## 问题
{}\\ """

task_40_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_40_infer_cfg = dict(
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

task_40_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_40_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_40',
        path='data/custom_task/task_40.jsonl',
        reader_cfg=task_40_reader_cfg,
        infer_cfg=task_40_infer_cfg,
        eval_cfg=task_40_eval_cfg,
    )
]
