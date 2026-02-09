from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_15: 自定义评测任务
# Metric: Acc

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '[角色] 请担任语音质检专家\n[任务] [录音文本]是装维人员与客户的语音对话文本，对输入[录音文本]进行是否存在引导改约质检，比如装维人员提到太晚了或者今天工作太多，来不及过来，且用户不同意，属于存在引导改约。\n[要求] \n参考关键词：[<关键词>]\n[输出格式] 请将识别结果和依据用json格式输出，注意\n1、result字段输出字符串"是"或"否"（中文），若result为"否"，则basis字段输出空字符串""。\n2、basis字段输出字符串，必须使用[录音文本]中的原文片段。\n3、格式示例：\n{\n   "result": "是",\n   "basis": "装维人员说\'\'"\n}\n[录音文本]'

task_15_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_15_infer_cfg = dict(
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

task_15_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_15_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_15',
        path='data/custom_task/task_15.jsonl',
        reader_cfg=task_15_reader_cfg,
        infer_cfg=task_15_infer_cfg,
        eval_cfg=task_15_eval_cfg,
    )
]
