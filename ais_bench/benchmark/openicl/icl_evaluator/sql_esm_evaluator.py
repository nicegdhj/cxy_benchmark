# -*- coding: utf-8 -*-
"""
SQL Exact Set Match (ESM) 评估器

将 SQL 语句拆解为各子句（SELECT/FROM/WHERE/GROUP BY/ORDER BY），
在每个子句内进行集合比较（无序），忽略格式差异。
"""

import re
from typing import List, Dict, Set, Optional

from ais_bench.benchmark.registry import ICL_EVALUATORS
from ais_bench.benchmark.openicl.icl_evaluator.icl_base_evaluator import BaseEvaluator


def normalize_sql(sql: str) -> str:
    """标准化 SQL 字符串"""
    if not sql:
        return ""
    # 去除首尾空白和分号
    sql = sql.strip().rstrip(';').strip()
    # 去除 ```sql ``` 包裹
    sql = re.sub(r'^```\s*sql\s*', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\s*```\s*$', '', sql)
    # 统一空白符
    sql = re.sub(r'\s+', ' ', sql)
    return sql.strip()


def extract_clauses(sql: str) -> Dict[str, str]:
    """
    从 SQL 中提取各子句内容
    
    返回: {"select": "...", "from": "...", "where": "...", ...}
    """
    sql = normalize_sql(sql)
    if not sql:
        return {}
    
    # 定义子句关键字及其顺序
    clause_keywords = [
        'SELECT', 'FROM', 'WHERE',
        'GROUP BY', 'HAVING',
        'ORDER BY', 'LIMIT'
    ]
    
    # 构建正则匹配各子句的位置
    positions = []
    sql_upper = sql.upper()
    
    for keyword in clause_keywords:
        # 查找关键字位置（需要是独立单词）
        pattern = r'\b' + keyword.replace(' ', r'\s+') + r'\b'
        match = re.search(pattern, sql_upper)
        if match:
            positions.append((match.start(), keyword, match.end()))
    
    # 按位置排序
    positions.sort(key=lambda x: x[0])
    
    clauses = {}
    for i, (start, keyword, content_start) in enumerate(positions):
        # 子句内容到下一个子句开始或字符串末尾
        if i + 1 < len(positions):
            end = positions[i + 1][0]
        else:
            end = len(sql)
        
        content = sql[content_start:end].strip()
        clauses[keyword.lower().replace(' ', '_')] = content
    
    return clauses


def parse_select_columns(select_str: str) -> Set[str]:
    """解析 SELECT 子句中的列名集合"""
    if not select_str:
        return set()
    
    # 按逗号分割，标准化每个列
    columns = set()
    depth = 0
    current = []
    
    for char in select_str:
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            col = ''.join(current).strip()
            if col:
                columns.add(normalize_column(col))
            current = []
        else:
            current.append(char)
    
    # 最后一个列
    col = ''.join(current).strip()
    if col:
        columns.add(normalize_column(col))
    
    return columns


def normalize_column(col: str) -> str:
    """标准化列名：去反引号、统一大小写"""
    col = col.strip()
    col = col.replace('`', '')
    col = re.sub(r'\s+', ' ', col)
    return col.upper()


def parse_from_tables(from_str: str) -> Set[str]:
    """解析 FROM 子句中的表名集合"""
    if not from_str:
        return set()
    
    tables = set()
    # 简单处理：按逗号和 JOIN 分割
    parts = re.split(r',|\bJOIN\b', from_str, flags=re.IGNORECASE)
    for part in parts:
        part = part.strip()
        # 去掉 ON 条件
        part = re.split(r'\bON\b', part, flags=re.IGNORECASE)[0].strip()
        # 去掉别名
        tokens = part.split()
        if tokens:
            table = tokens[0].replace('`', '').upper()
            if table and table not in ('LEFT', 'RIGHT', 'INNER', 'OUTER', 'CROSS'):
                tables.add(table)
    
    return tables


def parse_where_conditions(where_str: str) -> Set[str]:
    """解析 WHERE 子句中的条件集合"""
    if not where_str:
        return set()
    
    # 按 AND/OR 分割条件
    conditions = set()
    parts = re.split(r'\bAND\b|\bOR\b', where_str, flags=re.IGNORECASE)
    
    for part in parts:
        cond = part.strip()
        cond = cond.strip('()')
        cond = cond.strip()
        if cond:
            # 标准化：去反引号、统一空白
            cond = cond.replace('`', '')
            cond = re.sub(r'\s+', ' ', cond).strip()
            conditions.add(cond.upper())
    
    return conditions


def sql_exact_set_match(pred_sql: str, gold_sql: str) -> Dict[str, float]:
    """
    计算两条 SQL 的 Exact Set Match 得分
    
    返回: 各子句的匹配分数和总分
    """
    pred_clauses = extract_clauses(pred_sql)
    gold_clauses = extract_clauses(gold_sql)
    
    scores = {}
    
    # 1. SELECT 子句比较
    pred_cols = parse_select_columns(pred_clauses.get('select', ''))
    gold_cols = parse_select_columns(gold_clauses.get('select', ''))
    scores['select'] = 1.0 if pred_cols == gold_cols else 0.0
    
    # 2. FROM 子句比较
    pred_tables = parse_from_tables(pred_clauses.get('from', ''))
    gold_tables = parse_from_tables(gold_clauses.get('from', ''))
    scores['from'] = 1.0 if pred_tables == gold_tables else 0.0
    
    # 3. WHERE 子句比较
    pred_conds = parse_where_conditions(pred_clauses.get('where', ''))
    gold_conds = parse_where_conditions(gold_clauses.get('where', ''))
    if not gold_conds and not pred_conds:
        scores['where'] = 1.0
    elif not gold_conds or not pred_conds:
        scores['where'] = 0.0
    else:
        scores['where'] = 1.0 if pred_conds == gold_conds else 0.0
    
    # 4. GROUP BY 比较
    pred_gb = pred_clauses.get('group_by', '')
    gold_gb = gold_clauses.get('group_by', '')
    if not gold_gb and not pred_gb:
        scores['group_by'] = 1.0
    else:
        pred_gb_set = {c.strip().upper().replace('`', '') for c in pred_gb.split(',') if c.strip()}
        gold_gb_set = {c.strip().upper().replace('`', '') for c in gold_gb.split(',') if c.strip()}
        scores['group_by'] = 1.0 if pred_gb_set == gold_gb_set else 0.0
    
    # 5. ORDER BY 比较（顺序敏感）
    pred_ob = pred_clauses.get('order_by', '').upper().replace('`', '')
    gold_ob = gold_clauses.get('order_by', '').upper().replace('`', '')
    pred_ob = re.sub(r'\s+', ' ', pred_ob).strip()
    gold_ob = re.sub(r'\s+', ' ', gold_ob).strip()
    if not gold_ob and not pred_ob:
        scores['order_by'] = 1.0
    else:
        scores['order_by'] = 1.0 if pred_ob == gold_ob else 0.0
    
    # 总分 = 各子句权重平均（只计算标准答案中存在的子句）
    active_clauses = [k for k in scores if scores[k] is not None]
    total = sum(scores[k] for k in active_clauses)
    count = len(active_clauses)
    scores['overall'] = total / count if count > 0 else 0.0
    
    # 完全匹配 = 所有子句都匹配
    scores['exact_match'] = 1.0 if all(scores[k] == 1.0 for k in active_clauses) else 0.0
    
    return scores


@ICL_EVALUATORS.register_module()
class SqlExactSetMatchEvaluator(BaseEvaluator):
    """
    SQL Exact Set Match 评估器
    
    将 SQL 拆解为子句，在每个子句内进行集合比较。
    忽略列顺序、条件顺序、格式差异。
    
    输出指标：
    - accuracy: 完全匹配的比例（所有子句都匹配）
    - clause_score: 子句级平均分
    - select_match: SELECT 子句匹配率
    - where_match: WHERE 子句匹配率
    """
    
    def __init__(self) -> None:
        super().__init__()
    
    def score(self, predictions: List, references: List) -> dict:
        if len(predictions) != len(references):
            return {
                'error': f'predictions and references have different length. '
                         f'len(predictions): {len(predictions)}, '
                         f'len(references): {len(references)}'
            }
        
        total_exact = 0
        total_clause = 0.0
        total_select = 0.0
        total_from = 0.0
        total_where = 0.0
        n = len(predictions)
        
        for pred, gold in zip(predictions, references):
            scores = sql_exact_set_match(str(pred), str(gold))
            total_exact += scores['exact_match']
            total_clause += scores['overall']
            total_select += scores.get('select', 0)
            total_from += scores.get('from', 0)
            total_where += scores.get('where', 0)
        
        return {
            'accuracy': (total_exact / n) * 100 if n > 0 else 0.0,
            'clause_score': (total_clause / n) * 100 if n > 0 else 0.0,
            'select_match': (total_select / n) * 100 if n > 0 else 0.0,
            'from_match': (total_from / n) * 100 if n > 0 else 0.0,
            'where_match': (total_where / n) * 100 if n > 0 else 0.0,
        }
