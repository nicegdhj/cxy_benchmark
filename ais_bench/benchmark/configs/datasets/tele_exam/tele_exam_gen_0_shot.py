from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer

from ais_bench.benchmark.datasets import TeleExamDataset
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.utils.postprocess.text_postprocessors import (
    first_option_postprocess,
)

# -----------------------------------------------------------------------
# 年份列表
# 对应 telecom-intermediate-exam/ 下的年份文件夹名称。
# 若对应年份下缺少“综合”文件夹，会自动跳过。
# -----------------------------------------------------------------------
tele_exam_years = [
    # '2022',
    "2023",
]

tele_exam_datasets = []

for _year in tele_exam_years:
    # Reader configuration
    # The question field already contains the answer choices inline (A/B/C/D),
    # so only 'question' is needed as input.
    _reader_cfg = dict(
        input_columns=["question"],
        output_column="answer",
    )

    # Inference configuration
    # Since each question already embeds the choices, we only append "请选择正确答案：" then "答案："
    _infer_cfg = dict(
        prompt_template=dict(
            type=PromptTemplate,
            template="{question}\\n请选择正确答案（只输出选项字母）：\\n答案：",
        ),
        retriever=dict(type=ZeroRetriever),
        inferencer=dict(type=GenInferencer),
    )

    # Evaluation configuration
    _eval_cfg = dict(
        evaluator=dict(type=AccEvaluator),
        pred_postprocessor=dict(type=first_option_postprocess, options="ABCD"),
    )

    # Dataset configuration
    tele_exam_datasets.append(
        dict(
            type=TeleExamDataset,
            abbr=f"tele_exam_{_year}",
            path="data/telecom-intermediate-exam",
            year=_year,
            reader_cfg=_reader_cfg,
            infer_cfg=_infer_cfg,
            eval_cfg=_eval_cfg,
        )
    )

del _year, _reader_cfg, _infer_cfg, _eval_cfg
