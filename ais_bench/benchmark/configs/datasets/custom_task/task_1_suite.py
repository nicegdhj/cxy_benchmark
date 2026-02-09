from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_1: 自定义评测任务
# Metric: EM

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = 'system_instruction: str = \'\'\'\n    接下来我会给你发若干个文本，请你从我新发的文本和历史所有文本中(优先考虑新文本的信息)，回答下面的问题：\n\n    ## 判断我的问题是属于哪个业务类别？请从以下选择：\n    宽带密码重置:宽带账号密码重置\n    宽带密码修改:宽带账号密码修改,密码同步, 改1-6\n    查询宽带受理人员和渠道:查询宽带受理人、办理人的联系方式和渠道,受理组织,受理记录,受理营业厅\n    查询宽带极光和普通类型:大小猫查询、网关查询、光猫类型、ONU类型、宽带类型\n    查询宽带注册码:查询宽带注册码,激活码,认证码\n    查询宽带出库的设备序列号:查询设备序列号, sn码, 设备码\n    查询路由器终端模式:查询路由器档位,甲供还是乙供,组网模式,组网串号\n    查询摄像头装机类型:询问是否是阳光厨房、云台、室内或室外、安心包、和慧眼\n    查询宽带账号:根据序列号、手机号、机顶盒账号查询宽带账号，但不能查手机号或联系号码，宽带查询，宽带账户\n    查询宽带工单报结状态:查询宽带工单报结状态,是否办结,竣工,报了没\n    查询宽带撤单和退单记录:查询宽带撤单、退单记录\n    查询光功率值:看数据或者看光, 只有一个光字,PON口下用户光功率查询\n    查询机顶盒账号:查机顶盒,宽带电视,电视的账号或密码,查7开头账号\n    查询宽带3A及在线信息:掉线记录，上网记录，上线记录,下线记录\n    工单派发:通常是将单子派个某个人\n    开端口:指开通光功率，开光猫，激活ONU，激活或重启,猫开下\n    签收码查询:只要包含签收、验证码、交付码等相似关键字的都选这个\n    用户配置端口查询:查询返回该业务的资管配置端口信息（olt设备、分光器端口），光交信息，用户配置信息，查资管，分光器,查汇聚,查PON,查跳纤,查上联,资源信息,一级,资源点,哪个箱子\n    分纤箱位置查询:查询附近分纤箱位置\n    插拔网纤:看IP端口的光功率,PON口下用户上下线实时动态\n    随销推荐:随销推荐标签，销售，推销产品\n    修改机顶盒密码:修改机顶盒密码, 7开头的账号\n    踢下线:踢下线\n    超级密码查询:超级密码查询\n    装维主动领单:挂起、驳回、转我、领单、派我\n    出入库轨迹:出入库轨迹\n    查询在途装机类的工单信息:在途工单信息，有单子吗,单子在哪里,单子下来没,查询单,有没有单子,询问单子相关的内容\n    查询机顶盒安装时间和渠道:机顶盒安装\n    终端溯源查询:溯源,查询终端设备，在库已经在网的历时数据\n    查宽带账号当前所有在网设备:在网设备\n    暂不确定:只发了一个账号，或者可能是其他类别，但是不能确定具体是哪个，就选择这个\n    不支持该业务:确定业务不在以上所有类别\n    \n\n    ## 提取文本中包含的账号信息，请从以下选择：\n    宽带账号:首字母非v的五位小写字母+八位数字,a+十一位数字\n    密码:由六位纯数字组成\n    手机号:十一位纯数字\n    派发对象手机号:在工单派发的场景下，转给某个对象的手机号\n    工单号:ZJ或cp开头的账号\n    机顶盒账号:首字母v开头的五位小写字母+九位数字组成,7开头纯数字；\n    序列号:数字和大写字母组成\n    师傅名字:中文名称，不是数字和字母，只能提取成一个中文人名或"我"\n    \n    ## 注意事项\n    历史中的账号信息也需要提取，如果有重复的，以最新输入的为准。\n    请将结果以dict格式返回,不要返回其他任何信息。格式样例{"业务类别":"","信息提取":{}}\n    \'\'\''

task_1_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_1_infer_cfg = dict(
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

task_1_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_1_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_1',
        path='data/custom_task/task_1.jsonl',
        reader_cfg=task_1_reader_cfg,
        infer_cfg=task_1_infer_cfg,
        eval_cfg=task_1_eval_cfg,
    )
]
