from pathlib import Path
from sqlalchemy.orm import Session

from backend.app.models import Task


AIS_BENCH_CONFIGS = Path(__file__).resolve().parents[3] / \
    "ais_bench" / "benchmark" / "configs" / "datasets"


def _detect_is_llm_judge(suite_name: str) -> bool:
    """扫描 suite 配置文件，判断是否使用 LLMJudgeEvaluator。"""
    for py in AIS_BENCH_CONFIGS.rglob(f"{suite_name}.py"):
        try:
            if "LLMJudgeEvaluator" in py.read_text(encoding="utf-8"):
                return True
        except Exception:
            pass
    return False


def seed_generic_tasks(session: Session, suite_names: list[str]):
    for suite in suite_names:
        if session.query(Task).filter_by(key=suite).first():
            continue
        session.add(Task(
            key=suite,
            type="generic",
            suite_name=suite,
            display_name=suite,
            is_llm_judge=_detect_is_llm_judge(suite),
        ))


def seed_custom_tasks(session: Session, task_nums: list[int]):
    for num in task_nums:
        key = f"task_{num}_suite"
        if session.query(Task).filter_by(key=key).first():
            continue
        session.add(Task(
            key=key,
            type="custom",
            suite_name=key,
            display_name=f"Custom Task {num}",
            custom_task_num=num,
            default_data_rel_path=f"data/custom_task/task_{num}.jsonl",
            is_llm_judge=_detect_is_llm_judge(key),
        ))
