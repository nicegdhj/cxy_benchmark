import os
import json
import tempfile
from typing import List, Dict

from ais_bench.benchmark.registry import ICL_EVALUATORS
from ais_bench.benchmark.openicl.icl_evaluator.icl_base_evaluator import BaseEvaluator
from ais_bench.benchmark.utils.logging.logger import AISLogger
from ais_bench.benchmark.utils.logging.error_codes import DSET_CODES
from ais_bench.benchmark.utils.logging.exceptions import AISBenchImportError

logger = AISLogger()

HUMANEVAL_IMPORT_ERROR = """\
Please install human_eval use following steps:
git clone git@github.com:open-compass/human-eval.git
cd human-eval && pip install -e ."""


@ICL_EVALUATORS.register_module()
class CustomPassAtKEvaluator(BaseEvaluator):
    """
    Custom Pass@k Evaluator.

    Re-implemented logic from HumanEvalEvaluator to support custom datasets.
    Unlike existing HumanEvalEvaluator which binds to a specific hardcoded dataset,
    this evaluator dynamically constructs the problem definition file from the
    input `test_set` (dataset), allowing pass@k evaluation on ANY custom data.

    Requirements for the custom dataset items:
    - 'task_id': Unique identifier for the problem.
    - 'prompt': The code prompt/signature provided to the model.
    - 'entry_point': The name of the function to test.
    - 'test': The unit test code string.
    - 'canonical_solution': (Optional) Reference solution.
    """

    def __init__(self, k: List[int] = [1]) -> None:
        try:
            import human_eval
        except ImportError as e:
            raise AISBenchImportError(
                DSET_CODES.EVALUATION_LIBRARY_NOT_INSTALLED, HUMANEVAL_IMPORT_ERROR
            ) from e

        self.k = k
        super().__init__()

    def score(self, predictions: List, references: List, test_set: List[Dict]) -> Dict:
        """
        Calculate pass@k scores for custom datasets.

        Args:
            predictions (List): List of predicted code strings.
            references (List): List of canonical solutions (not strictly used for execution, but for aligning).
            test_set (List[Dict]): The dataset items containing problem definitions.

        Returns:
            Dict: calculated scores {'pass@1': float, ...} and 'details'.
        """
        if len(predictions) != len(test_set):
            return {
                "error": f"predictions and test_set have different lengths: {len(predictions)} vs {len(test_set)}"
            }

        from human_eval.evaluation import evaluate_functional_correctness
        from human_eval.data import write_jsonl

        # Prepare temporary directory for execution artifacts
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Create a custom problem file based on the test_set
            # This is the key difference allowing "Custom" datasets
            problems_file = os.path.join(tmp_dir, "custom_problems.jsonl")
            problems_data = []

            for item in test_set:
                problems_data.append(
                    {
                        "task_id": item.get(
                            "task_id", f"task_{hash(item.get('prompt', ''))}"
                        ),
                        "prompt": item.get("prompt", ""),
                        "entry_point": item.get("entry_point", "solution"),
                        "test": item.get("test", ""),
                        "canonical_solution": item.get("canonical_solution", ""),
                    }
                )

            write_jsonl(problems_file, problems_data)

            # 2. Prepare predictions in HumanEval format
            completion_file = os.path.join(tmp_dir, "custom_completions.jsonl")
            completion_data = []

            for i, (pred, item) in enumerate(zip(predictions, test_set)):
                task_id = item.get("task_id", f"task_{hash(item.get('prompt', ''))}")

                # Handle single prediction string or list of strings (for k>1 sampling)
                # But here in simple ICL mode, usually we get one string per sample unless configured otherwise.
                # If we want to support k>1, we assume 'predictions' might contain list of strings if n > 1
                # or we just treat single string as k=1.
                preds_list = pred if isinstance(pred, list) else [pred]

                for p in preds_list:
                    completion_data.append({"task_id": task_id, "completion": p})

            write_jsonl(completion_file, completion_data)

            # 3. Run execution-based evaluation
            # Using 4 workers by default, timeout 3.0s per test case
            logger.info(
                f"Running pass@k evaluation on {len(completion_data)} samples..."
            )
            pass_at_k_scores = evaluate_functional_correctness(
                sample_file=completion_file,
                k=self.k,
                n_workers=4,
                timeout=3.0,
                problem_file=problems_file,
            )

            # 4. Parse execution results to generate details with correct/incorrect info
            # Format details as list of dicts with standard schema expected by BaseEvaluator
            details_list = []
            results_file = completion_file + "_results.jsonl"
            if os.path.exists(results_file):
                with open(results_file, "r") as f:
                    for idx, line in enumerate(f):
                        res = json.loads(line)
                        # Extract task_id and pass status
                        task_id = res.get("task_id", f"task_{idx}")
                        passed = res.get("passed", False)
                        completion_text = res.get("completion", "")

                        # Build detail dict following standard evaluator schema
                        detail = {
                            "pred": completion_text,  # The generated code
                            "answer": references[idx]
                            if idx < len(references)
                            else "",  # Reference solution
                            "correct": passed,  # Boolean: whether test passed
                            "is_correct": passed,  # Alias for compatibility
                        }
                        details_list.append(detail)

        # Transform keys to match standard format e.g. "pass@1"
        results = {f"pass@{k}": v * 100 for k, v in pass_at_k_scores.items()}

        # Return details as list of dicts (standard format)
        if details_list:
            results["details"] = details_list

        return results
