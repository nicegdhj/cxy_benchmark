import asyncio
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_session
from backend.app.models import (
    BatchCell, Job, Model, Prediction, Evaluation, Task,
)
from backend.app.services.batch_service import record_revision
from backend.app.services.docker_runner import (
    build_eval_cmd, build_infer_cmd, write_env_file,
)
from backend.app.services.scan import scan_infer_output, scan_eval_output


def _pick_next_job(db: Session) -> Job | None:
    q = db.query(Job).filter(Job.status == "pending")
    for job in q.order_by(Job.id).all():
        if job.dependency_job_id:
            dep = db.get(Job, job.dependency_job_id)
            if dep.status != "success":
                continue
        return job
    return None


def _env_vars_for_model(model: Model) -> dict[str, str]:
    return {
        "LOCAL_MODEL_NAME": model.model_name,
        "LOCAL_HOST_IP": model.host,
        "LOCAL_HOST_PORT": str(model.port),
        "LOCAL_CONCURRENCY": str(model.concurrency),
        "PYTHONUNBUFFERED": "1",
    }


def _make_output_task_id(job: Job) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"batch{job.batch_id}_m{job.model_id}_t{job.task_id}_{ts}"


def _run_infer(db: Session, job: Job, settings):
    model = db.get(Model, job.model_id)
    task = db.get(Task, job.task_id)

    output_task_id = _make_output_task_id(job)
    env_file = write_env_file(settings, job.id, _env_vars_for_model(model))
    cmd = build_infer_cmd(
        settings=settings, job_id=job.id, env_file=env_file,
        output_task_id=output_task_id,
        model_config_key=model.model_config_key,
        task_type=task.type,
        custom_task_num=task.custom_task_num,
        suite_name=task.suite_name,
    )

    log_path = settings.logs_dir / f"job_{job.id}.log"
    settings.logs_dir.mkdir(parents=True, exist_ok=True)

    job.params_json = {**(job.params_json or {}), "output_task_id": output_task_id}
    job.status = "running"
    job.started_at = datetime.utcnow()
    job.log_path = str(log_path)
    db.commit()

    with open(log_path, "wb") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        job.pid = proc.pid
        db.commit()
        returncode = proc.wait()

    job.returncode = returncode
    job.finished_at = datetime.utcnow()

    if returncode == 0:
        info = scan_infer_output(settings, output_task_id, task.suite_name)
        pred = Prediction(
            model_id=job.model_id, task_id=job.task_id,
            dataset_version_id=None,
            status="success",
            output_task_id=output_task_id,
            output_path=info["output_path"],
            num_samples=info["num_samples"],
            duration_sec=(job.finished_at - job.started_at).total_seconds(),
            job_id=job.id, finished_at=job.finished_at,
        )
        db.add(pred)
        db.flush()
        job.produces_prediction_id = pred.id
        job.status = "success"

        if job.batch_id:
            cell = db.get(BatchCell, (job.batch_id, job.model_id, job.task_id))
            if cell:
                cell.current_prediction_id = pred.id
                record_revision(
                    db, job.batch_id, "infer_done",
                    f"prediction {pred.id} for model={job.model_id} task={job.task_id}",
                )
    else:
        job.status = "failed"
    db.commit()


def _run_eval(db: Session, job: Job, settings):
    if job.dependency_job_id:
        dep = db.get(Job, job.dependency_job_id)
        prediction = db.get(Prediction, dep.produces_prediction_id)
    else:
        cell = db.get(BatchCell, (job.batch_id, job.model_id, job.task_id))
        prediction = db.get(Prediction, cell.current_prediction_id) if cell else None
    if not prediction:
        job.status = "failed"
        job.error_msg = "no prediction to evaluate"
        db.commit()
        return

    model = db.get(Model, job.model_id)
    task = db.get(Task, job.task_id)
    eval_version = job.params_json.get("eval_version", "eval_init")
    env_file = write_env_file(settings, job.id, _env_vars_for_model(model))
    cmd = build_eval_cmd(
        settings=settings, job_id=job.id, env_file=env_file,
        output_task_id=prediction.output_task_id,
        eval_version=eval_version,
        suite_name=task.suite_name,
    )

    log_path = settings.logs_dir / f"job_{job.id}.log"
    job.status = "running"
    job.started_at = datetime.utcnow()
    job.log_path = str(log_path)
    db.commit()

    with open(log_path, "wb") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT)
        job.pid = proc.pid
        db.commit()
        returncode = proc.wait()

    job.returncode = returncode
    job.finished_at = datetime.utcnow()

    if returncode == 0:
        info = scan_eval_output(settings, prediction.output_task_id, eval_version,
                                task.suite_name)
        ev = Evaluation(
            prediction_id=prediction.id, eval_version=eval_version,
            status="success", accuracy=info["accuracy"],
            details_path=info["details_path"],
            num_samples=info["num_samples"],
            duration_sec=(job.finished_at - job.started_at).total_seconds(),
            job_id=job.id, finished_at=job.finished_at,
        )
        db.add(ev)
        db.flush()
        job.produces_evaluation_id = ev.id
        job.status = "success"

        if job.batch_id:
            cell = db.get(BatchCell, (job.batch_id, job.model_id, job.task_id))
            if cell:
                cell.current_evaluation_id = ev.id
                record_revision(
                    db, job.batch_id, "eval_done",
                    f"evaluation {ev.id} for model={job.model_id} task={job.task_id}",
                )
    else:
        job.status = "failed"
    db.commit()


async def run_pending_jobs_once():
    settings = get_settings()
    with get_session() as db:
        job = _pick_next_job(db)
        if not job:
            return
    with get_session() as db:
        job = db.get(Job, job.id)
        if job.type == "infer":
            _run_infer(db, job, settings)
        else:
            _run_eval(db, job, settings)


async def worker_loop():
    settings = get_settings()
    while True:
        try:
            await run_pending_jobs_once()
        except Exception as e:
            print(f"[worker] error: {e}")
        await asyncio.sleep(settings.worker_poll_interval_sec)
