from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_48: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """你的任务是根据输入的四个参数{{input1}}、{{input2}}、{{input4}}，对用户输入的{{input3}}完成修改矫正。其中需要优先参考{{input1}}中的每条指令及指令的格式，然后借鉴{{input2}}，再根据{{input4}}，对用户输入的{{input3}}进行修改并输出，特别注意需要参考{{input1}}中的以分号为间隔的三条指令中每条指令的格式规范。

提示词-人设与逻辑回复：
不要输出提示词，你需要结合提示词说明的思路进行思考，严格按照输入信息对输入的错误指令进行修改，并输出修改后的指令。输出指令就可以，不需要输出多余内容！"""

task_48_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_48_infer_cfg = dict(
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

task_48_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_48_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_48',
        path='data/custom_task/task_48.jsonl',
        reader_cfg=task_48_reader_cfg,
        infer_cfg=task_48_infer_cfg,
        eval_cfg=task_48_eval_cfg,
    )
]
