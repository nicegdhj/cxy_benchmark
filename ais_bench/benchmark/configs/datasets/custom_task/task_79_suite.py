from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import CodeASTEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_79: 自定义评测任务
# Metric: AST

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '这个工具可以查询某些部门/单位的工作亮点和不足的工作内心\n\n接口调用说明：\ncurl -X POST http://188.108.12.72:65532/worksheet/getFilteredData \\\n -H \'Content-Type: application/json\' \\\n -d \'{\n    "id": "xsydgzdp",\n      "params": [\n        {\n            "key": "danwei",\n            "value": ["椒江分公司"]        },#从用户的问题中完成实体抽取，该字段表示分公司的名字，例如椒江分公司、黄岩分公司\n{\n            "key": "riqi",\n            "value": ["2025-12-01"] # 该字段表示指标月度日期，取每个月的第一天，例如数据样例2025-11-01表示2025年11月的数据     }\n    ]\n}\''

task_79_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_79_infer_cfg = dict(
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

task_79_eval_cfg = dict(
    evaluator=dict(type=CodeASTEvaluator),
)

# 导出数据集配置
task_79_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_79',
        path='data/custom_task/task_79.jsonl',
        reader_cfg=task_79_reader_cfg,
        infer_cfg=task_79_infer_cfg,
        eval_cfg=task_79_eval_cfg,
    )
]
