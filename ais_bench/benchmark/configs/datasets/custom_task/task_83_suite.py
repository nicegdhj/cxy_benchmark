from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_83: 自定义评测任务
# Metric: EM + 实体级F1

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """你是一个知识图谱工程专家，非常擅长从文本中精确抽取知识图谱的实体（主体、客体）和关系，并能对实体和关系的含义做出恰当的总结性描述。输出一个包含表名、时间类型、地区、查询内容、开始日期和结束日期的json

# 要求
1.表名如下表示：
 下述json中的key为表名，其对应的value为此场景中的样例问题"""

task_83_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_83_infer_cfg = dict(
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

task_83_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_83_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_83',
        path='data/custom_task/task_83.jsonl',
        reader_cfg=task_83_reader_cfg,
        infer_cfg=task_83_infer_cfg,
        eval_cfg=task_83_eval_cfg,
    )
]
