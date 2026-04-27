from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.deps import db_session, require_role
from backend.app.models import (
    Batch, BatchCell, BatchRevision, Evaluation, Job, Model, Prediction, Task, User,
)
from backend.app.schemas import (
    BatchCreate, BatchOut, BatchReport, BatchReportRow, BatchRerun, BatchRevisionOut, CloneBatchIn,
)
from backend.app.services.batch_service import create_batch, rerun_batch


router = APIRouter(prefix="/api/v1/batches", tags=["batches"])


def _batch_status(db: Session, batch_id: int) -> str:
    """根据该批次下所有 Job 的状态汇总计算批次状态。"""
    rows = (
        db.query(Job.status, func.count())
        .filter(Job.batch_id == batch_id)
        .group_by(Job.status)
        .all()
    )
    if not rows:
        return "pending"
    counts = {s: c for s, c in rows}
    if counts.get("running", 0) > 0:
        return "running"
    total = sum(counts.values())
    if counts.get("success", 0) == total:
        return "success"
    if counts.get("pending", 0) == total:
        return "pending"
    if counts.get("failed", 0) + counts.get("cancelled", 0) > 0:
        return "failed"
    return "pending"


def _enrich_batch(db: Session, b: Batch) -> BatchOut:
    out = BatchOut.model_validate(b)
    out.status = _batch_status(db, b.id)
    return out


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create(payload: BatchCreate,
           db: Session = Depends(db_session),
           actor: User = Depends(require_role("operator", "admin"))):
    try:
        batch = create_batch(db, payload, actor_user_id=actor.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(batch)
    return _enrich_batch(db, batch)


@router.get("", response_model=list[BatchOut])
def list_(db: Session = Depends(db_session),
          _: User = Depends(require_role("viewer", "operator", "admin"))):
    batches = db.query(Batch).order_by(Batch.id.desc()).all()
    return [_enrich_batch(db, b) for b in batches]


@router.get("/{bid}", response_model=BatchOut)
def get(bid: int,
        db: Session = Depends(db_session),
        _: User = Depends(require_role("viewer", "operator", "admin"))):
    b = db.get(Batch, bid)
    if not b:
        raise HTTPException(status_code=404, detail=f"Batch {bid} not found")
    return _enrich_batch(db, b)


@router.get("/{bid}/report", response_model=BatchReport)
def report(bid: int, db: Session = Depends(db_session),
           rev: int | None = Query(None),
           _: User = Depends(require_role("viewer", "operator", "admin"))):
    batch = db.get(Batch, bid)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {bid} not found")

    # 历史 revision 模式（rev 指定时，基于快照还原战报）
    if rev is not None:
        snapshot_row = (
            db.query(BatchRevision)
            .filter_by(batch_id=bid, rev_num=rev)
            .first()
        )
        if not snapshot_row:
            raise HTTPException(404, f"Revision {rev} not found for batch {bid}")
        rows = []
        for cell in snapshot_row.snapshot_json.get("cells", []):
            m = db.get(Model, cell["model_id"])
            t = db.get(Task, cell["task_id"])
            pred = (
                db.get(Prediction, cell["current_prediction_id"])
                if cell.get("current_prediction_id") else None
            )
            ev = (
                db.get(Evaluation, cell["current_evaluation_id"])
                if cell.get("current_evaluation_id") else None
            )
            status_ = "pending"
            if ev and ev.status == "success":
                status_ = "eval_done"
            elif pred and pred.status == "success":
                status_ = "infer_done"
            rows.append(BatchReportRow(
                model_id=m.id, model_name=m.name,
                task_id=t.id, task_key=t.key,
                prediction_id=pred.id if pred else None,
                evaluation_id=ev.id if ev else None,
                accuracy=ev.accuracy if ev else None,
                num_samples=(ev.num_samples if ev
                             else (pred.num_samples if pred else None)),
                status=status_,
            ))
        return BatchReport(batch_id=batch.id, batch_name=batch.name,
                          generated_at=datetime.utcnow(), rows=rows)

    # 当前模式（基于 BatchCell 当前指针）
    cells = db.query(BatchCell).filter_by(batch_id=bid).all()
    rows = []
    for c in cells:
        m = db.get(Model, c.model_id)
        t = db.get(Task, c.task_id)
        pred = db.get(Prediction, c.current_prediction_id) if c.current_prediction_id else None
        ev = db.get(Evaluation, c.current_evaluation_id) if c.current_evaluation_id else None
        status_ = "pending"
        if ev and ev.status == "success":
            status_ = "eval_done"
        elif pred and pred.status == "success":
            status_ = "infer_done"
        rows.append(BatchReportRow(
            model_id=m.id, model_name=m.name,
            task_id=t.id, task_key=t.key,
            prediction_id=pred.id if pred else None,
            evaluation_id=ev.id if ev else None,
            accuracy=ev.accuracy if ev else None,
            num_samples=(ev.num_samples if ev else (pred.num_samples if pred else None)),
            status=status_,
        ))
    return BatchReport(batch_id=batch.id, batch_name=batch.name,
                       generated_at=datetime.utcnow(), rows=rows)


@router.get("/{bid}/revisions", response_model=list[BatchRevisionOut])
def list_revisions(bid: int,
                   db: Session = Depends(db_session),
                   _: User = Depends(require_role("viewer", "operator", "admin"))):
    batch = db.get(Batch, bid)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {bid} not found")
    return (
        db.query(BatchRevision)
        .filter_by(batch_id=bid)
        .order_by(BatchRevision.rev_num)
        .all()
    )


@router.post("/{bid}/rerun", status_code=status.HTTP_201_CREATED)
def rerun(bid: int, payload: BatchRerun,
          db: Session = Depends(db_session),
          actor: User = Depends(require_role("operator", "admin"))):
    batch = db.get(Batch, bid)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {bid} not found")
    try:
        jobs = rerun_batch(db, bid, payload, actor_user_id=actor.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return {
        "batch_id": bid,
        "jobs_created": len(jobs),
        "job_ids": [j.id for j in jobs],
    }


@router.post("/{bid}/clone", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def clone(bid: int, payload: CloneBatchIn,
          db: Session = Depends(db_session),
          actor: User = Depends(require_role("operator", "admin"))):
    src = db.get(Batch, bid)
    if not src:
        raise HTTPException(status_code=404, detail=f"Batch {bid} not found")
    cells = db.query(BatchCell).filter_by(batch_id=bid).all()
    if not cells:
        raise HTTPException(status_code=400, detail="源批次没有任何任务单元，无法重试")
    model_ids = list({c.model_id for c in cells})
    task_ids  = list({c.task_id  for c in cells})
    new_payload = BatchCreate(
        name=payload.name or f"评测id_{bid}(重试)",
        mode=src.mode,
        model_ids=model_ids,
        task_ids=task_ids,
        default_eval_version=src.default_eval_version,
        default_judge_id=src.default_judge_id,
        notes=src.notes,
    )
    new_batch = create_batch(db, new_payload, actor_user_id=actor.id)
    db.commit()
    db.refresh(new_batch)
    return _enrich_batch(db, new_batch)
