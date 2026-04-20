from pathlib import Path

from backend.app.config import Settings


def scan_infer_output(settings: Settings, output_task_id: str,
                      suite_name: str) -> dict:
    """扫描 outputs/{output_task_id}/ 得到推理产物信息。"""
    root = settings.workspace_dir / "outputs" / output_task_id
    return {
        "output_path": str(root),
        "num_samples": None,
    }


def scan_eval_output(settings: Settings, output_task_id: str,
                     eval_version: str, suite_name: str) -> dict:
    """扫描评测产物得到 accuracy。"""
    details_dir = (settings.workspace_dir / "outputs" / output_task_id
                   / eval_version / suite_name)
    return {
        "accuracy": None,
        "details_path": str(details_dir),
        "num_samples": None,
    }
