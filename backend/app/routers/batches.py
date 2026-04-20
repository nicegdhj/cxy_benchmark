from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.deps import db_session
from backend.app.models import Batch, BatchCell, Evaluation, Model, Prediction, Task
from backend.app.schemas import BatchCreate, BatchOut, BatchReport, BatchReportRow
from backend.app.services.batch_service import create_batch


router = APIRouter(prefix="/api/v1/batches", tags=["batches"])


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create(payload: BatchCreate, db: Session = Depends(db_session)):
    try:
        batch = create_batch(db, payload)
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.commit()
    db.refresh(batch)
    return batch


@router.get("", response_model=list[BatchOut])
def list_(db: Session = Depends(db_session)):
    return db.query(Batch).order_by(Batch.id.desc()).all()


@router.get("/{bid}", response_model=BatchOut)
def get(bid: int, db: Session = Depends(db_session)):
    b = db.get(Batch, bid)
    if not b:
        raise HTTPException(status_code=404, detail=f"Batch {bid} not found")
    return b


@router.get("/{bid}/report", response_model=BatchReport)
def report(bid: int, db: Session = Depends(db_session)):
    batch = db.get(Batch, bid)
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {bid} not found")
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