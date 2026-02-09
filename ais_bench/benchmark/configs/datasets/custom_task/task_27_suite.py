from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_27: 自定义评测任务
# Metric: EM

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '/no_think\n你现在是一个意图分流专家，现在又三个功能点如下，\n1.结合用户提供的客户背景、产品名称等生成售前解决方案文档，包含需求分析、网络接入方案、实施步骤、施工成本等信息。\n2.结合上下文中已经生成的多个接入专线成本预估方案，根据用户的需求选择唯一的需求方案，用户的输入 直接为 选择方案1，采纳方案1之类。\n3.施工点位新增及方案生成 用户输入专线接入的规划需求，需包含以下必要信息： 施工点位地址（支持文本地址或经纬度）、所属地市及区县、接入方式/点位类型/专线产品名称 用户也可提供更多扩展信息（非必填）：项目名称、点位楼层、接入资源类型（如DP盒、全业务光交、传输光交、基站机房）、接入资源范围（200米、500米、1公里）、方案数量（例如生成3个或5个方案）、新增敷设策略（直埋、管道、挂墙、杆路等）系统将根据输入新增施工点位并生成多个可选的接入专线路径方案，\n\n你需要根据用户用户的输入判断使用的功能，并直接给出功能id，仅需提供id数字\n\n{{input}}'

task_27_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_27_infer_cfg = dict(
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

task_27_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_27_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_27',
        path='data/custom_task/task_27.jsonl',
        reader_cfg=task_27_reader_cfg,
        infer_cfg=task_27_infer_cfg,
        eval_cfg=task_27_eval_cfg,
    )
]
