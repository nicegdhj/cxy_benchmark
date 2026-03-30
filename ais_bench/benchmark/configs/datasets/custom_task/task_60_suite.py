from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JsonFieldEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_60: 自定义评测任务
# Evaluator: JsonFieldEvaluator

SYSTEM_INSTRUCTION = """# [角色] 你是一个运营商投诉解析助手
# [任务] 请对用户的[投诉内容]进行分析，根据分类规则判断投诉类型以及判断依据。
# [说明] 
① 分类规则：
- 网络类：包含断网、定位、信号差、网速慢、流量异常、无法连接、路由器故障、接打电话故障、无法上网、信号、网络、语音不好等涉及到技术的故障，输出“网络类”。
- 非网络类：其他如订购、费用、服务态度、流量套餐变更、物联卡开通取消等涉及到收费的问题，输出“非网络类”。
# [输出要求]
结果请使用JSON格式。
```json
{
  "投诉类型": ...,
  "投诉类型判断依据": ...
}
```"""

task_60_reader_cfg = dict(
    input_columns=["input"],
    output_column="output",
)

task_60_infer_cfg = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template=dict(
            begin=[
                dict(role="SYSTEM", fallback_role="HUMAN", prompt=SYSTEM_INSTRUCTION),
            ],
            round=[
                dict(role="HUMAN", prompt="{input}"),
                dict(role="BOT", prompt=""),
            ],
        ),
    ),
    retriever=dict(type=ZeroRetriever),
    inferencer=dict(type=GenInferencer),
)

task_60_eval_cfg = dict(
    evaluator=dict(
        type=JsonFieldEvaluator,
        field_config={
            "投诉类型": {"match_type": "exact", "weight": 1.0},
            "投诉类型判断依据": {"match_type": "exact", "weight": 0},
        },
        default_match_type="exact",
        return_details=True,
        strict_mode=True,
    ),
)

# 导出数据集配置
task_60_datasets = [
    dict(
        type=CustomDataset,
        abbr="task_60",
        path="data/custom_task/task_60.jsonl",
        reader_cfg=task_60_reader_cfg,
        infer_cfg=task_60_infer_cfg,
        eval_cfg=task_60_eval_cfg,
    )
]
