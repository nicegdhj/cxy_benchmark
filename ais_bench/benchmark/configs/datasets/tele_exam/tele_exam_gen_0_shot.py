from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer

from ais_bench.benchmark.datasets import TeleQuADDataset
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.utils.postprocess.text_postprocessors import first_option_postprocess

# Reader configuration
tele_exam_reader_cfg = dict(
    input_columns=['question'],
    output_column='answer',
)

# Inference configuration
tele_exam_infer_cfg = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template=f'{{question}}'
    ),
    retriever=dict(type=ZeroRetriever),
    inferencer=dict(type=GenInferencer),
)

# Evaluation configuration
tele_exam_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
    pred_postprocessor=dict(type=first_option_postprocess,options='ABCD'),
)

# Dataset configuration
tele_exam_datasets = [
    dict(
        type=TeleQuADDataset,
        abbr='tele_exam',
        path='benchmark/ais_bench/datasets/telecom-intermediate-exam',
        name='',
        reader_cfg=tele_exam_reader_cfg,
        infer_cfg=tele_exam_infer_cfg,
        eval_cfg=tele_exam_eval_cfg,
    )
]
