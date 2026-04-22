import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.deps import db_session
from backend.app.models import DatasetVersion, Task
from backend.app.schemas import DatasetVersionOut, TaskOut


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


@router.post("/{tid}/datasets", response_model=DatasetVersionOut)
def upload_dataset(
    tid: int,
    tag: str = Form(...),
    is_default: bool = Form(False),
    note: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(db_session),
):
    task = db.get(Task, tid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 校验文件扩展名
    if not file.filename or not file.filename.endswith(".jsonl"):
        raise HTTPException(400, "Only .jsonl files are supported")

    content = file.file.read()

    # 校验首行可解析为 JSON
    first_line = content.split(b"\n")[0].strip()
    if not first_line:
        raise HTTPException(400, "File is empty")
    try:
        json.loads(first_line)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSONL format: first line is not valid JSON")

    # 计算 SHA256
    content_hash = hashlib.sha256(content).hexdigest()

    # 落盘
    settings = get_settings()
    version_dir = settings.workspace_dir / "data" / "versions" / task.key / tag
    version_dir.mkdir(parents=True, exist_ok=True)
    data_path = version_dir / "data.jsonl"
    data_path.write_bytes(content)

    rel_path = str(data_path.relative_to(settings.workspace_dir))

    # 若 is_default，清除其他默认版本
    if is_default:
        db.query(DatasetVersion).filter_by(task_id=tid, is_default=True).update(
            {"is_default": False}
        )

    dv = DatasetVersion(
        task_id=tid,
        tag=tag,
        data_path=rel_path,
        content_hash=content_hash,
        is_default=is_default,
        note=note,
    )
    db.add(dv)
    db.commit()
    db.refresh(dv)
    return dv


@router.get("/{tid}/datasets", response_model=list[DatasetVersionOut])
def list_datasets(tid: int, db: Session = Depends(db_session)):
    task = db.get(Task, tid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return (
        db.query(DatasetVersion)
        .filter_by(task_id=tid)
        .order_by(DatasetVersion.uploaded_at.desc())
        .all()
    )
