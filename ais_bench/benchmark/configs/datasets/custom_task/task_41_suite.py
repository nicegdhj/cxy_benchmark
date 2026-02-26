from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_41: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """## 任务要求
假如你是语言专家，先分析输入问题中的句子成分，主语、谓语、宾语名词、宾语修饰，状语、定语等，剔除除宾语名词外的所有词，不可更改提取的原句内容，以JSON字典的形式返回。

## 逻辑分析
如\"查询RRU设备序列号为2102314FXS10Q3100246关联小区列表\"
\"查询\"是谓语，\"RRU设备序列号为2102314FXS10Q3100246\"是定语，\"关联小区列表\"为宾语名词。


## 注意事项
返回结果只需返回一个json字典，不需要添加分析或注意内容。

## 返回格式
返回字段为1个：
`entity 宾语核心部分


## 已知信息
-输入问题 
{}

## 输入
例如：\"查询RRU设备序列号为2102314FXS10Q3100246关联小区列表\"

## 输出示例：
{{\"entity\": \"关联小区列表\"}}"""

task_41_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_41_infer_cfg = dict(
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

task_41_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_41_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_41',
        path='data/custom_task/task_41.jsonl',
        reader_cfg=task_41_reader_cfg,
        infer_cfg=task_41_infer_cfg,
        eval_cfg=task_41_eval_cfg,
    )
]
