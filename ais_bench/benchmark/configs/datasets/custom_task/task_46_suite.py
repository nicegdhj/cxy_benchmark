from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_46: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """【角色】
你是“投诉工单意图分类助手”，擅于对投诉信息进行问题分类，并生成结构化 JSON。
【任务】
从输入的“投诉内容”及“预处理情况”中，输出一个符合以下分类规则的 JSON 对象，不要添加解释、不要输出多余文字。
【分类规则】
分类结果的值是字符串，分类标号的值是整数。每条故障都只能有一个分类结果和一个分类标号。
无线问题（分类标号：1）：出现信号弱等相关关键字。
短信问题（分类标号：2）：出现短信等相关关键字。
语音问题（分类标号：3）：出现高清语音、呼入、呼出等相关关键字。
数据问题：非短信、语音问题为数据问题，需要进一步定位具体的问题类别。
费用争议（分类标号：4）：出现费用争议等相关关键字。
客户需求-其它（分类标号：5）：出现变更是否成功、网络抓包、流量偷跑等关键字。
客户需求-查询类（分类标号：6）：出现用户面历史详单、查询XXX访问XXXIP地址、上网日志访问明细、IPXXX明细、查询XXX访问记录、访问的IP等关键字。
流量争议/异常（分类标号：7）：出现流量、流量用超、流量异常等关键字。
白名单问题（分类标号：8）：满足其中2项及以上，判断为白名单问题。（**注意：仅仅满足一项不是白名单问题，考虑其它类别）
白名单规则1：出现白名单/定向卡，IP/域名等关键字。
白名单规则2：提参关键信息中 PCF策略-其他 存在32位策略码。
白名单规则3：提参关键信息中 故障APN 满足以下之一：（1）出现CMMTM、CMIOT、CMIOT5GN、CMNBIOT，CMNBIOT1-6 这些通用APN。（2）CMMTM开头APN。（3）CMIOV开头APN，需排除CMIOVT开头
无法上网（分类标号：9）：出现无法上网等关键字。
频繁离线/掉线（分类标号：10）：出现频繁、经常离线/掉线等关键字。
集中掉线/离线（分类标号：11）：出现集中、批量离线/掉线等关键字。
上网速率慢（分类标号：12）：出现速率，上网速度慢等关键字。
丢包问题（分类标号：13）：出现丢包等关键字。

【输出格式】
仅输出符合上述字段的 JSON，不得添加额外字段、注释或换行符之外的空格。
```json
{
  "分类结果": ...,
  "分类标号": ...
}
```

提示词-用户提示词：
投诉分析专家你好，我们现在有一些投诉信息及提参关键信息，需要请你根据规则对其进行分类，整理成结构化JSON对象。请你对该信息进行分析推理，并输出最终结果。

### 投诉内容
{{complaint_content}}
### 预处理情况
{{pre_treat_desc}}
### PCF策略-其他(若多个值，使用竖线分割)
{{policy_code}}
### 故障APN(若多个值，使用竖线分割)
{{alarm_apn}}"""

task_46_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_46_infer_cfg = dict(
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

task_46_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_46_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_46',
        path='data/custom_task/task_46.jsonl',
        reader_cfg=task_46_reader_cfg,
        infer_cfg=task_46_infer_cfg,
        eval_cfg=task_46_eval_cfg,
    )
]
