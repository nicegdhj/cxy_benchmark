from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_20: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """[角色] 请担任语音质检专家
[任务] 对输入[录音文本]进行“是否催单”质检，**基于录音内容**判断是否存在催单。
[要求] 
参考关键词：[<关键词>]
[输出格式] 请将识别结果和依据用json格式输出，注意
1、result字段输出字符串"是"或"否"（中文），若result为"否"，则basis字段输出空字符串""。
2、basis字段输出字符串，必须使用[录音文本]中的原文片段。
3、格式示例：
{
   "result": "是",
   "basis": "用户说'你快点上门'"
}
[录音文本]"""

task_20_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_20_infer_cfg = dict(
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

task_20_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_20_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_20',
        path='data/custom_task/task_20.jsonl',
        reader_cfg=task_20_reader_cfg,
        infer_cfg=task_20_infer_cfg,
        eval_cfg=task_20_eval_cfg,
    )
]
