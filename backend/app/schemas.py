from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ModelCreate(BaseModel):
    name: str
    host: str
    port: int
    model_name: str
    concurrency: int = 20
    gen_kwargs_json: dict[str, Any] = {}
    model_config_key: str = "local_qwen"


class ModelUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    model_name: str | None = None
    concurrency: int | None = None
    gen_kwargs_json: dict[str, Any] | None = None
    model_config_key: str | None = None


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    host: str
    port: int
    model_name: str
    concurrency: int
    gen_kwargs_json: dict[str, Any]
    model_config_key: str
    created_at: datetime
    updated_at: datetime


class JudgeCreate(BaseModel):
    name: str
    host: str
    port: int
    model_name: str
    auth_ref: str | None = None
    extra_env_json: dict[str, str] = {}


class JudgeUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    model_name: str | None = None
    auth_ref: str | None = None
    extra_env_json: dict[str, str] | None = None


class JudgeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    host: str
    port: int
    model_name: str
    auth_ref: str | None
    extra_env_json: dict[str, str]
    created_at: datetime
    updated_at: datetime


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    type: str
    suite_name: str
    display_name: str | None
    custom_task_num: int | None
    default_data_rel_path: str | None
    is_llm_judge: bool
    created_at: datetime


class DatasetVersionCreate(BaseModel):
    tag: str
    is_default: bool = False
    note: str | None = None


class DatasetVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_id: int
    tag: str
    data_path: str
    content_hash: str | None
    is_default: bool
    uploaded_at: datetime
    note: str | None


class BatchCreate(BaseModel):
    name: str
    mode: Literal["infer", "eval", "all"] = "all"
    model_ids: list[int] = Field(..., min_length=1)
    task_ids: list[int] = Field(..., min_length=1)
    default_eval_version: str = "eval_init"
    default_judge_id: int | None = None
    notes: str | None = None


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    mode: str
    default_eval_version: str
    default_judge_id: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class BatchReportRow(BaseModel):
    model_id: int
    model_name: str
    task_id: int
    task_key: str
    prediction_id: int | None
    evaluation_id: int | None
    accuracy: float | None
    num_samples: int | None
    status: str


class BatchReport(BaseModel):
    batch_id: int
    batch_name: str
    generated_at: datetime
    rows: list[BatchReportRow]


class BatchRerun(BaseModel):
    model_ids: list[int] = Field(..., min_length=1)
    task_ids: list[int] = Field(..., min_length=1)
    what: Literal["infer", "eval", "both"] = "both"
    dataset_version_id: int | None = None


class BatchRevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    batch_id: int
    rev_num: int
    change_type: str
    change_summary: str | None
    created_at: datetime


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_id: int
    task_id: int
    dataset_version_id: int | None
    status: str
    output_task_id: str | None
    output_path: str | None
    num_samples: int | None
    duration_sec: float | None
    job_id: int | None
    created_at: datetime
    finished_at: datetime | None
    error_msg: str | None


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    prediction_id: int
    eval_version: str
    judge_id: int | None
    status: str
    accuracy: float | None
    details_path: str | None
    num_samples: int | None
    duration_sec: float | None
    job_id: int | None
    created_at: datetime
    finished_at: datetime | None
    error_msg: str | None


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    status: str
    batch_id: int | None
    model_id: int | None
    task_id: int | None
    pid: int | None
    returncode: int | None
    produces_prediction_id: int | None
    produces_evaluation_id: int | None
    dependency_job_id: int | None
    log_path: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_msg: str | None