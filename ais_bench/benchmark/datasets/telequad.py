import json
import os
import re
from datasets import Dataset

from ais_bench.benchmark.registry import LOAD_DATASET
from ais_bench.benchmark.datasets.base import BaseDataset
from ais_bench.benchmark.utils.logging.logger import AISLogger
logger = AISLogger()

def load_json_or_jsonl(file_path):
    """
    自动加载 .json 或 .jsonl 文件，统一返回 list[dict]。
    
    - 如果是 .json 且顶层为 list → 直接返回
    - 如果是 .json 且顶层为 dict → 包装成 [dict]
    - 如果是 .jsonl → 每行解析为 dict，组成 list
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        # 读取第一行判断类型
        first_line = f.readline()
        if not first_line.strip():
            return []  # 空文件
        
        # 尝试将整文件作为 JSON 加载（.json 格式）
        try:
            f.seek(0)  # 回到文件开头
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                raise ValueError(f"Unsupported JSON root type: {type(data)}")
        except json.JSONDecodeError:
            # 不是合法 JSON → 假设是 .jsonl
            f.seek(0)
            records = []
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
            return records
@LOAD_DATASET.register_module()
class TeleQuADDataset(BaseDataset):

    @staticmethod
    def load(path: str, file_name: str = None, **kwargs):
        raw_data = []

        # Walk through the directory to find JSON files
        for root, dirs, files in os.walk(path):
            for file in files:
                if not file.endswith('.json') and not file.endswith('.jsonl'):
                    continue
                file_path = os.path.join(root, file)
                try:
                    data = load_json_or_jsonl(file_path)
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
                    continue

                # Case 1: Extractive (SQuAD-like format)
                # Structure: data -> paragraphs -> qas -> question, answers
                if isinstance(data, list) and "data" in data[0] and "paragraphs" in data[0]["data"][0]:
                    data = data[0]
                    for article in data["data"]:
                        if "paragraphs" not in article:
                            continue
                        for p in article["paragraphs"]:
                            if "qas" not in p:
                                continue
                            for qa in p["qas"]:
                                question = qa.get("question", "").strip()
                                answers = qa.get("answers", [])
                                if not question or not answers:
                                    continue
                                
                                # Take the first answer text
                                answer_text = answers[0].get("text", "").strip()
                                raw_data.append({
                                    "question": question,
                                    "answer": answer_text
                                })

                # Case 2: Tabular (Custom format)
                # Structure: data -> questions -> question, answer
                # NOTE: The provided sample showed data -> questions list inside data items, wait, let's re-verify the structure from view_file output.
                # The view_file output for tabular showed:
                # { "data": [ { "questions": [ { "question": ..., "answer": ... } ] } ] }
                # So it is data (list) -> item (dict) -> questions (list) -> item (dict) -> question, answer
                elif isinstance(data, list) and "data" in data[0] and  "questions" in data[0]["data"][0]:
                    data =data[0]
                    for item in data["data"]:
                        if "questions" not in item:
                            continue
                        for q_item in item["questions"]:
                            question = q_item.get("question", "").strip()
                            answer = q_item.get("answer", "").strip()
                            
                            if question and answer:
                                raw_data.append({
                                    "question": question,
                                    "answer": answer
                                })
                # 情况 3：扁平问答格式（Tele-Eval 风格）                
                elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "Statement" in data[0] and "Answer" in data[0]:
                    # 对象列表（可能来自 .json 文件）
                    for item in data:
                        question = item.get("Statement", "").strip()
                        answer = item.get("Answer", "").strip()
                        if question and answer:
                            raw_data.append({
                                "question": question,
                                "answer": answer
                            })
                elif isinstance(data, list):
                    for item in data:
                        question = item.get("question", "").strip()
                        answer = item.get("answer", "").strip()
                        if question and answer:
                            raw_data.append({
                                "question": question,
                                "answer": answer
                            })
        # --- 新增逻辑：处理数据量大于 10000 的情况 ---
        num_samples = len(raw_data)
        if num_samples > 10000:
            import random
            random.seed(42)  # 固定种子保证可复现
            random.shuffle(raw_data)  # 随机打乱
            raw_data = raw_data[:400] # 截取前 400 条
            logger.info(f"TeleQuAD dataset size {num_samples} > 10000, sampled 400 items.")
        # ----------------------------------------------
        dataset = Dataset.from_list(raw_data) 
        return dataset
