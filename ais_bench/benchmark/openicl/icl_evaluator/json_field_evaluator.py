# -*- coding: utf-8 -*-
"""
JSON 字段级评估器

支持对 JSON 结构化输出进行灵活的字段级评估：
1. 精确匹配字段（EM）
2. 值匹配字段（忽略键名，只比较值）
3. 部分匹配字段（包含关系）
4. ROUGE 匹配字段（基于分词的相似度，适合中文文本）
5. 嵌套结构支持
"""

import json
import re
import warnings
from typing import List, Dict, Any, Optional, Union

# 延迟导入 jieba 和 rouge，避免启动时的警告
_jieba = None
_Rouge = None


def _get_jieba():
    global _jieba
    if _jieba is None:
        warnings.filterwarnings(
            "ignore", message=".*pkg_resources is deprecated.*", category=UserWarning
        )
        import jieba

        _jieba = jieba
    return _jieba


def _get_rouge():
    global _Rouge
    if _Rouge is None:
        from rouge_chinese import Rouge

        _Rouge = Rouge
    return _Rouge


from ais_bench.benchmark.registry import ICL_EVALUATORS
from ais_bench.benchmark.openicl.icl_evaluator.icl_base_evaluator import BaseEvaluator


def safe_parse_json(text: str) -> Optional[Dict]:
    """安全解析 JSON，支持多种格式"""
    if not text:
        return None

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 块（可能被其他文本包裹）
    json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
    matches = re.findall(json_pattern, text, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    return None


def extract_all_values(obj: Any, values: set = None) -> set:
    """递归提取 JSON 中所有的值（非键）"""
    if values is None:
        values = set()

    if isinstance(obj, dict):
        for v in obj.values():
            extract_all_values(v, values)
    elif isinstance(obj, list):
        for item in obj:
            extract_all_values(item, values)
    elif isinstance(obj, str):
        parsed = safe_parse_json(obj)
        if parsed is not None and isinstance(parsed, (dict, list)):
            extract_all_values(parsed, values)
        else:
            values.add(obj.strip().lower())
    elif obj is not None:
        values.add(str(obj).strip().lower())

    return values


def compare_values_flexible(pred_val: Any, gold_val: Any) -> float:
    """灵活比较两个值，返回相似度 0-1"""
    if pred_val == gold_val:
        return 1.0

    pred_str = str(pred_val).strip().lower()
    gold_str = str(gold_val).strip().lower()

    if pred_str == gold_str:
        return 1.0

    # 部分包含
    if gold_str in pred_str or pred_str in gold_str:
        return 0.8

    return 0.0


def compare_values_rouge(pred_val: Any, gold_val: Any) -> float:
    """使用 ROUGE-L 评分中文文本相似度，返回 0-1

    适用于需要精确评估文本重合度的场景（如引用原文片段）
    """
    pred_str = str(pred_val).strip()
    gold_str = str(gold_val).strip()

    # 完全相等
    if pred_str == gold_str:
        return 1.0

    # 空字符串处理
    if not pred_str or not gold_str:
        return 0.0

    try:
        jieba = _get_jieba()
        Rouge = _get_rouge()

        # 分词
        pred_tokens = " ".join(jieba.cut(pred_str))
        gold_tokens = " ".join(jieba.cut(gold_str))

        # 避免空串错误
        if not pred_tokens.strip():
            pred_tokens = "__PRED__"
        if not gold_tokens.strip():
            gold_tokens = "__GOLD__"

        # 计算 ROUGE-L F1 分数
        rouge = Rouge()
        scores = rouge.get_scores([pred_tokens], [gold_tokens])
        rouge_l_f1 = scores[0]["rouge-l"]["f"]

        return float(rouge_l_f1)

    except Exception:
        # 如果 ROUGE 计算失败，回退到 flexible 模式
        return compare_values_flexible(pred_val, gold_val)


@ICL_EVALUATORS.register_module()
class JsonFieldEvaluator(BaseEvaluator):
    """
    JSON 字段级评估器

    配置示例：
    ```python
    evaluator=dict(
        type=JsonFieldEvaluator,
        field_config={
            "业务类别": {"match_type": "exact", "weight": 1.0},
            "信息提取": {"match_type": "value_only", "weight": 1.0},
        },
        default_match_type="exact",
    )
    ```

    match_type 选项：
    - "exact": 精确匹配（键和值都必须完全一致）
    - "value_only": 只比较值（忽略键名差异）
    - "contains": 包含匹配（pred 包含 gold）
    - "flexible": 灵活匹配（支持部分匹配）

    strict_mode：
    - False（默认）：各字段加权平均，支持部分得分
    - True：AND 逻辑，所有参评字段（weight > 0）都必须精确匹配才算正确，
      否则整个样本得 0 分。weight=0 的字段不参与评分。
    """

    def __init__(
        self,
        field_config: Dict[str, Dict] = None,
        default_match_type: str = "exact",
        return_details: bool = False,
        strict_mode: bool = False,
    ) -> None:
        super().__init__()
        self.field_config = field_config or {}
        self.default_match_type = default_match_type
        self.return_details = return_details
        self.strict_mode = strict_mode

    def _get_field_config(self, field_name: str) -> Dict:
        """获取字段配置，不存在则返回默认值"""
        return self.field_config.get(
            field_name, {"match_type": self.default_match_type, "weight": 1.0}
        )

    def _compare_field(self, pred_val: Any, gold_val: Any, match_type: str) -> float:
        """比较单个字段，返回分数 0-1"""

        if match_type == "exact":
            if pred_val == gold_val:
                return 1.0
            # 类型不同但字符串表示相同（如 3 vs "3"）视为匹配
            if str(pred_val).strip() == str(gold_val).strip():
                return 1.0
            return 0.0

        elif match_type == "value_only":
            # 对于嵌套结构，提取所有值进行比较
            if isinstance(gold_val, (dict, list)) and isinstance(
                pred_val, (dict, list)
            ):
                gold_values = extract_all_values(gold_val)
                pred_values = extract_all_values(pred_val)
                if not gold_values:
                    return 1.0 if not pred_values else 0.0
                overlap = len(gold_values & pred_values)
                return overlap / len(gold_values)
            else:
                return 1.0 if str(pred_val) == str(gold_val) else 0.0

        elif match_type == "contains":
            gold_str = str(gold_val)
            pred_str = str(pred_val)
            return 1.0 if gold_str in pred_str else 0.0

        elif match_type == "flexible":
            return compare_values_flexible(pred_val, gold_val)

        elif match_type == "rouge":
            return compare_values_rouge(pred_val, gold_val)

        else:
            # 默认精确匹配
            return 1.0 if pred_val == gold_val else 0.0

    def _evaluate_single(self, pred: str, gold: str) -> Dict[str, float]:
        """评估单个样本"""
        pred_json = safe_parse_json(pred)
        gold_json = safe_parse_json(gold)

        # 如果解析失败，使用字符串精确匹配
        if pred_json is None or gold_json is None:
            return {
                "accuracy": 1.0 if pred.strip() == gold.strip() else 0.0,
                "parse_success": 0.0,
            }

        # 计算各字段分数
        total_weight = 0.0
        weighted_score = 0.0
        field_scores = {}

        if isinstance(gold_json, dict):
            for field_name, gold_value in gold_json.items():
                config = self._get_field_config(field_name)
                match_type = config.get("match_type", self.default_match_type)
                weight = config.get("weight", 1.0)

                # strict_mode 下 weight=0 的字段不参与评分
                if self.strict_mode and weight == 0:
                    continue

                pred_value = (
                    pred_json.get(field_name) if isinstance(pred_json, dict) else None
                )

                if pred_value is None:
                    score = 0.0
                else:
                    score = self._compare_field(pred_value, gold_value, match_type)

                field_scores[field_name] = score
                weighted_score += score * weight
                total_weight += weight
        else:
            # 如果 gold_json 不是字典，将其作为一个整体进行比较
            match_type = self.default_match_type
            score = self._compare_field(pred_json, gold_json, match_type)
            result = {
                "accuracy": score,
                "parse_success": 1.0,
            }
            if self.return_details:
                result["field_scores"] = {"__overall__": score}
            return result

        if self.strict_mode:
            # AND 逻辑：所有参评字段都必须得 1.0，否则整体为 0
            overall_score = 1.0 if (field_scores and all(s == 1.0 for s in field_scores.values())) else 0.0
        else:
            overall_score = weighted_score / total_weight if total_weight > 0 else 0.0

        result = {
            "accuracy": overall_score,
            "parse_success": 1.0,
        }

        if self.return_details:
            result["field_scores"] = field_scores

        return result

    def score(self, predictions: List, references: List) -> Dict:
        """评估所有样本"""
        if len(predictions) != len(references):
            return {
                "error": f"predictions and references have different length. "
                f"len(predictions): {len(predictions)}, "
                f"len(references): {len(references)}"
            }

        total_accuracy = 0.0
        total_parse_success = 0.0
        all_field_scores = {}
        details = []

        for pred, gold in zip(predictions, references):
            result = self._evaluate_single(str(pred), str(gold))
            total_accuracy += result["accuracy"]
            total_parse_success += result.get("parse_success", 1.0)

            detail_item = {
                "pred": pred,
                "answer": gold,
            }
            if result["accuracy"] == 1.0:
                detail_item["eval_res"] = True
            elif result["accuracy"] == 0.0:
                detail_item["eval_res"] = False
            else:
                detail_item["eval_res"] = str(round(result["accuracy"] * 100, 2))

            detail_item["eval_details"] = None

            if self.return_details and "field_scores" in result:
                detail_item["eval_details"] = result["field_scores"]
                for field, score in result["field_scores"].items():
                    if field not in all_field_scores:
                        all_field_scores[field] = []
                    all_field_scores[field].append(score)

            details.append(detail_item)

        n = len(predictions)
        final_result = {
            "accuracy": (total_accuracy / n) * 100 if n > 0 else 0.0,
            "parse_success_rate": (total_parse_success / n) * 100 if n > 0 else 0.0,
            "details": details,
        }

        # 添加每个字段的平均分
        if all_field_scores:
            for field, scores in all_field_scores.items():
                final_result[f"field_{field}"] = (sum(scores) / len(scores)) * 100

        return final_result


@ICL_EVALUATORS.register_module()
class JsonValueMatchEvaluator(JsonFieldEvaluator):
    """
    JSON 值匹配评估器（简化版）

    默认行为：
    - 第一层字段使用精确匹配
    - 嵌套结构使用值匹配（忽略键名）

    适用于 task_1 这类场景：业务类别精确匹配，信息提取只比较值
    """

    def __init__(
        self,
        exact_fields: List[str] = None,
        value_only_fields: List[str] = None,
        **kwargs,
    ) -> None:
        # 构建 field_config
        field_config = {}

        for field in exact_fields or []:
            field_config[field] = {"match_type": "exact", "weight": 1.0}

        for field in value_only_fields or []:
            field_config[field] = {"match_type": "value_only", "weight": 1.0}

        super().__init__(
            field_config=field_config, default_match_type="exact", **kwargs
        )


# 为 task_1 类型任务预置的评估器
@ICL_EVALUATORS.register_module()
class BusinessClassificationEvaluator(JsonFieldEvaluator):
    """
    业务分类任务评估器

    专门用于评估包含 "业务类别" 和 "信息提取" 的 JSON 输出：
    - 业务类别：精确匹配
    - 信息提取：值匹配（忽略键名差异）
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(
            field_config={
                "业务类别": {"match_type": "exact", "weight": 1.0},
                "信息提取": {"match_type": "value_only", "weight": 1.0},
            },
            default_match_type="flexible",
            return_details=True,
            **kwargs,
        )
