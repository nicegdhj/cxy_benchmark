import json
import os
import re
from datasets import Dataset

from ais_bench.benchmark.registry import LOAD_DATASET
from ais_bench.benchmark.datasets.base import BaseDataset
from ais_bench.benchmark.utils.logging.logger import AISLogger

logger = AISLogger()


@LOAD_DATASET.register_module()
class OpsEvalDataset(BaseDataset):

    @staticmethod
    def load(path: str, name: str = None, **kwargs):
        """Load OpsEval dataset from JSONL file.

        The data directory contains one JSONL file per subset, e.g.
        ``5G_Communication.jsonl``, ``Wired_NetWork.jsonl``.  Each line is a
        JSON object with the following keys:

        - ``id``       : unique question identifier
        - ``domin``    : domain / category string
        - ``question`` : question text (options already embedded, e.g.
                         "...\\nA: foo\\nB: bar")
        - ``answer``   : correct option letter, e.g. ``"A"`` (may have
                         trailing whitespace / comma)

        Args:
            path: Path to the dataset directory containing the JSONL files.
            name: Subset name (e.g. ``"5G_Communication"``).  The loader
                  will look for ``{path}/{name}.jsonl``.  When *name* already
                  ends with ``.jsonl`` it is used as-is.
            **kwargs: Additional arguments (ignored).

        Returns:
            Dataset: HuggingFace ``Dataset`` object with columns
            ``question_id``, ``question``, ``answer``, ``domin``.
        """
        # ------------------------------------------------------------------ #
        # Resolve the JSONL file path
        # ------------------------------------------------------------------ #
        if name:
            # Accept both "5G_Communication" and "5G_Communication.jsonl"
            fname = name if name.endswith('.jsonl') else f"{name}.jsonl"
            full_path = os.path.join(path, fname)
        else:
            # Fallback: use the first .jsonl file found
            candidates = [f for f in os.listdir(path) if f.endswith('.jsonl')]
            if not candidates:
                raise FileNotFoundError(
                    f"No JSONL data file found in {path}"
                )
            full_path = os.path.join(path, candidates[0])

        if not os.path.exists(full_path):
            raise FileNotFoundError(
                f"OpsEval data file not found: {full_path}"
            )

        # ------------------------------------------------------------------ #
        # Parse JSONL
        # ------------------------------------------------------------------ #
        data_list = []
        with open(full_path, 'r', encoding='utf-8') as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        f"[OpsEvalDataset] Skipping invalid JSON at line "
                        f"{lineno}: {exc}"
                    )
                    continue

                question = record.get('question', '').strip()

                # Normalise answer: strip trailing spaces, commas, etc.
                # e.g. "A, " -> "A",  "B " -> "B"
                raw_answer = str(record.get('answer', '')).strip().rstrip(', ')
                # Extract the leading letter in case there is extra text
                m = re.match(r'^([A-Za-z])', raw_answer)
                answer = m.group(1).upper() if m else raw_answer.upper()

                item = {
                    'question':    question,
                    'answer':      answer,
                }
                data_list.append(item)

        logger.info(
            f"[OpsEvalDataset] Loaded {len(data_list)} samples from "
            f"{full_path}"
        )
        return Dataset.from_list(data_list)
