from sqlalchemy.orm import Session

from backend.app.models import (
    Batch, BatchCell, BatchRevision, Job, Model, Task,
)


def _snapshot(db: Session, batch_id: int) -> dict:
    cells = db.query(BatchCell).filter_by(batch_id=batch_id).all()
    return {
        "cells": [
            {
                "model_id": c.model_id,
                "task_id": c.task_id,
                "dataset_version_id": c.dataset_version_id,
                "current_prediction_id": c.current_prediction_id,
                "current_evaluation_id": c.current_evaluation_id,
            }
            for c in cells
        ]
    }


def _next_rev_num(db: Session, batch_id: int) -> int:
    last = (
        db.query(BatchRevision.rev_num)
        .filter_by(batch_id=batch_id)
        .order_by(BatchRevision.rev_num.desc())
        .first()
    )
    return (last[0] + 1) if last else 1


def record_revision(
    db: Session, batch_id: int, change_type: str, change_summary: str,
    actor_user_id: int | None = None
):
    """
    记录 BatchRevision 快照。

    **调用顺序要求**：调用方须在修改 BatchCell 指针后（db.flush 后）、
    db.commit 前调用本函数。_snapshot 读取的是 session 内当前 cell 状态，
    而非数据库已提交状态。勿在 cell 修改前调用，否则快照不准确。
    """
    rev = BatchRevision(
        batch_id=batch_id,
        rev_num=_next_rev_num(db, batch_id),
        change_type=change_type,
        change_summary=change_summary,
        snapshot_json=_snapshot(db, batch_id),
        actor_user_id=actor_user_id,
    )
    db.add(rev)


def rerun_batch(db: Session, batch_id: int, payload,
                actor_user_id: int | None = None) -> list[Job]:
    """为 batch 的指定子集创建新 jobs，返回新创建的 job 列表。"""
    batch = db.get(Batch, batch_id)
    if not batch:
        raise ValueError("batch not found")

    jobs_created = []
    for mid in payload.model_ids:
        for tid in payload.task_ids:
            cell = db.get(BatchCell, (batch_id, mid, tid))
            if not cell:
                raise ValueError(f"cell not found for model={mid} task={tid}")

            if payload.dataset_version_id is not None:
                cell.dataset_version_id = payload.dataset_version_id

            infer_job = None
            if payload.what in ("infer", "both"):
                infer_job = Job(
                    type="infer", batch_id=batch_id,
                    model_id=mid, task_id=tid,
                    params_json={},
                )
                db.add(infer_job)
                db.flush()
                jobs_created.append(infer_job)

            if payload.what in ("eval", "both"):
                dep_id = infer_job.id if infer_job else None
                # eval-only 时尝试用现有 prediction 作为依赖
                if payload.what == "eval" and cell.current_prediction_id:
                    # eval job 不需要 infer job 依赖，但需要 prediction 存在
                    # 这里保持和 create_batch 相同的结构：eval job 的 dependency 指向 infer
                    # 但 rerun 中 infer 可能不存在，所以 dependency_job_id 设为 None
                    dep_id = None

                eval_job = Job(
                    type="eval", batch_id=batch_id,
                    model_id=mid, task_id=tid,
                    params_json={"eval_version": batch.default_eval_version},
                    dependency_job_id=dep_id,
                )
                db.add(eval_job)
                db.flush()
                jobs_created.append(eval_job)

    record_revision(
        db, batch_id, "rerun",
        f"rerun {payload.what} for models={payload.model_ids} tasks={payload.task_ids}",
        actor_user_id=actor_user_id,
    )
    return jobs_created


def create_batch(db: Session, payload,
                 actor_user_id: int | None = None) -> Batch:
    # 校验 model/task 存在
    models = db.query(Model).filter(Model.id.in_(payload.model_ids)).all()
    if len(models) != len(payload.model_ids):
        raise ValueError("some model_id not found")
    tasks = db.query(Task).filter(Task.id.in_(payload.task_ids)).all()
    if len(tasks) != len(payload.task_ids):
        raise ValueError("some task_id not found")

    batch = Batch(
        name=payload.name,
        mode=payload.mode,
        default_eval_version=payload.default_eval_version,
        default_judge_id=payload.default_judge_id,
        notes=payload.notes,
        created_by_user_id=actor_user_id,
        last_modified_by_user_id=actor_user_id,
    )
    db.add(batch)
    db.flush()

    # 生成 N×M 个 cells
    for m in models:
        for t in tasks:
            db.add(BatchCell(
                batch_id=batch.id, model_id=m.id, task_id=t.id,
            ))
    db.flush()

    # 生成 jobs
    for m in models:
        for t in tasks:
            infer_job = None
            if payload.mode in ("infer", "all"):
                infer_job = Job(
                    type="infer", batch_id=batch.id,
                    model_id=m.id, task_id=t.id,
                    params_json={},
                    created_by_user_id=actor_user_id,
                )
                db.add(infer_job)
                db.flush()
            if payload.mode in ("eval", "all"):
                eval_job = Job(
                    type="eval", batch_id=batch.id,
                    model_id=m.id, task_id=t.id,
                    params_json={"eval_version": batch.default_eval_version},
                    dependency_job_id=infer_job.id if infer_job else None,
                    created_by_user_id=actor_user_id,
                )
                db.add(eval_job)

    record_revision(db, batch.id, "create", f"create batch '{batch.name}'",
                    actor_user_id=actor_user_id)
    return batch