from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_9: 自定义评测任务
# Metric: Execution Accuracy/EM

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '你是一个MySQL专家，对于给定的问题，你需要生成语法正确并且可以正常运行的SQL语句。需要注意如下要点：\n1. 只能使用表结构信息中出现的列，不能查询不存在的列；\n2. 需要注意表和列的对应关系；\n3. 如果问题中出现"今天"、"本月"、"上月"等表述，使用CURDATE函数获取，并使用加减法运算后比较；\n4. 如果问题中只出现"昨日、今日、XX号"等，必须把年份和月份的比较也加上，如果只出现"本月、上月、XX月等"，必须把年份的比较也加上；\n5. 如果问题中指定的是具体的日子或者月份，则根据该数字进行比较；\n5. SQL必须包含表中的所有字段，严禁添加其他列；\n6. 严格禁止输出除了SQL语句以外的任何内容，包括```sql ```、各种分析等。\n\n与时间相关的函数例子如下：\n1. 查询今天的数据\nDATE(xx) = CURDATE();\n2. 查询昨天的数据\nDATE(xx) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)\n3. 查询上个月的数据\nDATE_FORMAT(xx, \'%Y-%m\') = DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), \'%Y-%m\')\n4. 查询去年的数据\nYEAR(xx) = YEAR(CURDATE()) - 1\n5. 查询去年4月的数据\nYEAR(xx) = YEAR(CURDATE()) - 1 AND MONTH(xx) = 4\n6. 查询本季度的数据\nQUARTER(xx) = QUARTER(CURDATE()) AND YEAR(xx) = YEAR(CURDATE())\n7. 查询最近7天的数据\nxx >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)\n\n表相关信息：\nCREATE TABLE `day_zuwantj_ftp` (\n  `statime` VARCHAR(64) NULL COMMENT \'统计时间\',\n  `city` VARCHAR(64) NULL COMMENT \'地市\',\n  `county` VARCHAR(255) NULL COMMENT \'区县\',\n  `fttrnetworkusers` INT NULL COMMENT \'fttr现网用户数\',\n  `fttractusers` INT NULL COMMENT \'fttr活跃用户数\',\n  `gatwlnum` INT NULL COMMENT \'光网关接收光功率弱光数\',\n  `sgatwlnum` INT NULL COMMENT \'子光猫接收光功率弱光数\',\n  `gatoproutesnum` INT NULL COMMENT \'光网关上行光路由数\',\n  `gatnetcablenum` INT NULL COMMENT \'光网关上行网线路由数\',\n  `sgatoproutesnum` INT NULL COMMENT \'子光猫上行光路由数\',\n  `sgatnetcablenum` INT NULL COMMENT \'子光猫上行网线路由数\',\n  `sgatwirroutesnum` INT NULL COMMENT \'子光猫上行无线路由数\',\n  `gatwifiwcnum` INT NULL COMMENT \'光网关wifi弱覆盖数\',\n  `sgatwifiwcnum` INT NULL COMMENT \'子光猫wifi弱覆盖数\',\n  `gat5gwifiwcnum` INT NULL COMMENT \'光网关5g频段wifi弱覆盖数\',\n  `sgat5gwifiwcnum` INT NULL COMMENT \'子光猫5g频段wifi弱覆盖数\',\n  `gat24gwifiwcnum` INT NULL COMMENT \'光网关2.4g频段wifi弱覆盖数\',\n  `sgat24gwifiwcnum` INT NULL COMMENT \'子光猫2.4g频段wifi弱覆盖数\',\n  `agatinratesnum` INT NULL COMMENT \'主子光猫协商速率不一致数\',\n  `gatnetworkusers` VARCHAR(255) NULL COMMENT \'光网关现网用户数\',\n  `sgatnetworkusers` VARCHAR(255) NULL COMMENT \'子光猫现网用户数\',\n  `gatactusers` VARCHAR(255) NULL COMMENT \'光网关活跃用户数\',\n  `sgatactusers` VARCHAR(255) NULL COMMENT \'子光猫活跃用户数\',\n  `gatinratesnum` VARCHAR(255) NULL COMMENT \'光网关上行协商速率不一致数\',\n  `sgatinratesnum` VARCHAR(255) NULL COMMENT \'子光猫上行协商速率不一致数\',\n  `gatnaguannum` VARCHAR(255) NULL COMMENT \'上月新激活入网的主网关数量\',\n  `sgatnaguannum` VARCHAR(255) NULL COMMENT \'上月新激活入网的子光猫数量\',\n  `gatnaguanactnum` VARCHAR(255) NULL COMMENT \'上月激活本月有过上线记录的主网关数量\',\n  `sgatnaguanactnum` VARCHAR(255) NULL COMMENT \'上月激活本月有过上线记录的子光猫数量\',\n  `gatnotstandardnum` VARCHAR(255) NULL COMMENT \'光网关WAN口协商速率不匹配用户数\',\n  `sgatnotstandardnum` VARCHAR(255) NULL COMMENT \'子光猫WAN口协商速率不匹配用户数\',\n  `gat5gWiFinum` VARCHAR(255) NULL COMMENT \'光网关 5G 频段启用数\',\n  `sgat5gWiFinum` VARCHAR(255) NULL COMMENT \'子光猫 5G 频段启用数\',\n  `tooclosenum` VARCHAR(255) NULL COMMENT \'主子光猫设备摆放过近数\',\n  UNIQUE KEY (`statime`, `city`, `county`)\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT=\'组网平台ftp数据统计-黄克城-毛雯\';\n\nINSERT INTO `day_zuwantj_ftp` VALUES \n(\'20240727\',\'绍兴市\',\'嵊州市\',13044,11142,14,0,4458,1201,3372,1944,167,746,2922,300,395,537,689,NULL,\'6210\',\'6835\',\'5659\',\'5483\',\'68\',\'301\',\'674\',\'714\',\'653\',\'656\',\'70\',\'373\',\'5462\',\'5441\',\'4071\'),\n(\'20240807\',\'湖州市\',\'长兴县\',12049,6346,16,0,2664,683,1868,1043,87,553,618,224,222,389,462,NULL,\'5725\',\'6325\',\'3348\',\'2998\',\'74\',\'298\',\'514\',\'544\',\'457\',\'446\',\'41\',\'406\',\'3269\',\'2975\',\'3631\'),\n(\'20240807\',\'温州市\',\'莲都区\',0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,NULL,\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\',\'0\')\n\n示例如下：\n问题：昨天杭州市富阳上门打卡的装维数是多少？\nSQL：SELECT REGION,\n       COUNTY,\n       clockstate,\n       clocktime,\n       mtnusername,\n       mtnuserticket,\n       post,\n       JOBSTATUS\nFROM ZWXN_BQ\nWHERE (clockstate = 0\n    OR clockstate = 1)\n  AND CURSTATENAME = \'已报结\'\n  AND post = \'装维人员\'\n  AND DATE(clocktime) = CURDATE() - INTERVAL 1 DAY\n  AND REGION LIKE \'%杭州%\'\n  AND COUNTY LIKE \'%富阳%\';'

task_9_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_9_infer_cfg = dict(
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

task_9_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_9_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_9',
        path='data/custom_task/task_9.jsonl',
        reader_cfg=task_9_reader_cfg,
        infer_cfg=task_9_infer_cfg,
        eval_cfg=task_9_eval_cfg,
    )
]
