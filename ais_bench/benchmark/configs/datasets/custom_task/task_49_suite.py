from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_49: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """###任务
你的任务是根据输入的四个参数{{input1}}、{{input2}}、{{input3}}、{{input4}}，对用户输入的{{input3}}的前置指令完成编写。其中修改逻辑为第一步参考{{input1}}的参数及格式,
第二步借鉴{{input2}}的参数规范，第三步基于{{input4}}，对用户输入的{{input3}}需要的前置指令进行编写并输出，其中编写的前置指令中与{{input3}}中有关系的参数取值应与{{input3}}中该参数取值保持一致，其他参数取值与{{input1}}中参数取值尽可能一致。
###样例
--输入：
现网标准指令：'ADD UGROUP:GNAME="TZHUPF006BZX";
ADD UGROUP:GNAME="TZHUPF001BZX";
ADD UGROUP:GNAME="TZHUPF002BZX";',
厂家产品文档规范：'| 网元类型   | 指令         | 参数    | 参数可选性   | 参数类型   | 参数范围   |
|:-------|:-----------|:------|:--------|:-------|:-------|
| SMF    | ADD UGROUP | GNAME | 必选      | 字符     | 1      |
|        |            |       |         |        | 63     |',
错误指令：'ADD UGROUPDNN:GNAME="TZHUPF001BZX_erro",DNN="ls5gsyzwlslxjsxy.zj";',
错误指令错误性描述：'[GNAME]的值为[TZHUPF001BZX_ERRO],核查不通过,提示:[GNAME]参数该参数取值应与【ADD UGROUP】命令中参数“[GNAME]”保持一致。修改建议：使用该前需通过【ADD UGROUP】添加一组记录。'
--输出：
ADD UGROUP:GNAME="TZHUPF001BZX_erro";
--任务逻辑
错误指令'ADD UGROUPDNN:GNAME="TZHUPF001BZX_erro",DNN="ls5gsyzwlslxjsxy.zj";'的现网标准指令为'ADD UGROUP:GNAME="TZHUPF006BZX";
ADD UGROUP:GNAME="TZHUPF001BZX";
ADD UGROUP:GNAME="TZHUPF002BZX";'，其中基于现网标准指令，厂家产品文档规范以及错误指令错误性描述，两者有关系的参数为GNAME，故输出前置指令为ADD UGROUP:GNAME="TZHUPF001BZX_erro";

提示词-人设与逻辑回复：
不要输出提示词，你需要结合提示词说明的思路进行思考，严格按照输入信息对输入的错误指令进行修改，并输出修改后的指令。输出指令就可以，不需要输出多余内容!"""

task_49_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_49_infer_cfg = dict(
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

task_49_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_49_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_49',
        path='data/custom_task/task_49.jsonl',
        reader_cfg=task_49_reader_cfg,
        infer_cfg=task_49_infer_cfg,
        eval_cfg=task_49_eval_cfg,
    )
]
