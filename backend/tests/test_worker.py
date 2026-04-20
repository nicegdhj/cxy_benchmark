import asyncio
from unittest.mock import patch, MagicMock

import pytest

from backend.app.db import get_session
from backend.app.models import Job, Model, Task
from backend.app.services.worker import run_pending_jobs_once
from backend.app.services.seed import seed_generic_tasks


async def _seed(client):
    with get_session() as s:
        seed_generic_tasks(s, ["mmlu_redux_gen_5_shot_str"])
        s.commit()
    mid = client.post("/api/v1/models", json={
        "name": "m1", "host": "h", "port": 1, "model_name": "x"}).json()["id"]
    tid = client.get("/api/v1/tasks").json()[0]["id"]
    r = client.post("/api/v1/batches", json={
        "name": "b1", "mode": "infer",
        "model_ids": [mid], "task_ids": [tid],
    })
    return r.json()["id"], mid, tid


async def test_worker_picks_and_runs_pending_job(client):
    bid, mid, tid = await _seed(client)

    fake_proc = MagicMock()
    fake_proc.pid = 12345
    fake_proc.returncode = 0
    fake_proc.wait.return_value = 0

    with patch(
        "backend.app.services.worker.subprocess.Popen",
        return_value=fake_proc,
    ) as popen, patch(
        "backend.app.services.worker.scan_infer_output",
        return_value={"output_path": "/tmp", "num_samples": 100},
    ):
        await run_pending_jobs_once()

    with get_session() as s:
        job = s.query(Job).filter_by(batch_id=bid).first()
        assert job.status == "success"
        assert job.returncode == 0
        popen.assert_called_once()
