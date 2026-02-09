from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import CodeASTEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_6: 自定义评测任务
# Metric: AST

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '请你从以下文本中提取用户输入的账号对应的wifi名称和当前信道号，并返回对应wifi名称和信道号，不要有思考过程和其他无用语句。\n\n# 注意事项\n如果没有wifi名称或当前信道号，不要出现相关key，如果两个都没有，那么就返回无；\n有几个就返回几个；\n注意用json返回；\n信道号是纯数字，wifi名称是字符型，可能加载中英文，标点，数字等；\n不要随便提取无关的信息，要明确说了是wifi名称和信道相关字眼才能提取，例如有：wifi名称是wbb_!223,信道号是1，那么提取结果是{"WiFiName":"wbb_!223","channel":"1"}；\n可能会单独输入信道号或wifi名称，也要进行提取；\n\n# 输出格式\n{"WiFiName":"wifi名称","channel":"信道号"}'

task_6_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_6_infer_cfg = dict(
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

task_6_eval_cfg = dict(
    evaluator=dict(type=CodeASTEvaluator),
)

# 导出数据集配置
task_6_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_6',
        path='data/custom_task/task_6.jsonl',
        reader_cfg=task_6_reader_cfg,
        infer_cfg=task_6_infer_cfg,
        eval_cfg=task_6_eval_cfg,
    )
]
