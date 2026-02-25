from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_51: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """#[角色] 核心网MML配置专家，擅长MML配置语言
#[任务] 第一步基于[倒回指令规范]{{input1}}中指令的描述及规范；第二步参考现网中[倒回指令样例]{{input2}}，如果样例为空则忽略；第三步基于[原始指令]{{input3}}里面的参数信息；结合上述三步骤信息，生成倒回指令命令,最终输出结果只输出该条倒回指令的命令，请勿输出其他内容。
#[倒回指令规范]{{input1}}
#[倒回指令样例]{{input2}}
#[原始指令] {{input3}}"""

task_51_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_51_infer_cfg = dict(
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

task_51_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_51_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_51',
        path='data/custom_task/task_51.jsonl',
        reader_cfg=task_51_reader_cfg,
        infer_cfg=task_51_infer_cfg,
        eval_cfg=task_51_eval_cfg,
    )
]
