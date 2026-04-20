from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


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


class BatchCreate(BaseModel):
    name: str
    mode: str = "all"  # infer | eval | all
    model_ids: list[int]
    task_ids: list[int]
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