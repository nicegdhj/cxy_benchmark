import ast
from typing import List

from ais_bench.benchmark.registry import ICL_EVALUATORS
from ais_bench.benchmark.openicl.icl_evaluator.icl_base_evaluator import BaseEvaluator


@ICL_EVALUATORS.register_module()
class CodeASTEvaluator(BaseEvaluator):
    """
    Code AST Evaluator.

    Evaluates the accuracy of code generation by comparing the Abstract Syntax Trees (AST)
    of the prediction and the reference. This allows for checking structural equality
    ignoring formatting differences (whitespace, comments, etc.).
    """

    def __init__(self) -> None:
        super().__init__()

    def score(self, predictions: List, references: List) -> dict:
        """
        Calculate AST match accuracy.

        Args:
            predictions (List): List of predicted code strings.
            references (List): List of reference code strings.

        Returns:
            dict: calculated scores {'accuracy': float}.
        """
        if len(predictions) != len(references):
            return {
                "error": "predictions and references have different "
                f"length. len(predictions): {len(predictions)}, "
                f"len(references): {len(references)}"
            }

        correct = 0
        total = len(predictions)

        for pred, ref in zip(predictions, references):
            try:
                # Parse both prediction and reference into ASTs
                pred_ast = ast.parse(pred)
                ref_ast = ast.parse(ref)

                # Check for structural equality using ast.dump
                if ast.dump(pred_ast) == ast.dump(ref_ast):
                    correct += 1
            except SyntaxError:
                # If prediction is not valid Python code, it's definitely not a match
                pass
            except Exception:
                # Catch other potential parsing errors safely
                pass

        accuracy = (correct / total) * 100 if total > 0 else 0
        return {"accuracy": accuracy}
