from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_11: 自定义评测任务
# Metric: EM + 字段级F1

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '[角色] 请担任信息抽取专家\n[任务] 输入[录音文本]为装维人员与客户的电话语音文本，请进行语义分析，**基于录音内容**判断装维人员与客户预约的具体时间点，并将抽取的预约时间与[装维预约上门时间]进行比较，判断是否一致。\n[要求]\n请按照步骤1、2、3，先提取预约时间，并判断预约时间是否在[装维预约上门时间]之前，[装维预约上门时间]可能有多个，用时间最晚的一个进行判断。\n步骤1、按以下①~⑥顺序提取预约时间，如果没有具体时间点，再进入步骤2\n①预约时间有完整的时间段或时间点，使用该时间点或时间段，例：“XX月XX日”、“XX月XX日XX时~XX时”\n②预约时间点或时间段仅有“XX时”或“XX时XX分”提取“工单时间”中的“日期”与“月份”组合成完整时间\n③预约时间点或时间段仅有“XX日”或“XX日XX时”或“XX日XX时XX分”提取“工单时间”中的“月份”组合成完整时间\n④预约时间为今天某个时间点或某个时间段，提取“工单时间”中的“日期”与“月份”组合成完整时间；例预约时间“今天早上9点”，工单时间“2025年7月11日13:00”，最终预约时间7月11日9:00\n⑤预约时间为昨天某个时间点或某个时间段，提取“工单时间”中的“日期”与“月份”再将“日期”-1，组合成完整时间；例预约时间“昨天下午2点56”，工单时间“2025年7月11日11:00”，最终预约时间7月10日14:56\n⑥预约时间输出请转换为24小时制，且注意一般预约时间不会出现在凌晨0-6点之间，请转换成下午的时间\n注：预约时间点或时间段中没有具体“XX时”或“XX时XX分”且描述中有“凌晨”、“下午”等模糊时间点, 将模糊时间点转换为时间区间，对应关系如下：\n上午：6:00 - 12:00\n中午：10:00 - 14:00\n下午：12:00 - 18:00\n晚上：18:00 - 0:00\n步骤2、当[录音文本]没有预约具体时间点则使用[工单时间]作为预约时间\n步骤3、预约时间是否在[装维预约上门时间]时间之前，若是，输出结果合格，若不是，输出结果不合格\n# [输出格式] 结果请用json格式输出，格式如下：\n{\n    "time": "2025-7-10 09:00:00",\n    "result": "合格",\n    "basis": "判断合格依据（录音提及“今天上午9点过来”，在[装维预约上门时间]之前）"\n}\n[录音文本]\n{text}\n[工单时间]\n{calling_time}\n[装维预约上门时间]\n{doortime}'

task_11_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_11_infer_cfg = dict(
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

task_11_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_11_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_11',
        path='data/custom_task/task_11.jsonl',
        reader_cfg=task_11_reader_cfg,
        infer_cfg=task_11_infer_cfg,
        eval_cfg=task_11_eval_cfg,
    )
]
