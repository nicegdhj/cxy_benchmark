from ais_bench.benchmark.openicl.icl_prompt_template import PromptTemplate
from ais_bench.benchmark.openicl.icl_retriever import ZeroRetriever
from ais_bench.benchmark.openicl.icl_inferencer import GenInferencer

from ais_bench.benchmark.datasets import TeleQuADDataset
from ais_bench.benchmark.openicl.icl_evaluator import LLMJudgeEvaluator

telequad_sub_sets = [
    "extractive",
    "tabular",
]

telequad_datasets = []

for _name in telequad_sub_sets:
    # Reader configuration
    telequad_reader_cfg = dict(
        input_columns=["question"],
        output_column="answer",
    )

    # Inference configuration
    telequad_infer_cfg = dict(
        prompt_template=dict(
            type=PromptTemplate,
            template=f"You are a specialized telecommunications QA assistant. Your primary knowledge comes from 3GPP specs, but you may use general telecom knowledge when 3GPP coverage is insufficient\nInstructions:\n* Prioritize answering strictly based on facts explicitly stated in 3GPP technical specifications.\n* If the answer cannot be confirmed from 3GPP documentation, you may use general telecommunications domain knowledge to provide a reasonable response.\n* Do not hallucinate, fabricate, or present speculative information as fact.\n* Use standard 3GPP terminology wherever possible.\nQuestion:\n{{question}}",
        ),
        retriever=dict(type=ZeroRetriever),
        inferencer=dict(type=GenInferencer),
    )

    # Evaluation configuration
    telequad_eval_cfg = dict(
        evaluator=dict(type=LLMJudgeEvaluator),
    )

    # Dataset configuration
    telequad_datasets.append(
        dict(
            abbr=f"telequad_{_name}",
            type=TeleQuADDataset,
            path=f"data/TeleQuAD/{_name}",
            name=_name,
            reader_cfg=telequad_reader_cfg,
            infer_cfg=telequad_infer_cfg,
            eval_cfg=telequad_eval_cfg,
        )
    )
del _name
