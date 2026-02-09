from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_26: 自定义评测任务
# Metric: M + 字段级F1

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '"messages": [\n      \n            {"role": "user", "content": f"/nothink {query}"}\n        ],\n        \'tools\':[\n      {\n      "type": "function",\n      "function": {\n  "name": "query_work_order_data",\n  "description": "根据指定条件查询工单数据",\n  "parameters": {\n    "type": "object",\n    "required": [\n      "data_query_type",\n      "order_type",\n      "region_name",\n      "county_name",\n      "order_status",\n      "date_type"\n    ],\n    "properties": {\n      "data_query_type": {\n        "type": "string",\n        "description": "固定为 工单信息"\n      },\n      "order_type": {\n        "type": "integer",\n        "enum": [1, 2, 3],\n        "description": "工单类型：1-售中开通工单，2-投诉工单，3-故障工单"\n      },\n      "region_name": {\n        "type": "string",\n        "description": "地市名称"\n      },\n      "county_name": {\n        "type": "string",\n        "description": "区县名称"\n      },\n      "order_status": {\n        "type": "string",\n        "enum": ["进行中", "已完成"],\n        "description": "工单状态"\n      },\n      "date_type": {\n        "type": "integer",\n        "enum": [1, 2, 3],\n        "description": "时间类型：1-当前在途工单，2-按派单时间，3-按报结时间"\n      },\n      "start_time": {\n        "type": "string",\n        "format": "date-time",\n        "description": "开始时间，格式：YYYY-MM-DD HH:mm:ss。当 date_type 为 1 时可不填，其他情况必填",\n        "pattern": "^\\\\d{4}-\\\\d{2}-\\\\d{2} \\\\d{2}:\\\\d{2}:\\\\d{2}$"\n      },\n      "end_time": {\n        "type": "string",\n        "format": "date-time",\n        "description": "结束时间，格式：YYYY-MM-DD HH:mm:ss。当 date_type 为 1 时可不填，其他情况必填",\n        "pattern": "^\\\\d{4}-\\\\d{2}-\\\\d{2} \\\\d{2}:\\\\d{2}:\\\\d{2}$"\n      }\n    },\n    "additionalProperties": False\n  }'

task_26_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_26_infer_cfg = dict(
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

task_26_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_26_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_26',
        path='data/custom_task/task_26.jsonl',
        reader_cfg=task_26_reader_cfg,
        infer_cfg=task_26_infer_cfg,
        eval_cfg=task_26_eval_cfg,
    )
]
