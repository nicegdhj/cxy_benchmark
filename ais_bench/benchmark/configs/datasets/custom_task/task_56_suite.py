from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_56: 自定义评测任务
# Metric: EM + 字段级F1

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """角色设定：你是一个专业的信息提取助手，专门处理用户投诉内容和调度建议，精准提取短信发送方的公司实体名称或短信发送号码。
处理逻辑：
优先从 {{complaitContent}}（投诉内容）中提取公司名称或短信发送号码.
如果在投诉内容中未找到相关信息，则从 {{dispatchSuggestion}}（调度建议）中提取.
如果两个参数中都未找到有效信息，则返回空字符串.
输出要求：
公司名称和短信号码分别以独立的字符串形式返回
格式：{"company": "str", "phoneNumber": "str"}

人设与逻辑回复：
不要输出思考过程，你需要结合提示词说明的思路进行思考，严格按照输入信息抽取对应的值，并输出json格式的字符串。"""

task_56_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_56_infer_cfg = dict(
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

task_56_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_56_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_56',
        path='data/custom_task/task_56.jsonl',
        reader_cfg=task_56_reader_cfg,
        infer_cfg=task_56_infer_cfg,
        eval_cfg=task_56_eval_cfg,
    )
]
