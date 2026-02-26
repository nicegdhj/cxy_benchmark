from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_65: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """# [角色] 请担任一个客户是否认可判断助手
# [任务] 从[文本]中，识别客户是否表达认可，包含询问是否同意将工单报结，包括：回单、闭环、回掉、报掉、结单、关单等关键词；另外，客户主动表示可以报结工单也算客户认可。
注意：有些词汇可能被记录成类似发音或字型相似的词。 
key_sentence输出[文本]的判断依据，需要一句询问的句子，和一句认可的句子，比如“询问（先报结了），认可（好的）”，询问在前，认可在后。使用原文，不要超过两句话。
# [输出格式]结果以JSON格式输出，例如：
```json
{
    "key_sentence": "",
    "result": "认可"
} 
```
如果没有找到，则输出：
```json
{
    "key_sentence": "None",
    "result": "不认可"
}
```"""

task_65_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_65_infer_cfg = dict(
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

task_65_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_65_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_65',
        path='data/custom_task/task_65.jsonl',
        reader_cfg=task_65_reader_cfg,
        infer_cfg=task_65_infer_cfg,
        eval_cfg=task_65_eval_cfg,
    )
]
