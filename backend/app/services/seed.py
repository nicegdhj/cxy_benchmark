import logging

from pathlib import Path
from sqlalchemy.orm import Session

from backend.app.models import Task


def _get_ais_bench_configs() -> Path:
    """Walk up from this file to find worktree root and derive AISBench configs path.

    seed.py is at: backend/app/services/seed.py
    worktree root is at: backend/ (parent of backend/)
    configs are at: worktree_root/../ais_bench/benchmark/configs/datasets
    """
    current = Path(__file__).resolve()
    # backend/app/services/seed.py -> backend/app/services -> backend/app -> backend/ -> eval-backend/
    for _ in range(4):  # safety limit
        current = current.parent
    worktree_root = current
    configs = worktree_root / "ais_bench" / "benchmark" / "configs" / "datasets"
    if not configs.exists():
        raise RuntimeError(
            f"AISBench configs not found at {configs}. "
            f"Expected from worktree root {worktree_root}"
        )
    return configs


def _detect_is_llm_judge(suite_name: str) -> bool:
    """扫描 suite 配置文件，判断是否使用 LLMJudgeEvaluator。"""
    configs = _get_ais_bench_configs()
    for py in configs.rglob(f"{suite_name}.py"):
        try:
            if "LLMJudgeEvaluator" in py.read_text(encoding="utf-8"):
                return True
        except (OSError, UnicodeDecodeError) as e:
            logging.warning(f"Failed to read {py}: {e}")
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
            is_llm_judge=False,  # custom tasks use AccEvaluator, not LLMJudgeEvaluator
        ))
