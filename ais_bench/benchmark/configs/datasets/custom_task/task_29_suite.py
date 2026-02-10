from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_29: 自定义评测任务
# Metric: EM

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """/no_think
结合上下文信息，提取当前施工点位接入方案的点位Id 以及用户需要的方案编号

你需要的返回的json格式如下：

{  
 "positionId": "提取到的当前施工点位接入方案的点位Id"  ,
  "id": "方案编号,只需要是数值，int类型"  
}  
\`\`\`json和\`\`\`是JSON开始和结束的标志，不要省略。  

历史信息
{history}

用户输入
{user}
'''"""

task_29_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_29_infer_cfg = dict(
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

task_29_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_29_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_29',
        path='data/custom_task/task_29.jsonl',
        reader_cfg=task_29_reader_cfg,
        infer_cfg=task_29_infer_cfg,
        eval_cfg=task_29_eval_cfg,
    )
]
