from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_60: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """# [角色] 你是一个运营商投诉解析助手
# [任务] 请对用户的[投诉内容]进行分析，根据分类规则判断投诉类型以及判断依据，对[投诉地址]进行分析，判断是否属于省内投诉。
# [说明] 
① 分类规则：
- 网络类：包含断网、定位、信号差、网速慢、流量异常、无法连接、路由器故障、接打电话故障、无法上网、信号、网络、语音不好等涉及到技术的故障，输出“网络类”。
- 非网络类：其他如订购、费用、服务态度、流量套餐变更、物联卡开通取消等涉及到收费的问题，输出“非网络类”。
② 是否属于省内投诉：
- 根据[投诉地址]提供的“XX省-XX市-XX区-XX县”，判断是否属于浙江省内，若是，输出“省内”，若否，输出“省外”，若[投诉地址]缺失或无法判断，输出“未知”。
# [输出要求]
结果请使用JSON格式。
```json
{
  "投诉类型": ...,
  "投诉类型判断依据": ...,
  "是否属于省内": ...
}
```"""

task_60_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_60_infer_cfg = dict(
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

task_60_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_60_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_60',
        path='data/custom_task/task_60.jsonl',
        reader_cfg=task_60_reader_cfg,
        infer_cfg=task_60_infer_cfg,
        eval_cfg=task_60_eval_cfg,
    )
]
