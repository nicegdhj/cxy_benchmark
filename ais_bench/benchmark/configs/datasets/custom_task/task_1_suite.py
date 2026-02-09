from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# Task 1: 宽带业务分类与信息提取
# Metric: EM (精确匹配)

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '''
接下来我会给你发若干个文本，请你从我新发的文本和历史所有文本中(优先考虑新文本的信息)，回答下面的问题：

## 判断我的问题是属于哪个业务类别？请从以下选择：
宽带密码重置:宽带账号密码重置
宽带密码修改:宽带账号密码修改,密码同步, 改1-6
查询宽带受理人员和渠道:查询宽带受理人、办理人的联系方式和渠道,受理组织,受理记录,受理营业厅
查询宽带极光和普通类型:大小猫查询、网关查询、光猫类型、ONU类型、宽带类型
... (完整的系统提示词)

请将结果以dict格式返回,不要返回其他任何信息。格式样例{"业务类别":"","信息提取":{}}
'''

task_1_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_1_infer_cfg = dict(
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

task_1_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),  # EM 使用 AccEvaluator
)

# 导出数据集配置
task_1_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_1_broadband_classification',
        path='data/custom_task/task_1.jsonl',
        reader_cfg=task_1_reader_cfg,
        infer_cfg=task_1_infer_cfg,
        eval_cfg=task_1_eval_cfg,
    )
]