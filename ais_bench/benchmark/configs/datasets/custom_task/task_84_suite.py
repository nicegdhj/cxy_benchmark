from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_84: 自定义评测任务
# Metric: 默认 ACC

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """你是一个ORACLE数据库SQL专家，你需要基于数据库中表字段描述、用户问题中的实体信息和用户问题中的实体信息，生成ORACLE数据库的查询SQL语句。
# 数据库中表字段描述

字段描述

表_网络受损_无线退服_区域_5分钟粒度\tv_t_nd_ww_area_5m

| 字段名               | 数据类型 | 描述                                                         | 示例           |
| -------------------- | -------- | ------------------------------------------------------------ | -------------- |
| STAT_DATE            | DATE     | 时间，粒度为5分钟                                                        | 2025/4/15 0:05 |
| AREA_TYPE_CODE       | VARCHAR2 | 区域类型编码                                                 | 999            |
| AREA_TYPE_NAME       | VARCHAR2 | 区域类型名称，该字段为省或城市名称                           | 浙江           |
| AREA_CODE            | VARCHAR2 | 区域编码                                                     | 20             |
| AREA_NAME            | VARCHAR2 | 区域名称，当AREA_TYPE_NAME为'浙江'时，该字段为'浙江'或市名，用以查询全省情况或市的情况，其余为AREA_TYPE_NAME市下的区 | 萧山           |
| LSR_2G               | NUMBER   | 2G逻辑站退服数                                               |                |
| LSR_4G               | NUMBER   | 4G逻辑站退服数                                               |                |
| LSR_5G               | NUMBER   | 5G逻辑站退服数                                               |                |
| LSR_TOTAL            | NUMBER   | 2G/4G/5G逻辑站退服总数                                       |                |
| LSR_RATE             | NUMBER   | 逻辑站退服比例                                               |                |
| PSW                  | NUMBER   | 物理站退服数                                                 |                |
| RFW_NUM_TRANSMISSION | NUMBER   | 退服原因数量-传输                                            |                |
| RFW_NUM_WIRELESS     | NUMBER   | 退服原因数量-无线                                            |                |
| RFW_NUM_POWER        | NUMBER   | 退服原因数量-动力                                            |                |
| RFW_NUM_OTHER        | NUMBER   | 退服原因数量-其他                                            |                |
| RFW_P_TRANSMISSION   | NUMBER   | 退服原因占比-传输                                            |                |
| RFW_P_WIRELESS       | NUMBER   | 退服原因占比-无线                                            |                |
| RFW_P_POWER          | NUMBER   | 退服原因占比-动力                                            |                |
| RFW_P_OTHER          | NUMBER   | 退服原因占比-其他                                            |                |
| PD_NUM_MOBILE        | NUMBER   | 产权分布数量-中国移动                                        |                |
| PD_NUM_TOWER         | NUMBER   | 产权分布数量-中国铁塔                                        |                |
| RSW                  | NUMBER   | 重保站点退服数                                               |                |
| BSW_SUPPER           | NUMBER   | 超级基站退服数                                               |                |
| BSW_UBS              | NUMBER   | 超60分钟未恢复基站数量                                       |                |
| COVERAGE_SCENE       | VARCHAR2 | 覆盖场景  0 默认值     1 党政军机关     2 党政军宿舍     3 武警军区     25 医院 |                |
| PSW_PF               | NUMBER   | 停电物理站数                                                 |                |
| PSW_WI               | NUMBER   | 水浸物理站数                                                 |                |
| FTMPS                | NUMBER   | 天面物理站退服                                               |                |



# 要求
1. 要求输出的格式如下：{\"sql_list\": [\"select * from t_edi_oes_area_5m;\",\"select * from t_edi_oes_area_15m;\"]}
2. 时间格式请参考数据库中表字段描述。当前时间是:2025-12-29 14:24。注意使用TO_DATE将字符串类型的时间转换为时间类型。
3. 你需要仔细观察数据库中表字段描述中，日期相关字段的格式，使得生成的SQL可以准确地利用日期做过滤,如果数据表中有STAT_DATE和AREA_NAME两个字段，sql要呈现出STAT_DATE和AREA_NAME信息以及指标信息,生成的sql需要把每个字段的中文含义用AS表示出来,同时AS后面的名称必须使用双引号包围,不要使用单引号。
4. 要根据提供的开始日期和结束日期，查询指定时间范围的数据
5. SELECT区域AS前面的字段名和WHERE区域的字段名不要用引号包围
6. 不要把中文名当做字段名!不要把中文名当做字段名!不要把中文名当做字段名!
7. 请严格参考数据库中表字段描述，查询的字段名要直接来自数据库中表字段描述，不能杜撰字段名，如果数据表结构中不存在地区或时间字段即使条件中有时间地点信息也不要在SQL的where区域出现这些字段。
8. sql里面不要有排序，去重，求和，平均这种函数，所有的查询字段都可以直接从数据库中表字段描述得到
9. 如果数据表里面有AREA_NAME和AREA_TYPE_NAME都和地点相关，需要注意地点填在AREA_NAME里面,如果数据库中表字段描述里面没有STAT_DATE和AREA_NAME两个字段一定不要在SQL中出现这两个字段
10. 时间条件尽量用between比较,不要对数据库原始数据使用TO_DATE函数
11. 禁止输出其它任何字符
12.如果用户问题中的实体信息中的location有多个值，就用in ('XX')全部包含进来"""

task_84_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_84_infer_cfg = dict(
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

task_84_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_84_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_84',
        path='data/custom_task/task_84.jsonl',
        reader_cfg=task_84_reader_cfg,
        infer_cfg=task_84_infer_cfg,
        eval_cfg=task_84_eval_cfg,
    )
]
