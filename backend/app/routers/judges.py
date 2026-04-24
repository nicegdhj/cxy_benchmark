from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.deps import db_session, require_role
from backend.app.models import JudgeLLM, User
from backend.app.schemas import JudgeCreate, JudgeOut, JudgeUpdate


router = APIRouter(prefix="/api/v1/judges", tags=["judges"])


@router.post("", response_model=JudgeOut, status_code=status.HTTP_201_CREATED)
def create(payload: JudgeCreate,
           _: User = Depends(require_role("operator", "admin")),
           db: Session = Depends(db_session)):
    j = JudgeLLM(**payload.model_dump())
    db.add(j)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A judge with this name already exists")
    db.refresh(j)
    return j


@router.get("", response_model=list[JudgeOut])
def list_(db: Session = Depends(db_session),
          _: User = Depends(require_role("viewer", "operator", "admin"))):
    return db.query(JudgeLLM).order_by(JudgeLLM.id).all()


@router.get("/{jid}", response_model=JudgeOut)
def get(jid: int,
        db: Session = Depends(db_session),
        _: User = Depends(require_role("viewer", "operator", "admin"))):
    j = db.get(JudgeLLM, jid)
    if not j:
        raise HTTPException(404)
    return j


@router.put("/{jid}", response_model=JudgeOut)
def update(jid: int, payload: JudgeUpdate,
           db: Session = Depends(db_session),
           _: User = Depends(require_role("operator", "admin"))):
    j = db.get(JudgeLLM, jid)
    if not j:
        raise HTTPException(404)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(j, k, v)
    db.commit()
    db.refresh(j)
    return j


@router.delete("/{jid}", status_code=204)
def delete(jid: int,
           db: Session = Depends(db_session),
           _: User = Depends(require_role("operator", "admin"))):
    j = db.get(JudgeLLM, jid)
    if not j:
        raise HTTPException(404)
    db.delete(j)
    db.commit()
