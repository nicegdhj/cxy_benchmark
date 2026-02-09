from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_23: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '[角色] 请担任语音质检专家\n[任务] 对输入[录音文本]进行是否存在禁忌语质检，**基于录音内容**判断是否存在禁忌语。\n[要求] \n参考关键词：[<关键词>]\n[输出格式] 请将识别结果和依据用json格式输出，注意\n1、result字段输出字符串"是"或"否"（中文），若result为"否"，则basis字段输出空字符串""。\n2、basis字段输出字符串，必须使用[录音文本]中的原文片段。\n3、格式示例：\n{\n   "result": "是",\n   "basis": "用户说\'\'"\n}\n[录音文本]'

task_23_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_23_infer_cfg = dict(
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

task_23_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_23_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_23',
        path='data/custom_task/task_23.jsonl',
        reader_cfg=task_23_reader_cfg,
        infer_cfg=task_23_infer_cfg,
        eval_cfg=task_23_eval_cfg,
    )
]
