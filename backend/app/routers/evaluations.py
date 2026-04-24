from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import db_session, require_role
from backend.app.models import Evaluation, User
from backend.app.schemas import EvaluationOut


router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("/{eid}", response_model=EvaluationOut)
def get(eid: int,
        db: Session = Depends(db_session),
        _: User = Depends(require_role("viewer", "operator", "admin"))):
    ev = db.get(Evaluation, eid)
    if not ev:
        raise HTTPException(status_code=404, detail=f"Evaluation {eid} not found")
    return ev
