from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JiebaRougeEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_4: 自定义评测任务
# Metric: ROUGE

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """请根据以下网络慢五阶段排障的结果，生成一份专业的总结报告：

            用户宽带账号：{params.get('userName', '未知')}
            用户反馈问题：{problem_summary}

            各阶段诊断结果：
            {chr(10).join(stages_summary)}

            请按照以下格式生成总结报告：
            1. 总体诊断结论：简要概括诊断结果
            2. 主要发现：列出发现的关键问题和正常项
            3. 优先级建议：按重要性和解决难度给出处理建议顺序
            4. 后续跟进：如有需要，给出进一步检查的建议
            5. 总体诊断结论、主要发现、优先级建议、后续跟进都请换行输出，换行不要返回"\n"，用"\n#"代替
            6. 不要使用"**"加粗

            要求：
            - 语言专业、简洁、易懂
            - 针对技术人员的报告风格
            - 直接输出总结报告内容，不要输出标题
            - 重要问题要突出强调
            - 如果所有阶段都正常，说明网络状况良好
            - 控制字数在100-150字左右"""

task_4_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_4_infer_cfg = dict(
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

task_4_eval_cfg = dict(
    evaluator=dict(type=JiebaRougeEvaluator),
)

# 导出数据集配置
task_4_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_4',
        path='data/custom_task/task_4.jsonl',
        reader_cfg=task_4_reader_cfg,
        infer_cfg=task_4_infer_cfg,
        eval_cfg=task_4_eval_cfg,
    )
]
