from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import CustomPassAtKEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_39: 自定义评测任务
# Metric: pass@k？

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """你是${database}数据库专家，当前时间为: ${datetime}。问题中的查询时间没有指定年份时，请使用当前时间的年份。
# 任务
基于下面给出的表信息，将以下问题转换为SQL语句，只输出SQL，不要描述内容。${timeSpec}
# 要求
SQL语句中使用AS设置别名时，不要使用DATE，date等数据库关键字，SQL中不要查询问题无关的字段，不要构造表中不存在的字段，尽量把用到的时间字段查询出来。
# 数据库结构
该查询基于这个表进行，该表的建表语句如下：
${tables_info}
" """

task_39_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_39_infer_cfg = dict(
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

task_39_eval_cfg = dict(
    evaluator=dict(type=CustomPassAtKEvaluator),
)

# 导出数据集配置
task_39_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_39',
        path='data/custom_task/task_39.jsonl',
        reader_cfg=task_39_reader_cfg,
        infer_cfg=task_39_infer_cfg,
        eval_cfg=task_39_eval_cfg,
    )
]
