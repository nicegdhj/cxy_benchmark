from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import JsonFieldEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_17: 自定义评测任务
# Evaluator: JsonFieldEvaluator (字段级评估)

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """[角色] 请担任语音质检专家
[任务] 对输入[录音文本]进行“文明用语”质检，基于**录音内容**请分别识别装维人员是否有说问候语（greeting）、自我介绍（introduction）、结束语（ending）。
[要求]
- 问候语，参考关键词：[<问候语关键词>]
- 自我介绍，参考关键词：[<自我介绍关键词>]
- 结束语，参考关键词：[<结束语关键词>]
[输出格式] 请将识别结果和依据用json格式输出，注意
1、result字段输出字符串"是"或者"否"（中文）。
2、basis字段输出字符串，必须使用**录音内容**中的原文片段。
4、格式示例：
{
   "greeting_result": "是",
   "greeting_basis": "装维人员说'我移动宽带的'",
   "introduction_result": "是",
   "introduction_basis": "装维人员说'喂你好你好'",
   "ending_result": "是",
   "ending_basis": "装维人员说'嗯那不行，就明天反正后天也行，哈你你到时候临时我就早上8点吧嗯好的，再见'"
}
[录音文本]
"""

task_17_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_17_infer_cfg = dict(
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

# 字段级评估配置:
# - result 类字段: exact (精确匹配, 权重 1.0)
# - basis 类字段: rouge (ROUGE 评分, 权重 0.5)
task_17_eval_cfg = dict(
    evaluator=dict(
        type=JsonFieldEvaluator,
        field_config={
            "greeting_result": {
                        "match_type": "exact",
                        "weight": 1.0
            },
            "greeting_basis": {
                        "match_type": "rouge",
                        "weight": 0.5
            },
            "introduction_result": {
                        "match_type": "exact",
                        "weight": 1.0
            },
            "introduction_basis": {
                        "match_type": "rouge",
                        "weight": 0.5
            },
            "ending_result": {
                        "match_type": "exact",
                        "weight": 1.0
            },
            "ending_basis": {
                        "match_type": "rouge",
                        "weight": 0.5
            }
},
        default_match_type="exact",
        return_details=True,
    ),
)

# 导出数据集配置
task_17_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_17',
        path='data/custom_task/task_17.jsonl',
        reader_cfg=task_17_reader_cfg,
        infer_cfg=task_17_infer_cfg,
        eval_cfg=task_17_eval_cfg,
    )
]
