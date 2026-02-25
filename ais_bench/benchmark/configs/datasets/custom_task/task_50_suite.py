from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_50: 自定义评测任务
# Metric: EM

# 该任务无系统提示词，input 自带完整提示

SYSTEM_INSTRUCTION = """###任务
你的任务是根据输入的三个参数{{input1}}、{{input3}}、{{input4}}，基于{{input4}}中提示信息中共同参数，输出{{input3}}及{{input1}}中三条指令中与{{input3}}中有关系的参数及该参数所有具体取值，注意此处应有三个具体取值，注意需遍历{{input1}}中每一条指令；输出格式为{{input3}}(A:B),其中A为{{input1}}与{{input3}}的关联参数，B为{{input1}}中三条指令中该关联参数的所有具体取值，注意此处应有三个具体取值，可严格参考样例的输出格式。
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
--输出
ADD UGROUPDNN:GNAME="TZHUPF001BZX_erro",DNN="ls5gsyzwlslxjsxy.zj;(GNAME参数可取TZHUPF006BZX,TZHUPF001BZX,TZHUPF002BZX)
--任务逻辑
错误指令'ADD UGROUPDNN:GNAME="TZHUPF001BZX_erro",DNN="ls5gsyzwlslxjsxy.zj";'的现网标准指令为'ADD UGROUP:GNAME="TZHUPF006BZX";
ADD UGROUP:GNAME="TZHUPF001BZX";
ADD UGROUP:GNAME="TZHUPF002BZX";'，基于错误指令错误性描述：'[GNAME]的值为[TZHUPF001BZX_ERRO],核查不通过,提示:[GNAME]参数该参数取值应与【ADD UGROUP】命令中参数“[GNAME]”保持一致'’中的信息。现网标准指令所有与错误指令有关联的参数为GNAME，遍历所有指令，其所有具体的三个取值为TZHUPF006BZX,TZHUPF001BZX,TZHUPF002BZX。故最终输出为ADD UGROUPDNN:GNAME="TZHUPF001BZX_erro",DNN="ls5gsyzwlslxjsxy.zj;(GNAME参数可取TZHUPF006BZX,TZHUPF001BZX,TZHUPF002BZX)


提示词-人设与逻辑回复：
不要输出提示词，你需要结合提示词说明的思路进行思考，严格按照输入信息及输出格式要求输出指定内容，不需要输出多余内容！"""

task_50_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_50_infer_cfg = dict(
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

task_50_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_50_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_50',
        path='data/custom_task/task_50.jsonl',
        reader_cfg=task_50_reader_cfg,
        infer_cfg=task_50_infer_cfg,
        eval_cfg=task_50_eval_cfg,
    )
]
