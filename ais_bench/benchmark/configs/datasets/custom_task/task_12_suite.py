from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_12: 自定义评测任务
# Metric: Acc

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """[角色] 请担任语音质检专家
[任务] 对输入[录音文本]进行“投诉原因”质检，基于**录音内容**请识别投诉原因，原因分为九类：营销资费、网速慢掉线卡顿、无法上网、终端设备、WIFI信号差、业务质量、垃圾电话、其他、无法判断、未接通。
[要求]
- 营销资费，参考关键词：[<营销资费关键词>]
- 网速慢掉线卡顿，参考关键词：[<网速慢掉线卡顿关键词>]
- 无法上网，参考关键词：[<无法上网关键词>]
- 终端设备，参考关键词：[<终端设备关键词>]
- WIFI信号差，参考关键词：[<WIFI信号差关键词>]
- 业务质量，参考关键词：[<业务质量关键词>]
- 垃圾电话，参考关键词：[<垃圾电话关键词>]
- 其他，能识别且未在上述分类中
- 无法判断，录音质量问题或内容不完整无法判断
[输出格式] 请将识别结果和依据用json格式输出，注意
1、result字段输出字符串"是"（中文）。
2、cause字段输出字符串，仅限九类原因之一（如"营销资费"），不要输出其他内容。
3、basis字段输出字符串，必须使用[录音文本]中的原文片段。
4、格式示例：
{
   "result": "是",
   "cause": "营销资费",
   "basis": "用户咨询'营销活动'"
}
[录音文本]"""

task_12_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_12_infer_cfg = dict(
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

task_12_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_12_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_12',
        path='data/custom_task/task_12.jsonl',
        reader_cfg=task_12_reader_cfg,
        infer_cfg=task_12_infer_cfg,
        eval_cfg=task_12_eval_cfg,
    )
]
