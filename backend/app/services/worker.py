import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_session
from backend.app.models import (
    Batch, BatchCell, Evaluation, Job, JudgeLLM, Model, Prediction, Task,
)
from backend.app.services.batch_service import record_revision
from backend.app.services.docker_runner import (
    build_eval_cmd, build_infer_cmd, write_env_file,
)
from backend.app.services.scan import scan_eval_output, scan_infer_output

logger = logging.getLogger(__name__)


def _pick_next_job(db: Session) -> Job | None:
    """选取下一个可执行的 pending job，超出 Model 并发配额的会被跳过。"""
    q = db.query(Job).filter(Job.status == "pending")
    for job in q.order_by(Job.id).all():
        if job.dependency_job_id:
            dep = db.get(Job, job.dependency_job_id)
            if dep is None or dep.status != "success":
                continue
        # 检查 Model 并发配额（I1）
        model = db.get(Model, job.model_id)
        if model:
            running_count = (
                db.query(Job)
                .filter_by(model_id=job.model_id, status="running")
                .count()
            )
            if running_count >= model.concurrency:
                continue
        return job
    return None


def _env_vars_for_model(model: Model) -> dict[str, str]:
    key = model.model_config_key or "local_qwen"
    base = {"PYTHONUNBUFFERED": "1"}
    if key == "local_qwen":
        return {**base,
                "LOCAL_MODEL_NAME": model.model_name or "",
                "LOCAL_HOST_IP":    model.host or "",
                "LOCAL_HOST_PORT":  str(model.port or ""),
                "LOCAL_CONCURRENCY": str(model.concurrency)}
    elif key == "maas_gateway":
        return {**base,
                "MAAS_MODEL":       model.model_name or "",
                "MAAS_API_KEY":     model.api_key or "",
                "MAAS_HOST_IP":     model.host or "",
                "MAAS_HOST_PORT":   str(model.port or ""),
                "MAAS_URL":         model.url or "",
                "MAAS_CONCURRENCY": str(model.concurrency)}
    elif key == "common_gateway":
        return {**base,
                "COMMON_MODEL_NAME":   model.model_name or "",
                "COMMON_API_KEY":      model.api_key or "",
                "COMMON_API_URL":      model.url or "",
                "COMMON_CONCURRENCY":  str(model.concurrency)}

    else:
        # 未知 config_key：原样透传通用字段，让容器自行处理
        return {**base,
                "LOCAL_MODEL_NAME": model.model_name or "",
                "LOCAL_HOST_IP":    model.host or "",
                "LOCAL_HOST_PORT":  str(model.port or ""),
                "LOCAL_CONCURRENCY": str(model.concurrency)}


def _make_output_task_id(job: Job) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return f"batch{job.batch_id}_m{job.model_id}_t{job.task_id}_{ts}"


async def _run_infer(db: Session, job: Job, settings):
    """异步执行推理 job，scan 异常时自动将 job 置为 failed（防止卡 running）。"""
    env_file = None
    try:
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
            loop = asyncio.get_event_loop()
            returncode = await loop.run_in_executor(None, proc.wait)

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

    except Exception as e:
        logger.exception("infer job %d failed", job.id)
        job.status = "failed"
        job.error_msg = str(e)
        try:
            db.commit()
        except Exception:
            pass
        raise
    finally:
        if env_file and env_file.exists():
            env_file.unlink(missing_ok=True)


def _env_vars_for_judge(judge: JudgeLLM) -> dict[str, str]:
    key = judge.judge_config_key or "local_judge"
    concurrency = str(judge.concurrency or 5)
    if key == "local_judge":
        return {
            "SCORE_MODEL_NAME":      judge.model_name or "",
            "SCORE_HOST_IP":         judge.host or "",
            "SCORE_HOST_PORT":       str(judge.port or ""),
            "SCORE_LLM_CONCURRENCY": concurrency,
            "SCORE_MODEL_TYPE":      "maas",
        }
    else:  # api_judge
        return {
            "SCORE_MODEL_NAME":      judge.model_name or "",
            "SCORE_API_KEY":         judge.api_key or "",
            "SCORE_URL":             judge.url or "",
            "SCORE_LLM_CONCURRENCY": concurrency,
            "SCORE_MODEL_TYPE":      judge.score_model_type or "maas",
        }


async def _run_eval(db: Session, job: Job, settings):
    """异步执行评测 job，scan 异常时自动将 job 置为 failed。"""
    env_file = None
    try:
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

        # 合并 judge 的 SCORE_* 环境变量
        judge_env: dict[str, str] = {}
        batch = db.get(Batch, job.batch_id) if job.batch_id else None
        if batch and batch.default_judge_id:
            judge = db.get(JudgeLLM, batch.default_judge_id)
            if judge:
                judge_env = _env_vars_for_judge(judge)

        env_file = write_env_file(settings, job.id, {**_env_vars_for_model(model), **judge_env})
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
            loop = asyncio.get_event_loop()
            returncode = await loop.run_in_executor(None, proc.wait)

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

    except Exception as e:
        logger.exception("eval job %d failed", job.id)
        job.status = "failed"
        job.error_msg = str(e)
        try:
            db.commit()
        except Exception:
            pass
        raise
    finally:
        if env_file and env_file.exists():
            env_file.unlink(missing_ok=True)


async def run_pending_jobs_once():
    settings = get_settings()
    with get_session() as db:
        job = _pick_next_job(db)
        if not job:
            return
    with get_session() as db:
        job = db.get(Job, job.id)
        if job.type == "infer":
            await _run_infer(db, job, settings)
        else:
            await _run_eval(db, job, settings)


async def worker_loop():
    settings = get_settings()
    while True:
        try:
            await run_pending_jobs_once()
        except Exception as e:
            logger.exception("worker loop error")
        await asyncio.sleep(settings.worker_poll_interval_sec)
