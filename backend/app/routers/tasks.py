from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import db_session
from backend.app.models import Task
from backend.app.schemas import TaskOut


router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
def list_(db: Session = Depends(db_session)):
    return db.query(Task).order_by(Task.key).all()


@router.get("/{tid}", response_model=TaskOut)
def get(tid: int, db: Session = Depends(db_session)):
    t = db.get(Task, tid)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return t
