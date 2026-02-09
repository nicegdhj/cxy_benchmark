from ais_bench.benchmark.openicl.icl_evaluator import (
    AccEvaluator,
    RougeEvaluator,
    CodeASTEvaluator,
    CustomPassAtKEvaluator,
)
from ais_bench.benchmark.datasets.custom import CustomDataset

# 1. ACC Evaluator: Standard NLP Task - Exact Match
nlp_eval_acc_dataset = dict(
    abbr="demo_nlp_eval_acc",
    type=CustomDataset,
    path="data/demo/nlp_eval.jsonl",
    reader_cfg=dict(input_columns=["question"], output_column="answer"),
    infer_cfg=dict(
        prompt_template=dict(
            type="PromptTemplate",
            template=dict(
                round=[
                    dict(role="HUMAN", prompt="{question}"),
                    dict(role="BOT", prompt=""),
                ]
            ),
        ),
        retriever=dict(type="ZeroRetriever"),
        inferencer=dict(type="GenInferencer"),
    ),
    eval_cfg=dict(
        evaluator=dict(type=AccEvaluator)  # ACC / Exact Match
    ),
)


# 2. ROUGE Evaluator: Standard NLP Task - ROUGE Score
nlp_eval_rouge_dataset = dict(
    abbr="demo_nlp_eval_rouge",
    type=CustomDataset,
    path="data/demo/nlp_eval.jsonl",
    reader_cfg=dict(input_columns=["question"], output_column="answer"),
    infer_cfg=dict(
        prompt_template=dict(
            type="PromptTemplate",
            template=dict(
                round=[
                    dict(role="HUMAN", prompt="{question}"),
                    dict(role="BOT", prompt=""),
                ]
            ),
        ),
        retriever=dict(type="ZeroRetriever"),
        inferencer=dict(type="GenInferencer"),
    ),
    eval_cfg=dict(
        evaluator=dict(type=RougeEvaluator)  # ROUGE
    ),
)


# 3. Code AST Task
# New CodeASTEvaluator used
ast_eval_dataset = dict(
    abbr="demo_ast_eval",
    type=CustomDataset,
    path="data/demo/ast_eval.jsonl",
    reader_cfg=dict(input_columns=["code_snippet"], output_column="target_code"),
    infer_cfg=dict(
        prompt_template=dict(
            type="PromptTemplate",
            template=dict(
                round=[
                    dict(role="HUMAN", prompt="Write python code: {code_snippet}"),
                    dict(role="BOT", prompt=""),
                ]
            ),
        ),
        retriever=dict(type="ZeroRetriever"),
        inferencer=dict(type="GenInferencer"),
    ),
    eval_cfg=dict(
        evaluator=dict(type=CodeASTEvaluator)  # AST Structure Match
    ),
)


# 4. Pass@k Task
# New CustomPassAtKEvaluator used
codegen_eval_dataset = dict(
    abbr="demo_codegen_eval",
    type=CustomDataset,
    path="data/demo/codegen_eval.jsonl",
    reader_cfg=dict(
        input_columns=["prompt"],
        output_column="canonical_solution",  # Needed for reference alignment
    ),
    # Note: For pass@k, the dataset items must contain 'task_id', 'entry_point', 'test'
    infer_cfg=dict(
        prompt_template=dict(
            type="PromptTemplate",
            template=dict(
                round=[
                    dict(role="HUMAN", prompt="{prompt}"),
                    dict(role="BOT", prompt=""),
                ]
            ),
        ),
        retriever=dict(type="ZeroRetriever"),
        inferencer=dict(type="GenInferencer"),
    ),
    eval_cfg=dict(
        evaluator=dict(type=CustomPassAtKEvaluator, k=[1])  # Pass@1
    ),
)
# 导出所有 4 个评估器的配置：
# 1. AccEvaluator (精确匹配)
# 2. RougeEvaluator (ROUGE 分数)
# 3. CodeASTEvaluator (AST 结构匹配)
# 4. CustomPassAtKEvaluator (Pass@k 代码执行)
custom_eval_suite_datasets = [
    nlp_eval_acc_dataset,  # 1. ACC Evaluator
    # nlp_eval_rouge_dataset,  # 2. ROUGE Evaluator
    # ast_eval_dataset,  # 3. Code AST Evaluator
    # codegen_eval_dataset,  # 4. Pass@k Evaluator
]

# custom_eval_suite_datasets = [
#     nlp_eval_acc_dataset,  # 1. ACC Evaluator
# ]

