from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_8: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '你是一个意图识别的专家，需要根据用户输入的问题将其分为如下几类：\n0. 其它\n101. 在岗装维数\n102. 在职装维数\n103. FTTR光猫活跃用户数\n104. 终端营业回收量\n105. 满意度维系量\n106. 受理工单量\n107. 在途工单量\n108. 报结工单量\n109. 超时工单量\n110. 即将超时工单量\n111. 当天上门工单\n112. 满意度情况\n113. 质量积分\n114. 工单及时率\n115. 退单率\n116. 24小时报结率\n117. 重复投诉率\n118. 有责稽核情况\n119. 智能质检情况\n120. 装维用户画像\n121. 装维薪酬及构成\n122. 奖励和考核情况\n123. 薪酬排名情况\n124. 随营随销\n\n注意：\n- 要求只输出类别编号，禁止输出多于内容\n- 出现"上门打卡装维"、"在岗装维"等类似字眼或者类似含义为意图101\n- 出现"在职装维"、"装维数"等类似字眼或者类似含义为意图102\n- 出现"光猫"、"网关"等类似字眼或者类似含义为意图103\n- 出现"回收量"等类似字眼或者类似含义为意图104\n- 出现"满意度维系量"等字眼为意图105\n- 出现"受理工单"、"XX工单"等类似字眼或者类似含义为意图106\n- 出现"在途工单"、"未报结工单"等类似字眼或者类似含义为意图107\n- 出现"报结工单""等类似字眼或者类似含义为意图108\n- 出现"超时工单""等类似字眼或者类似含义为意图109\n- 出现"即将超时""等类似字眼或者类似含义为意图110\n- 出现"XX上门工单""等类似字眼或者类似含义为意图111\n- 出现"满意度情况""等类似字眼或者类似含义为意图112\n- 出现"质量积分"等类似字眼或者类似含义为意图113\n- 出现"工单及时率"等类似字眼或者类似含义为意图114\n- 出现"退单"等类似字眼或者类似含义为意图115\n- 出现"报结率"等类似字眼或者类似含义为意图116\n- 出现"重复投诉"等类似字眼或者类似含义为意图117\n- 出现"有责稽核"、"有责工单"等类似字眼或者类似含义为意图118\n- 出现"质检情况"等类似字眼或者类似含义为意图119\n- 出现"用户画像"等类似字眼或者类似含义为意图120\n- 出现"薪酬"、"XX月薪酬"、"XX工资"、"薪酬变化"、"薪酬构成"、"薪酬清单"等类似字眼或者类似含义为意图121\n- 出现"奖励和考核"、"XX月奖励和考核"等类似字眼或者类似含义为意图122\n- 出现"薪酬排名"等类似字眼或者类似含义为意图123\n- 出现"随营"、"随销"、"营服"等字眼为意图124'

task_8_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_8_infer_cfg = dict(
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

task_8_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_8_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_8',
        path='data/custom_task/task_8.jsonl',
        reader_cfg=task_8_reader_cfg,
        infer_cfg=task_8_infer_cfg,
        eval_cfg=task_8_eval_cfg,
    )
]
