import json

from backend.app.config import Settings


def scan_infer_output(settings: Settings, output_task_id: str,
                      suite_name: str) -> dict:
    """扫描 outputs/{output_task_id}/infer_meta.json 得到推理产物信息。"""
    root = settings.workspace_dir / "outputs" / output_task_id
    num_samples = None
    meta = root / "infer_meta.json"
    if meta.exists():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            # tasks 是 dict，key=suite_name（见 eval_entry.generate_infer_meta）
            task_info = data.get("tasks", {}).get(suite_name)
            if task_info:
                num_samples = task_info.get("num_samples")
        except Exception:
            pass
    return {"output_path": str(root), "num_samples": num_samples}


def scan_eval_output(settings: Settings, output_task_id: str,
                     eval_version: str, suite_name: str) -> dict:
    """扫描 eval_version/suite_name/{summary,report}.json 得到 accuracy。"""
    details_dir = (settings.workspace_dir / "outputs" / output_task_id
                   / eval_version / suite_name)
    accuracy = None
    num_samples = None
    for fname in ("summary.json", "report.json"):
        p = details_dir / fname
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            accuracy = data.get("accuracy", accuracy)
            num_samples = data.get("num_samples", num_samples)
        except Exception:
            pass
    return {"accuracy": accuracy, "details_path": str(details_dir),
            "num_samples": num_samples}
