from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.datasets.custom import CustomDataset

# task_2: 自定义评测任务
# Metric: ACC

# 该任务固定的系统提示词
SYSTEM_INSTRUCTION = """接下来我会给你发若干个文本，请你作为装维排障助手，从我新发的文本和历史所有文本中，优先考虑新文本的信息，回答下面的问题：
        
        ##判断我的问题是属于哪个业务类别？请从以下工具中选择：
        {json.dumps(function_description,ensure_ascii=False)}
        可以参考如下示例：
        1. 输入：查询工号cp-x-20250513-000-00931的概览及详情，输出：B；
        2. 输入：我的代办投诉工单，输出：A；
        3. 输入：账号进行一键诊断，输出：C；
  
        ## 注意事项
        如果不确定业务类别，请选择Z，不要随意选择一个业务类别，用户输入Z，不代表要选择Z同理其他也是，只关注内容。
        只要返回结果字母，不要输出其他内容。"""

task_2_reader_cfg = dict(
    input_columns=['input'],
    output_column='output',
)

task_2_infer_cfg = dict(
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

task_2_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
)

# 导出数据集配置
task_2_datasets = [
    dict(
        type=CustomDataset,
        abbr='task_2',
        path='data/custom_task/task_2.jsonl',
        reader_cfg=task_2_reader_cfg,
        infer_cfg=task_2_infer_cfg,
        eval_cfg=task_2_eval_cfg,
    )
]
