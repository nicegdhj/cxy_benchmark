"""
ExamDynamicEvaluator — 多题型动态评估器

根据每道题的 type 字段进行动态路由评分：
  - fill_blank    : 使用 MATHEvaluator 内部的 parse/verify 判断正确性（全对/全错）
  - multiple_choice: 提取模型输出的选项与标准答案做完整匹配（兼容多选）
  - subjective    : 调用 LLMJudgeEvaluator 获取连续得分；
                    当 has_image=True 或 need_plot=True 时跳过，不计入分母

以试卷（subdivision）为维度聚合：
  paper_score = sum(got_scores) / sum(active_max_scores) * 100
"""

import re
from collections import defaultdict
from typing import List

from datasets import Dataset

from ais_bench.benchmark.registry import ICL_EVALUATORS
from ais_bench.benchmark.openicl.icl_evaluator.icl_base_evaluator import BaseEvaluator
from ais_bench.benchmark.utils.logging.logger import AISLogger

logger = AISLogger()


# ────────────────────────────────────────────────────────────
# 内部工具函数
# ────────────────────────────────────────────────────────────


def _extract_choices(text: str, expected_len: int = 1) -> str:
    """从模型输出文本中提取选项字母，支持多空顺序匹配。"""
    upper = text.upper()

    # 1. 优先使用中文"答案"关键词后面的选项
    cn_match = re.search(
        r"(?:答案|选项|选择)[是为选：:]*\s*([A-Z][A-Z、,，\s]*)",
        upper,
        re.IGNORECASE,
    )
    if cn_match:
        letters = re.findall(r"[A-Z]", cn_match.group(1))
        if letters:
            return "".join(letters[:expected_len])

    # 2. 英文 Answer/answer 关键词
    en_match = re.search(r"[Aa]nswer\s*[:：＝= ]\s*([A-Z][A-Z,\s]*)", upper)
    if en_match:
        letters = re.findall(r"[A-Z]", en_match.group(1))
        if letters:
            return "".join(letters[:expected_len])

    # 3. 找所有连续大写字母组（如 "AB"、"ACD"）
    all_groups = re.findall(r"[A-Z]{2,10}", upper)
    candidates = [g for g in all_groups if len(g) == expected_len]
    if candidates:
        return candidates[-1]

    # 4. 兜底：所有大写字母按序提取
    all_letters = re.findall(r"[A-Z]", upper)
    if all_letters:
        return "".join(all_letters[:expected_len])

    return ""


def _score_multiple_choice(prediction: str, reference: str) -> float:
    """判断选择题得分比例（按空顺序计分，支持多空独立计分）。"""
    expected = reference.strip().upper()
    if not expected:
        return 0.0
    extracted = _extract_choices(prediction, expected_len=len(expected))
    
    if not extracted:
        return 0.0

    match_count = sum(1 for p, e in zip(extracted, expected) if p == e)
    return float(match_count) / len(expected)


# ────────────────────────────────────────────────────────────
# 评估器主类
# ────────────────────────────────────────────────────────────


