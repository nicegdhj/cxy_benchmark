from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import db_session
from backend.app.models import Evaluation
from backend.app.schemas import EvaluationOut


router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("/{eid}", response_model=EvaluationOut)
def get(eid: int, db: Session = Depends(db_session)):
    ev = db.get(Evaluation, eid)
    if not ev:
        raise HTTPException(status_code=404, detail=f"Evaluation {eid} not found")
    return ev
