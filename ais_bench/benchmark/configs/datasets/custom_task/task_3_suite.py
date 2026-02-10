from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_3: 自定义评测任务
# Metric: ROUGE

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """请总结以下用户反馈的网络问题：
        {chr(10).join(recent_problems)}

        请用一句话总结用户遇到的核心问题，格式为："xxx问题"。
        例如："网络卡顿问题"、"视频缓冲问题"、"游戏延迟问题"等。
        以用户最新一条问题为主，如"网络卡"则为"网络卡顿问题",如"网络慢"则为"网络慢问题"。"""

task_3_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_3_infer_cfg = dict(
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

task_3_eval_cfg = dict(
    evaluator=dict(type=JiebaRougeEvaluator),
)

# 导出数据集配置
task_3_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_3',
        path='data/custom_task/task_3.jsonl',
        reader_cfg=task_3_reader_cfg,
        infer_cfg=task_3_infer_cfg,
        eval_cfg=task_3_eval_cfg,
    )
]
