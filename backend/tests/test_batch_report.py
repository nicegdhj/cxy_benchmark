from backend.app.db import get_session
from backend.app.models import BatchCell, Evaluation, Prediction, Task
from backend.app.services.seed import seed_generic_tasks


def test_report_shows_matrix(client):
    with get_session() as s:
        seed_generic_tasks(s, ["mmlu_redux_gen_5_shot_str"])
        s.commit()
    mid = client.post("/api/v1/models", json={
        "name": "m1", "host": "h", "port": 1, "model_name": "x"}).json()["id"]
    tid = client.get("/api/v1/tasks").json()[0]["id"]
    bid = client.post("/api/v1/batches", json={
        "name": "b", "mode": "all",
        "model_ids": [mid], "task_ids": [tid]}).json()["id"]

    # 模拟 worker 完成
    with get_session() as s:
        pred = Prediction(model_id=mid, task_id=tid, status="success",
                          output_task_id="tx", output_path="/p",
                          num_samples=10)
        s.add(pred); s.flush()
        ev = Evaluation(prediction_id=pred.id, eval_version="eval_init",
                        status="success", accuracy=88.0, num_samples=10)
        s.add(ev); s.flush()
        cell = s.get(BatchCell, (bid, mid, tid))
        cell.current_prediction_id = pred.id
        cell.current_evaluation_id = ev.id
        s.commit()

    r = client.get(f"/api/v1/batches/{bid}/report")
    assert r.status_code == 200
    body = r.json()
    assert body["batch_id"] == bid
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["model_id"] == mid
    assert row["task_id"] == tid
    assert row["accuracy"] == 88.0
    assert row["num_samples"] == 10
    assert row["status"] == "eval_done"


def test_report_pending_cell(client):
    with get_session() as s:
        seed_generic_tasks(s, ["mmlu_redux_gen_5_shot_str"])
        s.commit()
    mid = client.post("/api/v1/models", json={
        "name": "m1", "host": "h", "port": 1, "model_name": "x"}).json()["id"]
    tid = client.get("/api/v1/tasks").json()[0]["id"]
    bid = client.post("/api/v1/batches", json={
        "name": "b", "mode": "infer",
        "model_ids": [mid], "task_ids": [tid]}).json()["id"]

    r = client.get(f"/api/v1/batches/{bid}/report")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert row["status"] == "pending"
    assert row["accuracy"] is None


def test_report_not_found(client):
    r = client.get("/api/v1/batches/99999/report")
    assert r.status_code == 404