@ICL_EVALUATORS.register_module()
class ExamDynamicEvaluator(BaseEvaluator):
    """多题型动态评估器，以试卷为维度汇总得分。

    Args:
        llm_judge_kwargs (dict): 传递给 LLMJudgeEvaluator 的额外构造参数，
            如 ``prompt_template``。默认为空字典。
    """

    def __init__(self, llm_judge_kwargs: dict = None, **kwargs):
        super().__init__()
        self._llm_judge_kwargs = llm_judge_kwargs or {}
        self._llm_judge = None  # 懒加载，仅在存在主观题时初始化
        self._math_evaluator = None  # 懒加载，仅在存在填空题时初始化

    # ── 懒加载 Evaluators ─────────────────────────────

    def _get_llm_judge(self):
        if self._llm_judge is None:
            from ais_bench.benchmark.openicl.icl_evaluator.llm_judge_evaluator import (
                LLMJudgeEvaluator,
            )
            self._llm_judge = LLMJudgeEvaluator(**self._llm_judge_kwargs)
        return self._llm_judge

    def _get_math_evaluator(self):
        if self._math_evaluator is None:
            from ais_bench.benchmark.openicl.icl_evaluator.math_evaluator import (
                MATHEvaluator,
            )
            self._math_evaluator = MATHEvaluator()
        return self._math_evaluator

    # ── score() —— 单道题评分（供外部或测试直接调用）───────────────

    def score(self, predictions: List[str], references: List[str],
              test_set: Dataset = None) -> dict:
        """逐题评分，返回 details 列表。

        每条 detail：
            pred          (str)   – 后处理后的预测
            answer        (str)   – 标准答案
            type          (str)   – 题型
            item_score    (float) – 本题满分
            got_score     (float) – 本题得分
            skipped       (bool)  – 是否被跳过（不计入分母）
            correct       (bool)  – 是否完全正确（选择/填空用）
        """
        details = []

        # 存放占位索引，稍后批量送给对应 Evaluator
        subjective_indices = []  # (detail_index, pred, ref, item_score)
        fill_blank_indices = []  # (detail_index, pred, ref, item_score)

        for i, (pred, ref) in enumerate(zip(predictions, references)):
            item_score = 1.0
            q_type = "multiple_choice"
            has_image = False
            need_plot = False

            if test_set is not None and i < len(test_set):
                example = test_set[i]
                item_score = float(example.get("score", 1.0))
                q_type = example.get("type", "multiple_choice")
                has_image = bool(example.get("has_image", False))
                need_plot = bool(example.get("need_plot", False))

            detail = {
                "pred": pred,
                "answer": ref,
                "type": q_type,
                "item_score": item_score,
                "got_score": 0.0,
                "skipped": False,
                "correct": False,
            }

            if q_type == "fill_blank":
                p_clean = pred.strip()
                r_clean = ref.strip()
                
                # 快速通道：如果去空格后完全一致，直接判对（防止底层模型解析引擎无法识别特定符号导致全错）
                if p_clean == r_clean or p_clean.replace(" ", "") == r_clean.replace(" ", ""):
                    detail["correct"] = True
                    detail["got_score"] = item_score
                else:
                    detail["_pending_math"] = True
                    fill_blank_indices.append((len(details), pred, ref, item_score))

            elif q_type == "multiple_choice":
                ratio = _score_multiple_choice(pred, ref)
                detail["correct"] = (ratio == 1.0)
                detail["got_score"] = item_score * ratio

            elif q_type == "subjective":
                if has_image or need_plot:
                    # 跳过：不计入分母
                    detail["skipped"] = True
                    detail["got_score"] = 0.0
                else:
                    # 标记占位，稍后批量 LLM 评分
                    detail["_pending_llm"] = True
                    subjective_indices.append((len(details), pred, ref, item_score))
            else:
                logger.warning(
                    f"[ExamDynamicEvaluator] Unknown question type '{q_type}' at index {i}, "
                    "treating as skipped."
                )
                detail["skipped"] = True

            details.append(detail)

        # 批量处理填空题 (使用 MATHEvaluator)
        if fill_blank_indices:
            def _wrap_math_pred(p: str) -> str:
                p = p.strip()
                if not p:
                    return p
                # 在 MATHEvaluator 的 LatexExtractionConfig(try_extract_without_anchor=False)
                # 配置下，必须使用 \boxed{...} 才能被当作答案提取。$...$ 是不识别的。
                if "$" not in p and "\\boxed" not in p and "\\[" not in p and "\\(" not in p:
                    # 强行套上 \boxed，以便复用底层而不用修改它
                    return f"\\boxed{{{p}}}"
                return p

            math_preds = [_wrap_math_pred(t[1]) for t in fill_blank_indices]
            math_refs = [t[2] for t in fill_blank_indices]

            try:
                math_ev = self._get_math_evaluator()
                math_result = math_ev.score(math_preds, math_refs)
                math_details = math_result.get("details", [])

                for (detail_idx, _, _, item_score_), md in zip(
                    fill_blank_indices, math_details
                ):
                    correct = md.get("correct", False)
                    details[detail_idx]["correct"] = correct
                    details[detail_idx]["got_score"] = item_score_ if correct else 0.0
                    details[detail_idx].pop("_pending_math", None)
            except Exception as e:
                logger.warning(
                    f"[ExamDynamicEvaluator] MATHEvaluator failed: {e}. "
                    "Falling back to exact string match."
                )
                for detail_idx, p, r, item_score_ in fill_blank_indices:
                    correct = p.strip() == r.strip()
                    details[detail_idx]["correct"] = correct
                    details[detail_idx]["got_score"] = item_score_ if correct else 0.0
                    details[detail_idx].pop("_pending_math", None)

        # 批量处理主观题
        if subjective_indices:
            sub_preds = [t[1] for t in subjective_indices]
            sub_refs = [t[2] for t in subjective_indices]
            sub_scores_max = [t[3] for t in subjective_indices]

            try:
                judge = self._get_llm_judge()
                # 构造临时 Dataset 供 LLMJudgeEvaluator 读取 score 字段
                import datasets as hf_datasets
                tmp_ds = hf_datasets.Dataset.from_list(
                    [{"score": str(s)} for s in sub_scores_max]
                )
                judge_result = judge.score(
                    predictions=sub_preds,
                    references=sub_refs,
                    test_set=tmp_ds,
                )
                judge_details = judge_result.get("details", [])

                for (detail_idx, _, _, item_score_), jd in zip(
                    subjective_indices, judge_details
                ):
                    llm_score = jd.get("llm_score", 0.0)
                    details[detail_idx]["got_score"] = llm_score
                    details[detail_idx]["llm_judge_output"] = jd.get("judge_output", "")
                    details[detail_idx].pop("_pending_llm", None)

            except Exception as e:
                logger.warning(
                    f"[ExamDynamicEvaluator] LLM judge failed: {e}. "
                    "Subjective questions will get 0 score."
                )
                for detail_idx, _, _, _ in subjective_indices:
                    details[detail_idx].pop("_pending_llm", None)
                    details[detail_idx]["got_score"] = 0.0
                    details[detail_idx]["llm_error"] = str(e)

        return {"details": details}

    # ── evaluate() —— 整体评估入口 ──────────────────────────────

    def evaluate(self, k, n, original_dataset: Dataset, **score_kwargs) -> dict:
        """重写 evaluate()，在 score() 结果基础上按试卷维度聚合得分。"""

        predictions = score_kwargs.get("predictions", [])
        references = score_kwargs.get("references", [])

        # pred 后处理（如有配置）
        predictions = self.pred_postprocess(predictions)

        # 调用 score()
        score_result = self.score(
            predictions=predictions,
            references=references,
            test_set=original_dataset,
        )

        details = score_result.get("details", [])

        # 补充 example_abbr、subdivision 元信息
        paper_got = defaultdict(float)   # subdivision → 已得分总和
        paper_max = defaultdict(float)   # subdivision → 参与评估的满分总和

        for i, detail in enumerate(details):
            subdiv = "unknown"
            idx = i
            if i < len(original_dataset):
                example = original_dataset[i]
                subdiv = example.get("subdivision", "unknown")
                idx = example.get("idx", i)
            detail["example_abbr"] = f"{subdiv}_{idx}"

            if not detail.get("skipped", False):
                paper_got[subdiv] += detail.get("got_score", 0.0)
                paper_max[subdiv] += detail.get("item_score", 1.0)
            got_score = detail.get("got_score", 0.0)
            res_tag = "✅ PASS" if got_score > 0 else "❌ FAIL"
            p_str = predictions[i][:50].replace('\n', ' ')
            g_str = references[i][:50].replace('\n', ' ')

            # 核心日志行
            logger.info(
                f"{detail['example_abbr']:<25} | "
                f"{res_tag:<7} | "
                f"{got_score:<5} | "
                f"Pred: [{p_str}] vs Gold: [{g_str}]"
            )
        # 按试卷聚合得分
        eval_results = {}
        all_got = 0.0
        all_max = 0.0

        for subdiv in sorted(paper_max.keys()):
            got = paper_got[subdiv]
            max_score = paper_max[subdiv]
            if max_score > 0:
                pct = (got / max_score) * 100
            else:
                pct = 0.0
            logger.info(f"Summary [{subdiv}]: Score: {got}/{max_score} ({pct:.2f}%)")
            all_got += got
            all_max += max_score

        # 全局汇总
        if all_max > 0:
            eval_results["overall_score_percentage"] = round(
                (all_got / all_max) * 100, 2
            )
        else:
            eval_results["overall_score_percentage"] = 0.0

        eval_results["details"] = details
        return eval_results
