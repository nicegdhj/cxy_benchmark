from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_5: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = '请你根据用户问题和历史记录识别用户的意图\n\n# 意图识别\nA:查询质差情况，查询室内质差\nB:处理质差，处理异常,解决质差，解决异常\nC:质差是否修复\nD:网关wifi信道调优\nE:路由器信道调优\nF:网关重启\nG:路由器重启\nH:查询重启和调优的执行情况,是否生效,解决进展\nI:室外断，中断\nJ:室外慢检测\nK:诊断异常,账号诊断，频繁掉线、上网卡顿、测速不达标,在线状态为停机, 网络性能指标无法采集获取,无法打开网页\nL:重复投诉单：重复投诉单\nM:个体质差单：个体质差单\nZ:其他常规问题，闲聊,不明确意图等\n\n\n# 注意事项\n优先考虑最新一条的用户输入意图；\n如果最新输入只有一串账号，那么意图优先考虑上一条；\n\n# 输出格式\n{"意图识别":"B"}'

task_5_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_5_infer_cfg = dict(
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

task_5_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_5_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_5',
        path='data/custom_task/task_5.jsonl',
        reader_cfg=task_5_reader_cfg,
        infer_cfg=task_5_infer_cfg,
        eval_cfg=task_5_eval_cfg,
    )
]
