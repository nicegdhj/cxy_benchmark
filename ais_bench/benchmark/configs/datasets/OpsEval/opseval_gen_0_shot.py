from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer

from ais_bench.benchmark.datasets import OpsEvalDataset
from ais_bench.benchmark.openicl.icl_evaluator import AccEvaluator
from ais_bench.benchmark.utils.postprocess.text_postprocessors import first_option_postprocess

opseval_sub_sets = [
    "5G_Communication",
    "Mobile_Communication_Network",
    "Wired_NetWork"
]

opseval_datasets = []

for _name in opseval_sub_sets:
    # Reader configuration
    opseval_reader_cfg = dict(
        input_columns=["question"],
        output_column="answer",
    )

    # Inference configuration
    opseval_infer_cfg = dict(
        prompt_template=dict(
            type=PromptTemplate,
            template=f"Please select the correct answer from the options provided.\nQuestion:\n{{question}}\\n答案：",
        ),
        retriever=dict(type=ZeroRetriever),
        inferencer=dict(type=GenInferencer),
    )

    # Evaluation configuration
    opseval_eval_cfg = dict(
    evaluator=dict(type=AccEvaluator),
    pred_postprocessor=dict(type=first_option_postprocess,options='ABCDE'),
)

    # Dataset configuration
    opseval_datasets.append(
        dict(
            abbr=f"opseval_{_name}",
            type=OpsEvalDataset,
            path=f"data/OpsEval",
            name=_name,
            reader_cfg=opseval_reader_cfg,
            infer_cfg=opseval_infer_cfg,
            eval_cfg=opseval_eval_cfg,
        )
    )
del _name
