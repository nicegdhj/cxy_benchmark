import json
import os
from datasets import Dataset

from ais_bench.benchmark.registry import LOAD_DATASET
from ais_bench.benchmark.datasets.base import BaseDataset
from ais_bench.benchmark.utils.logging.logger import AISLogger

logger = AISLogger()


@LOAD_DATASET.register_module()
class IdentityExplorationDataset(BaseDataset):
    @staticmethod
    def load(path: str, file_name: str = None, **kwargs):
        raw_data = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if not file.endswith('.jsonl'):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                item = json.loads(line)
                                instruction = item.get("instruction", "").strip()
                                category = item.get("category", "unknown").strip()

                                if instruction:
                                    # Pack category and instruction into reference for LLMJudgeEvaluator
                                    reference = f"测试类别：\n{category}\n\n用户输入：\n{instruction}"
                                    raw_data.append({
                                        "instruction": instruction,
                                        "category": category,
                                        "reference": reference
                                    })
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")

        dataset = Dataset.from_list(raw_data)
        return dataset
