from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_72: 自定义评测任务
# Metric: rouge/llm

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """# 角色：
你是一个通信领域的运维专家，擅长对告警数据进行根因分析。

# 已知
输入的数据是一些告警数据，每个告警数据包含告警标题、网元名称、告警正文、物理端口名称等各种字段。

# 任务：
1.请分析数据中的告警字段
2.判断这批告警是否有关联性
3.识别哪个告警标题是根因告警
4.分析出告警对传播链"""

task_72_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_72_infer_cfg = dict(
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

task_72_eval_cfg = dict(
    evaluator=dict(type=JiebaRougeEvaluator),
)

# 导出数据集配置
task_72_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_72',
        path='data/custom_task/task_72.jsonl',
        reader_cfg=task_72_reader_cfg,
        infer_cfg=task_72_infer_cfg,
        eval_cfg=task_72_eval_cfg,
    )
]
