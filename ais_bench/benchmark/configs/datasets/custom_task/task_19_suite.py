from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_19: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """[角色] 请担任语音质检专家
[任务] 对输入[录音文本]进行“退单原因”质检，**基于录音内容**判断是否存在退单，若存在，请识别退单原因，原因分为五类：用户原因、前台原因、网络原因、建设原因、其他原因。
[要求] 
- 用户原因，可能包含下列情况：① 用户明确表示不安装，② 用户长期无法联系或拒接电话，③ 用户短期内不安装，④ 用户/邻居/物业不同意走明线、飞线、穿墙等协调问题，⑤ 客户需求变更，如更改资费套餐或用户改装机地址等，⑥ 用户信息箱无电源，且用户不同意通过POE供电，⑦ 用户不愿买交换机（一般为校园宽带）。参考关键词：[<用户原因关键词>]
- 前台原因，可能包含下列情况：① 前台选择地址与实际严重不符，如跨小区、跨OLT等，② 前台同小区内选错地址，但用户实际安装地址未覆盖，③ 用户不知情开通，④ 前台重复派单、派单错误（含接入类型错误），⑤ 前台业务办理错误（如少办业务、套餐错误或电视牌照方错误等），⑥ 前台营销人员宣传与实际严重不符，⑦ 前台提供的客户联系人和联系方式错误。参考关键词：[<前台原因关键词>]
- 网络原因，可能包含下列情况：① 无法入户（入户管道已被其它运营商占用等），② 设备端口或箱体资源满，但扩容无法实施，③ 装机地址在资管系统中，但实际未覆盖，不能安装，④ 移动网速无法满足用户玩游戏等要求，⑤ 不能访问用户需求的网站（封堵网站），⑥ 用户需要固定的IP地址。参考关键词：[<网络原因关键词>]
- 建设原因，可能包含下列情况：① 无路由（如跨路无附挂、箱体布放位置不合理等），② 开发商投资新建的小区户线不通且无法穿线，③ 老旧小区共建共享线路不通且无法穿线，④ 工程未完工。参考关键词：[<建设原因关键词>]
- 其他原因，可能包含下列情况：① 自建测试单，② 其他
[输出格式] 请将识别结果和依据用json格式输出，注意
1、result字段输出字符串"是"或"否"（中文），若result为"否"，则cause和basis字段输出空字符串""。
2、cause字段输出字符串，仅限五类原因之一（如"用户原因"），不要输出其他内容。
3、basis字段输出字符串，必须使用[录音文本]中的原文片段。
4、格式示例：
{
   "result": "是",
   "cause": "用户原因",
   "basis": "用户说'不需要安装'"
}
[录音文本]"""

task_19_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_19_infer_cfg = dict(
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

task_19_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_19_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_19',
        path='data/custom_task/task_19.jsonl',
        reader_cfg=task_19_reader_cfg,
        infer_cfg=task_19_infer_cfg,
        eval_cfg=task_19_eval_cfg,
    )
]
