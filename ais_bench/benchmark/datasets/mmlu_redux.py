import os
import json
from datasets import load_from_disk,Dataset, DatasetDict
from ais_bench.benchmark.registry import LOAD_DATASET
from ais_bench.benchmark.datasets.utils.datasets import get_data_path
from .base import BaseDataset
from ais_bench.benchmark.utils.logging.error_codes import DSET_CODES
from ais_bench.benchmark.utils.logging.exceptions import AISBenchDataContentError
def _fix_record(record: dict) -> dict:
    """
    根据 MMLU-Redux 的 error_type 修正 choices 和 answer。
    返回修正后的 record（包含 'choices' 和 'answer' 字段）。
    """
    question = record['question']
    choices = list(record['choices'])  # 避免修改原数据
    original_answer = int(record['answer'])
    error_type = record.get('error_type', '')
    correct_answer = record.get('correct_answer', None)
    target_index = [original_answer]

    if error_type == 'no_correct_answer' and correct_answer:
        # 替换原答案位置的选项文本
        choices[target_index[0]] = correct_answer

    elif error_type == 'wrong_groundtruth' and correct_answer:
        # 修正答案索引
        try:
            target_index = [int(correct_answer)]
        except ValueError:
            # 尝试字母（如 "C" -> 2）
            if isinstance(correct_answer, str) and len(correct_answer.strip()) == 1:
                idx = ord(correct_answer.strip().upper()) - ord('A')
                if 0 <= idx < len(choices):
                    target_index = [idx]
                else:
                    raise AISBenchDataContentError(
                        DSET_CODES.DATA_INVALID_CONTENT,
                        f"Invalid correct_answer letter: {correct_answer}"
                    )
            else:
                raise AISBenchDataContentError(
                    DSET_CODES.DATA_INVALID_CONTENT,
                    f"Cannot parse correct_answer: {correct_answer}"
                )

    elif error_type == 'multiple_correct_answers' and correct_answer:
        # >>> 严格遵循用户提供的原始逻辑 <<<
        ca = str(correct_answer).strip('()')
        try:
            # Step 1: replace ' and '/' or ' with ','
            ca = ca.replace(' and ', ',').replace(' or ', ',')
            # Split and convert to int
            target_index = list(map(int, ca.split(',')))
        except ValueError:
            try:
                # Step 2: try parsing as letters (A, B, C...)
                # 注意：原始逻辑未 strip 空格，这里按原样 split，但加安全处理
                parts = ca.split(',')
                indices = []
                for part in parts:
                    p_clean = part.strip()  # <-- 关键修复：避免 ' C' 导致 ord 失败
                    if p_clean and len(p_clean) == 1 and p_clean.isalpha():
                        idx = ord(p_clean.upper()) - ord('A')
                        indices.append(idx)
                    else:
                        raise ValueError(f"Invalid part: '{part}'")
                target_index = indices
            except (ValueError, TypeError):
                # Step 3: fallback to text matching in choices
                parts = ca.split(',')
                indices = []
                for part in parts:
                    p_clean = part.strip()
                    if p_clean in choices:
                        indices.append(choices.index(p_clean))
                if not indices:
                    raise AISBenchDataContentError(
                        DSET_CODES.DATA_INVALID_CONTENT,
                        f"None of the parts in correct_answer '{correct_answer}' found in choices"
                    )
                target_index = indices

    return {
        'question': question,
        'choices': choices,
        'answer': target_index,
    }
   
@LOAD_DATASET.register_module()
class MMLUReduxDataset(BaseDataset):
    """
    MMLU Redux 数据集加载类。
    结构：根目录下有多个学科文件夹（如 anatomy, astronomy），每个文件夹下有 test.csv 或 arrow 文件。
    """
    @staticmethod

    def load(path: str, name: str, **kwargs):
        """
        Load MMLU-Redux dataset from a JSONL file.
        
        Expected format per line:
        {
            "question": "What is ...?",
            "choices": ["A", "B", "C", "D"],
            "answer": 2  # int, 0-based index
        }
        """
        path = get_data_path(path)
        category_path = os.path.join(path, name)
        dataset = load_from_disk(category_path)
        raw_data = []
        for row_idx, row in enumerate(dataset):
            if len(row['choices']) != 4:
                raise AISBenchDataContentError(
                    DSET_CODES.DATA_INVALID_STRUCTURE,
                    f"Row {row_idx} in {name} has {len(row['choices'])} columns, expected 4"
                )
            fixed = _fix_record(row)
            letters = ['ABCD'[i] for i in fixed['answer'] if 0 <= i < 4]
            answer_letter = ' '.join(letters)
            raw_data.append({
                'input': fixed['question'],
                'A': fixed['choices'][0],
                'B': fixed['choices'][1],
                'C': fixed['choices'][2],
                'D': fixed['choices'][3],
                'target': answer_letter,
            })
        dataset = Dataset.from_list(raw_data)        
        return dataset