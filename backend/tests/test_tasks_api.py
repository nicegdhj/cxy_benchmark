from backend.app.db import get_session
from backend.app.services.seed import seed_generic_tasks, seed_custom_tasks


def _seed():
    with get_session() as s:
        seed_generic_tasks(s, ["mmlu_redux_gen_5_shot_str"])
        seed_custom_tasks(s, [34])
        s.commit()


def test_list_tasks(client):
    _seed()
    r = client.get("/api/v1/tasks")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    keys = {t["key"] for t in items}
    assert keys == {"mmlu_redux_gen_5_shot_str", "task_34_suite"}


def test_get_task(client):
    _seed()
    r = client.get("/api/v1/tasks")
    tid = r.json()[0]["id"]
    r2 = client.get(f"/api/v1/tasks/{tid}")
    assert r2.status_code == 200
    data = r2.json()
    assert "key" in data
    assert "type" in data
    assert "suite_name" in data


def test_get_task_404(client):
    r = client.get("/api/v1/tasks/99999")
    assert r.status_code == 404
