import json
import os
import re
from datasets import Dataset

from ais_bench.benchmark.registry import LOAD_DATASET
from ais_bench.benchmark.datasets.base import BaseDataset

def extract_option_letter(answer_str):
    # 使用正则提取 "option X" 中的数字 X
    match = re.search(r'option[_\s]*(\d+)', answer_str, re.IGNORECASE)
    if not match:
        return None  # 未找到 option 数字
    option_num = int(match.group(1))
    if option_num < 1 or option_num > 26:
        return None  # 超出 A-Z 范围
    return chr(ord('A') + option_num - 1)
@LOAD_DATASET.register_module()
class TeleQnADataset(BaseDataset):
    """Dataset class for TeleQnA (Telecommunications Q&A) dataset.
    
    The TeleQnA dataset contains telecommunications domain questions with multiple
    choice options, answers, explanations, and categories.
    
    Data format:
    {
        "question 0": {
            "question": "...",
            "option 1": "...",
            "option 2": "...",
            ...
            "answer": "option X: ...",
            "explanation": "...",
            "category": "..."
        },
        ...
    }
    """

    @staticmethod
    def load(path: str, file_name: str = None, **kwargs):
        """Load TeleQnA dataset from JSON file.
        
        Args:
            path: Path to the dataset directory
            file_name: Name of the JSON file (default: None, will look for .txt or .json)
            **kwargs: Additional arguments
            
        Returns:
            Dataset: HuggingFace Dataset object
        """
        # Construct full path
        if file_name:
            full_path = os.path.join(path, file_name)
        else:
            # Try common file names
            for fname in ['TeleQnA.txt', 'TeleQnA.json', 'test.json']:
                test_path = os.path.join(path, fname)
                if os.path.exists(test_path):
                    full_path = test_path
                    break
            else:
                raise FileNotFoundError(f"No TeleQnA data file found in {path}")
        
        # Load JSON data
        with open(full_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        # Convert to list format
        data_list = []
        for question_id, question_data in raw_data.items():
            # Extract question text
            question_text = question_data.get('question', '')
            
            # Extract options (can be option 1-5 or more)
            options = {}
            option_num = 1
            while f'option {option_num}' in question_data:
                content = question_data[f'option {option_num}']
                letter = chr(ord('A') + option_num - 1) 
                options[letter] = content  
                option_num += 1
            while f'option_{option_num}' in question_data:
                content = question_data[f'option_{option_num}']
                letter = chr(ord('A') + option_num - 1) 
                options[letter] = content  
                option_num += 1            
            # Extract answer
            answer = question_data.get('answer', '')
            letter = extract_option_letter(answer)

            
            # Extract explanation and category
            explanation = question_data.get('explanation', '')
            category = question_data.get('category', '')
            
            # Create formatted item
            item = {
                'question_id': question_id,
                'question': question_text,
                'answer': letter,
                'explanation': explanation,
                'category': category,
            }
            
            # Add all options to the item
            item.update(options)
            
            data_list.append(item)
        
        return Dataset.from_list(data_list)
