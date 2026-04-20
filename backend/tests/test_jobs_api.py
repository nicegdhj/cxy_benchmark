from backend.app.db import get_session
from backend.app.services.seed import seed_generic_tasks


def test_list_and_get_job(client):
    with get_session() as s:
        seed_generic_tasks(s, ["mmlu_redux_gen_5_shot_str"])
        s.commit()
    mid = client.post("/api/v1/models", json={
        "name": "m1", "host": "h", "port": 1, "model_name": "x"}).json()["id"]
    tid = client.get("/api/v1/tasks").json()[0]["id"]
    client.post("/api/v1/batches", json={
        "name": "b", "mode": "infer",
        "model_ids": [mid], "task_ids": [tid]})

    r = client.get("/api/v1/jobs")
    assert r.status_code == 200
    jobs = r.json()
    assert len(jobs) >= 1
    jid = jobs[0]["id"]
    r2 = client.get(f"/api/v1/jobs/{jid}")
    assert r2.status_code == 200
    assert r2.json()["type"] == "infer"


def test_get_job_not_found(client):
    r = client.get("/api/v1/jobs/99999")
    assert r.status_code == 404


def test_list_jobs_filter_by_batch_id(client):
    with get_session() as s:
        seed_generic_tasks(s, ["mmlu_redux_gen_5_shot_str"])
        s.commit()
    mid = client.post("/api/v1/models", json={
        "name": "m1", "host": "h", "port": 1, "model_name": "x"}).json()["id"]
    tid = client.get("/api/v1/tasks").json()[0]["id"]
    bid_r = client.post("/api/v1/batches", json={
        "name": "b", "mode": "infer",
        "model_ids": [mid], "task_ids": [tid]})
    bid = bid_r.json()["id"]

    r = client.get(f"/api/v1/jobs?batch_id={bid}")
    assert r.status_code == 200
    jobs = r.json()
    assert len(jobs) == 1
    assert jobs[0]["batch_id"] == bid
