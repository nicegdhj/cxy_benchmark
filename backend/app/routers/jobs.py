from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.deps import db_session
from backend.app.models import Job
from backend.app.schemas import JobOut


router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_(db: Session = Depends(db_session),
          batch_id: int | None = Query(None),
          status: str | None = Query(None)):
    q = db.query(Job)
    if batch_id is not None:
        q = q.filter_by(batch_id=batch_id)
    if status is not None:
        q = q.filter_by(status=status)
    return q.order_by(Job.id.desc()).limit(200).all()


@router.get("/{jid}", response_model=JobOut)
def get(jid: int, db: Session = Depends(db_session)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(status_code=404, detail=f"Job {jid} not found")
    return j


@router.get("/{jid}/log")
def get_log(jid: int, db: Session = Depends(db_session)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(status_code=404, detail=f"Job {jid} not found")
    if not j.log_path:
        raise HTTPException(status_code=404, detail="No log file for this job")
    return FileResponse(j.log_path, media_type="text/plain")


@router.post("/{jid}/cancel")
def cancel(jid: int, db: Session = Depends(db_session)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(status_code=404, detail=f"Job {jid} not found")
    if j.status not in ("pending", "running"):
        raise HTTPException(400, f"Cannot cancel job with status {j.status}")
    import subprocess
    if j.pid:
        try:
            subprocess.run(["docker", "kill", f"eval-{jid}-infer"],
                           capture_output=True)
            subprocess.run(["docker", "kill", f"eval-{jid}-judge"],
                           capture_output=True)
        except Exception:
            pass
    j.status = "cancelled"
    j.error_msg = "Cancelled by user"
    db.commit()
    return {"status": "cancelled", "job_id": jid}
