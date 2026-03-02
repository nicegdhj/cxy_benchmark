from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer
from ais_bench.benchmark.openicl.icl_evaluator import LLMJudgeEvaluator

from ais_bench.benchmark.datasets import TeleExamSubDataset
from ais_bench.benchmark.utils.postprocess.text_postprocessors import first_option_postprocess

# -----------------------------------------------------------------------
# 子科目列表
# 对应 telecom-intermediate-exam/<year>/<subcategory>/ 下的文件夹名称。
# 若某年份下不存在对应文件夹，数据加载时会自动跳过。
# -----------------------------------------------------------------------
tele_exam_sub_sets = [
    # '交换技术',
    # '传输与接入（无线）',
    # '传输与接入（有线）',
    # '终端与业务',
    '互联网技术',
    # '设备环境',
]

tele_exam_sub_datasets = []

for _name in tele_exam_sub_sets:

    _reader_cfg = dict(
        input_columns=['question'],
        output_column='answer',
        test_range='[:2]',
    )

    _infer_cfg = dict(
        prompt_template=dict(
            type=PromptTemplate,
            # 主观题：直接呈现题目，请模型给出答案
            template='{question}\n请根据题型简洁作答：填空题只写答案，选择题只写字母，问答题简要回答。：\n答：',
        ),
        retriever=dict(type=ZeroRetriever),
        inferencer=dict(type=GenInferencer),
    )

    # 主观题使用 AccEvaluator 做精确匹配评估（也可后续替换为其他评估器）
    _eval_cfg = dict(
        evaluator=dict(type=LLMJudgeEvaluator),
    )

    tele_exam_sub_datasets.append(
        dict(
            type=TeleExamSubDataset,
            abbr=f'tele_exam_{_name}',
            path='ais_bench/datasets/telecom-intermediate-exam',
            name=_name,
            reader_cfg=_reader_cfg,
            infer_cfg=_infer_cfg,
            eval_cfg=_eval_cfg,
        )
    )

del _name, _reader_cfg, _infer_cfg, _eval_cfg
