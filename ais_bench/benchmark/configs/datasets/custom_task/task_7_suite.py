from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_7: 自定义评测任务
# Metric: ROUGE

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """请你帮我提取时间范围，如果没有输入时间就回复无。"
"如果有时间请提取为array格式，[%Y%m%d%H%M,%Y%m%d%H%M]，"
"如果只输入一个精确时间，就根据这个时间前后倒退半小时，例如下午3点，则时间范围是下午2点半到3点半，"
"如果没有输入时间就默认最近两个小时"
"如果有两个时间，根据时间排序返回array"
"如果超过两个时间，就只考虑最近的两个时间"
"如果输入一个范围，例如最近一周，昨天，则按照格式输出对应的起止时间"
f"现在是now_date, weekdays，不要有思考过程，只返回给我[\"%Y%m%d%H%M\",\"%Y%m%d%H%M\"]"
"# 注意事项，日期必须是12位的字符串"""

task_7_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_7_infer_cfg = dict(
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

task_7_eval_cfg = dict(
    evaluator=dict(type=JiebaRougeEvaluator),
)

# 导出数据集配置
task_7_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_7',
        path='data/custom_task/task_7.jsonl',
        reader_cfg=task_7_reader_cfg,
        infer_cfg=task_7_infer_cfg,
        eval_cfg=task_7_eval_cfg,
    )
]
