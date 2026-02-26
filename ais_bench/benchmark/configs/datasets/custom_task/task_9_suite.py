from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import SqlExactSetMatchEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_9: 自定义评测任务
# Metric: Execution Accuracy/EM

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """你是一个MySQL专家，对于给定的问题，你需要生成语法正确并且可以正常运行的SQL语句。需要注意如下要点：
1. 只能使用表结构信息中出现的列，不能查询不存在的列；
2. 需要注意表和列的对应关系；
3. 如果问题中出现"今天"、"本月"、"上月"等表述，使用CURDATE函数获取，并使用加减法运算后比较；
4. 如果问题中只出现"昨日、今日、XX号"等，必须把年份和月份的比较也加上，如果只出现"本月、上月、XX月等"，必须把年份的比较也加上；
5. 如果问题中指定的是具体的日子或者月份，则根据该数字进行比较；
5. SQL必须包含表中的所有字段，严禁添加其他列；
6. 严格禁止输出除了SQL语句以外的任何内容，包括```sql ```、各种分析等。

与时间相关的函数例子如下：
1. 查询今天的数据
DATE(xx) = CURDATE();
2. 查询昨天的数据
DATE(xx) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
3. 查询上个月的数据
DATE_FORMAT(xx, '%Y-%m') = DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')
4. 查询去年的数据
YEAR(xx) = YEAR(CURDATE()) - 1
5. 查询去年4月的数据
YEAR(xx) = YEAR(CURDATE()) - 1 AND MONTH(xx) = 4
6. 查询本季度的数据
QUARTER(xx) = QUARTER(CURDATE()) AND YEAR(xx) = YEAR(CURDATE())
7. 查询最近7天的数据
xx >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)

表相关信息：
CREATE TABLE `day_zuwantj_ftp` (
  `statime` VARCHAR(64) NULL COMMENT '统计时间',
  `city` VARCHAR(64) NULL COMMENT '地市',
  `county` VARCHAR(255) NULL COMMENT '区县',
  `fttrnetworkusers` INT NULL COMMENT 'fttr现网用户数',
  `fttractusers` INT NULL COMMENT 'fttr活跃用户数',
  `gatwlnum` INT NULL COMMENT '光网关接收光功率弱光数',
  `sgatwlnum` INT NULL COMMENT '子光猫接收光功率弱光数',
  `gatoproutesnum` INT NULL COMMENT '光网关上行光路由数',
  `gatnetcablenum` INT NULL COMMENT '光网关上行网线路由数',
  `sgatoproutesnum` INT NULL COMMENT '子光猫上行光路由数',
  `sgatnetcablenum` INT NULL COMMENT '子光猫上行网线路由数',
  `sgatwirroutesnum` INT NULL COMMENT '子光猫上行无线路由数',
  `gatwifiwcnum` INT NULL COMMENT '光网关wifi弱覆盖数',
  `sgatwifiwcnum` INT NULL COMMENT '子光猫wifi弱覆盖数',
  `gat5gwifiwcnum` INT NULL COMMENT '光网关5g频段wifi弱覆盖数',
  `sgat5gwifiwcnum` INT NULL COMMENT '子光猫5g频段wifi弱覆盖数',
  `gat24gwifiwcnum` INT NULL COMMENT '光网关2.4g频段wifi弱覆盖数',
  `sgat24gwifiwcnum` INT NULL COMMENT '子光猫2.4g频段wifi弱覆盖数',
  `agatinratesnum` INT NULL COMMENT '主子光猫协商速率不一致数',
  `gatnetworkusers` VARCHAR(255) NULL COMMENT '光网关现网用户数',
  `sgatnetworkusers` VARCHAR(255) NULL COMMENT '子光猫现网用户数',
  `gatactusers` VARCHAR(255) NULL COMMENT '光网关活跃用户数',
  `sgatactusers` VARCHAR(255) NULL COMMENT '子光猫活跃用户数',
  `gatinratesnum` VARCHAR(255) NULL COMMENT '光网关上行协商速率不一致数',
  `sgatinratesnum` VARCHAR(255) NULL COMMENT '子光猫上行协商速率不一致数',
  `gatnaguannum` VARCHAR(255) NULL COMMENT '上月新激活入网的主网关数量',
  `sgatnaguannum` VARCHAR(255) NULL COMMENT '上月新激活入网的子光猫数量',
  `gatnaguanactnum` VARCHAR(255) NULL COMMENT '上月激活本月有过上线记录的主网关数量',
  `sgatnaguanactnum` VARCHAR(255) NULL COMMENT '上月激活本月有过上线记录的子光猫数量',
  `gatnotstandardnum` VARCHAR(255) NULL COMMENT '光网关WAN口协商速率不匹配用户数',
  `sgatnotstandardnum` VARCHAR(255) NULL COMMENT '子光猫WAN口协商速率不匹配用户数',
  `gat5gWiFinum` VARCHAR(255) NULL COMMENT '光网关 5G 频段启用数',
  `sgat5gWiFinum` VARCHAR(255) NULL COMMENT '子光猫 5G 频段启用数',
  `tooclosenum` VARCHAR(255) NULL COMMENT '主子光猫设备摆放过近数',
  UNIQUE KEY (`statime`, `city`, `county`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组网平台ftp数据统计-黄克城-毛雯';

INSERT INTO `day_zuwantj_ftp` VALUES 
('20240727','绍兴市','嵊州市',13044,11142,14,0,4458,1201,3372,1944,167,746,2922,300,395,537,689,NULL,'6210','6835','5659','5483','68','301','674','714','653','656','70','373','5462','5441','4071'),
('20240807','湖州市','长兴县',12049,6346,16,0,2664,683,1868,1043,87,553,618,224,222,389,462,NULL,'5725','6325','3348','2998','74','298','514','544','457','446','41','406','3269','2975','3631'),
('20240807','温州市','莲都区',0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,NULL,'0','0','0','0','0','0','0','0','0','0','0','0','0','0','0')

示例如下：
问题：昨天杭州市富阳上门打卡的装维数是多少？
SQL：SELECT REGION,
       COUNTY,
       clockstate,
       clocktime,
       mtnusername,
       mtnuserticket,
       post,
       JOBSTATUS
FROM ZWXN_BQ
WHERE (clockstate = 0
    OR clockstate = 1)
  AND CURSTATENAME = '已报结'
  AND post = '装维人员'
  AND DATE(clocktime) = CURDATE() - INTERVAL 1 DAY
  AND REGION LIKE '%杭州%'
  AND COUNTY LIKE '%富阳%';"""

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
    evaluator=dict(type=SqlExactSetMatchEvaluator),
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
