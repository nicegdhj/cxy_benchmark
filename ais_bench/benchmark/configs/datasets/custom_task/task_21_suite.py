from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_21: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '[角色] 请担任语音质检专家\n[任务] 对输入[录音文本]对客户情绪进行判断，分为三类，积极、中性、消极。\n[要求] \n参考消极关键词：[<关键词>]\n① 若客户的话中包含消极关键词2个或2个以上，认为情绪为消极；\n② 若客户的话存在较明显的感谢、表彰的含义，认为情绪为积极；\n③ 其余认为情绪为中性；\n[输出格式] 请将识别结果和依据用json格式输出，注意\n1、result字段输出字符串"积极"、"中性"或"消极"（中文）。\n2、basis字段输出字符串，必须使用[录音文本]中的原文片段。\n3、格式示例：\n{\n   "result": "中性",\n   "basis": "...\n}\n[录音文本]'

task_21_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_21_infer_cfg = dict(
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

task_21_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_21_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_21',
        path='data/custom_task/task_21.jsonl',
        reader_cfg=task_21_reader_cfg,
        infer_cfg=task_21_infer_cfg,
        eval_cfg=task_21_eval_cfg,
    )
]
