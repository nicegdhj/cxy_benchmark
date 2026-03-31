import json
import os

from datasets import Dataset

from ais_bench.benchmark.registry import LOAD_DATASET
from ais_bench.benchmark.datasets.base import BaseDataset
from ais_bench.benchmark.datasets.utils.datasets import get_data_path
from ais_bench.benchmark.utils.logging.logger import AISLogger

logger = AISLogger()


@LOAD_DATASET.register_module()
class TeleExamDataset(BaseDataset):
    """
    Dataset class for 电信中级考试综合题（telecom-intermediate-exam）。

    数据路径结构：
        <path>/
            <year>/
                综合/
                    *.json   ← 本类只读取这层目录下的 JSON 文件

    每条 JSON 记录格式（flat list）：
        {
            "id": "1",
            "question": "题目文本\\nA.选项A\\nB.选项B\\nC.选项C\\nD.选项D",
            "answer": "A",
            "correct answer": ""   # 可忽略
        }

    加载后每条样本字段：
        question  (str) – 原始题目文本（含选项）
        answer    (str) – 正确答案字母（A/B/C/D）
        subdivision (str) – 当前 JSON 文件的文件名（无后缀）
    """

    @staticmethod
    def load(path: str, year: str, **kwargs):
        path = get_data_path(path)
        raw_data = []

        target_dir = os.path.join(path, year, '综合')
        if not os.path.isdir(target_dir):
            logger.warning(f'[TeleExamDataset] target dir does not exist: {target_dir}')
            return Dataset.from_list([])

        for file in sorted(os.listdir(target_dir)):
            if not file.endswith('.json'):
                continue

            file_path = os.path.join(target_dir, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f'[TeleExamDataset] Failed to load {file_path}: {e}')
                continue

            if not isinstance(data, list):
                logger.warning(f'[TeleExamDataset] Unexpected format in {file_path}, skipping.')
                continue

            for item in data:
                question = item.get('question', '').strip()
                # 优先使用 correct answer（若非空），否则使用 answer
                correct_answer = item.get('correct answer', '').strip()
                answer = item.get('answer', '').strip()
                final_answer = correct_answer if correct_answer else answer
                if not question or not final_answer:
                    continue
                raw_data.append({
                    'question': question,
                    'answer': final_answer,
                    'subdivision': file.replace('.json', ''),
                })

        if not raw_data:
            logger.warning(f'[TeleExamDataset] No data loaded for year {year}.')

        return Dataset.from_list(raw_data)


@LOAD_DATASET.register_module()
class TeleExamSubDataset(BaseDataset):
    """
    按子科目加载电信中级考试主观题数据集。

    数据路径结构：
        <path>/
            <year>/          ← 如 2022, 2023
                <name>/      ← 子科目文件夹名，如 互联网技术
                    *.json

    每条 JSON 记录格式（flat list）：
        {
            "id": "...",
            "question": "题目文本",
            "answer": "参考答案",
            "score": "3分",           # 可忽略
            "correct answer": "..."   # 以此为准（若非空则覆盖 answer）
        }

    加载后每条样本字段：
        question  (str) – 题目文本
        answer    (str) – 参考答案（优先使用 correct answer 字段，若为空则用 answer）

    参数：
        name (str) – 子科目文件夹名称，如 "互联网技术"
    """

    @staticmethod
    def load(path: str, name: str, **kwargs):
        path = get_data_path(path)
        raw_data = []

        if not os.path.isdir(path):
            logger.warning(f'[TeleExamSubDataset] path does not exist: {path}')
            return Dataset.from_list([])

        # 遍历所有年份目录
        for year_entry in sorted(os.scandir(path), key=lambda e: e.name):
            if not year_entry.is_dir():
                continue
            sub_dir = os.path.join(year_entry.path, name)
            if not os.path.isdir(sub_dir):
                # 该年份没有此子科目文件夹，跳过
                continue

            for file in sorted(os.listdir(sub_dir)):
                if not file.endswith('.json'):
                    continue
                file_path = os.path.join(sub_dir, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    logger.warning(f'[TeleExamSubDataset] Failed to load {file_path}: {e}')
                    continue

                if not isinstance(data, list):
                    logger.warning(f'[TeleExamSubDataset] Unexpected format in {file_path}, skipping.')
                    continue

                for item in data:
                    question = item.get('question', '').strip()
                    # 优先使用 correct answer（若非空）
                    answer = item.get('answer', '').strip() or item.get('correct answer', '').strip()
                    # 判题符号标准化
                    if answer == '×':
                        answer = '错误'
                    elif answer == '√':
                        answer = '正确'
                    if not question or not answer:
                        continue
                    
                    data_obj = {
                        'question': question,
                        'answer': answer,
                        'subdivision': file.replace('.json', ''),
                    }
                    if 'score' in item:
                        data_obj['score'] = item['score']
                        
                    raw_data.append(data_obj)

        if not raw_data:
            logger.warning(
                f'[TeleExamSubDataset] No data loaded for subcategory "{name}". '
                'Please check that the subfolder exists under each year directory.'
            )

        return Dataset.from_list(raw_data)
