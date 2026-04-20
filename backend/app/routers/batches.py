from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.deps import db_session
from backend.app.models import Batch
from backend.app.schemas import BatchCreate, BatchOut
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
        raise HTTPException(404)
    return b