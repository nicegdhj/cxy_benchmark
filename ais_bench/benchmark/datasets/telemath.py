import json
import os
import re
from os import environ

from datasets import Dataset, DatasetDict

from ais_bench.benchmark.openicl.icl_evaluator import BaseEvaluator
from ais_bench.benchmark.registry import (ICL_EVALUATORS, LOAD_DATASET,
                                  TEXT_POSTPROCESSORS)
from ais_bench.benchmark.datasets.utils.datasets import get_data_path
from ais_bench.benchmark.utils.logging.logger import AISLogger
from ais_bench.benchmark.utils.logging.error_codes import DSET_CODES
from ais_bench.benchmark.utils.logging.exceptions import ParameterValueError, AISBenchDataContentError

from .base import BaseDataset

logger = AISLogger()



@LOAD_DATASET.register_module()
class TeleMathDataset(BaseDataset):

    @staticmethod
    def load(path: str, file_name: str = 'test.json', **kwargs):
        path = get_data_path(path)
        logger.debug(f"Loading TeleMath dataset from: {path}/{file_name}")
        dataset = DatasetDict()
        raw_data = []

        file_path = os.path.join(path, file_name)
        data = json.load(open(file_path))
        
        # TeleMath data is a list, not a dictionary
        if isinstance(data, list):
            for item in data:
                raw_data.append({
                    'problem': item['question'],
                    'solution': str(item['answer']),  # Convert numeric answer to string
                    'category': item.get('category', ''),
                    'tags': item.get('tags', []),
                    'difficulty': item.get('difficulty', '')
                })
        else:
            # Fallback for dictionary format
            for key in data.keys():
                item = data[key]
                raw_data.append({
                    'problem': item['question'],
                    'solution': str(item['answer']),
                    'category': item.get('category', ''),
                    'tags': item.get('tags', []),
                    'difficulty': item.get('difficulty', '')
                })

        dataset['test'] = Dataset.from_list(raw_data)
        dataset['train'] = Dataset.from_list(raw_data)
        logger.debug(f"TeleMath dataset loaded: {len(raw_data)} samples")
        return dataset

