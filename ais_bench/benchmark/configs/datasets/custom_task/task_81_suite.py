from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_81: 自定义评测任务
# Metric: EM + 字段级准确率

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """你是一个意图识别、指标解析和时间解析的数据增强专家
（1）现在有以下业务指标可供查询：
日报、网络情况、网络运行、网络运维、网络投诉、网络安全、移动业务、家庭业务、政企业务、用户数、业务量、业务质量、移动网络峰值用户数、4G网络峰值注册用户数、5G网络峰值注册用户数、话务量、数据流量、5G流量、4G流量、5G分流比、5G注册成功率均值、MME附着成功率均值、VoNR网络接通率均、4G/5G无线接通率均值、4G/5G切换成功率均值、家庭宽带峰值在线用户数、宽带电视峰值播放用户数、BRAS峰值流入流速、BRAS峰值利用率、CDN峰值流速、宽带电视EPG请求成功率均值、宽带电视播放成功率均值、宽带电视卡顿比、专线客户数、5G专网峰值在线用户数、专线数、重要保障、重要事件、网络功能、网络割接、移动业务投诉情况、家庭业务投诉情况、政企业务投诉情况、网络投诉接续质量、投诉热点等等。
（2）用户的输入中可能会包含一个或者多个的指标，你需要分析用户的提问是否包含这些指标的信息，并抽取相关指标形成指标列表，而后将用户非标准化的指标描述转写成标准的指标名，其余保持不变。
（3）a. 你需要帮助用户进行指标查询和分析，需要把用户的输入进行拆解，提取出时间和需要查询的内容，若时间只到月，则给出一整个月的时间列表信息;时间精确到日，用yyyy-mm-dd格式表示；如果用户没有输入明确的时间，例如，“今天” 、“昨天” 、“上月”等模糊时间描述，则解析出对应时间A，同时你需要将**用户输入中的时间改写为精确的时间A**，作为新的查询内容，如mm月dd日等；如果是近n天，上周等相对时间描述，则返回对应的list形式返回所有日期；如果是"近期"、"最近"等模糊时间段描述，则返回近一周的时间列表; b. 如果用户没有输入时间信息，则需理解用户的需求，若是查询指标则日期为前三天；c. 若用户提问中包含“变化情况”、“趋势”、“趋势分析”等需要多时间分析的查询，则返回近7天，不包含今天。时间信息用列表返回所有日期。

##要求
1.以json字符串格式进行返回，需要包含4个字段，其中"category"为"indicator"，"indicator_lsit"中为提取的字段列表，"time"为抽取出来的时间，"query"中为改写的问题。若用户的提问中不包含上述指标，则返回指标列表为空，query中为原问题。
2.只需要返回json，禁止返回其他内容
##示例
（以下示例仅供参考，请勿直接复制）
示例1：
当用户输入为 : "8月16日网络用户数是多少"
输出为：
{
"category": "indicator",
"indicator_lsit": ["移动网络峰值用户数"],
"time": ["2025-08-16"],
"query": "8月16日移动网络峰值用户数是多少"
}

示例2：
当用户输入为 :"网络用户数和网络流量之间的关联"
输出为：
{
"category":"indicator",
"indicator_lsit":["移动网络峰值用户数","数据流量"],
"time":["yyyy-mm-dd","yyyy-mm-dd","yyyy-mm-dd","yyyy-mm-dd","yyyy-mm-dd","yyyy-mm-dd","yyyy-mm-dd"],
"query":"移动网络峰值用户数和数据流量之间的关联"
}


示例3：
当用户输入为“昨天5G用户数是多少”，
 输出为：
{
"category":"indicator",
"indicator_lsit":["5G网络峰值注册用户数"],
"time":["yyyy-mm-dd"],
"query":"mm月dd日5G用户数是多少"
}

示例4：
当用户输入为 : "NE5000E接口基础配置"
输出为：
{
"category":"indicator",
"indicator_lsit":[],
"time":[],
"query":"NE5000E接口基础配置"
}"""

task_81_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_81_infer_cfg = dict(
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

task_81_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_81_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_81',
        path='data/custom_task/task_81.jsonl',
        reader_cfg=task_81_reader_cfg,
        infer_cfg=task_81_infer_cfg,
        eval_cfg=task_81_eval_cfg,
    )
]
