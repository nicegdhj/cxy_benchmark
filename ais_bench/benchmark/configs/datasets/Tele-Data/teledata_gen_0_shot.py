from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer

from ais_bench.benchmark.datasets import TeleQuADDataset
from ais_bench.benchmark.openicl.icl_evaluator import LLMJudgeEvaluator


teledata_reader_cfg = dict(
    input_columns=['question'],
    output_column='answer',
)

# Inference configuration
teledata_infer_cfg = dict(
    prompt_template=dict(
        type=PromptTemplate,
        template=f'{{question}}'
    ),
    retriever=dict(type=ZeroRetriever),
    inferencer=dict(type=GenInferencer),
)

# Evaluation configuration
teledata_eval_cfg = dict(
    evaluator=dict(type=LLMJudgeEvaluator),
)

# Dataset configuration
teledata_datasets = [
    dict(
        abbr = f'teledata',
        type=TeleQuADDataset,
        path='ais_bench/datasets/Tele-Data',
        name='Tele-Eval.jsonl',
        reader_cfg=teledata_reader_cfg,
        infer_cfg=teledata_infer_cfg,
        eval_cfg=teledata_eval_cfg,
    )
]
