from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, ForeignKey,
    DateTime, Text, JSON, UniqueConstraint, Enum,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _now():
    return datetime.utcnow()


class Model(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    model_name = Column(String, nullable=False)
    concurrency = Column(Integer, default=20)
    gen_kwargs_json = Column(JSON, default=dict)
    model_config_key = Column(String, default="local_qwen")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class JudgeLLM(Base):
    __tablename__ = "judges"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    model_name = Column(String, nullable=False)
    auth_ref = Column(String)
    extra_env_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    type = Column(String, nullable=False)  # custom | generic
    suite_name = Column(String, nullable=False)
    display_name = Column(String)
    custom_task_num = Column(Integer)
    default_data_rel_path = Column(String)
    is_llm_judge = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    tag = Column(String, nullable=False)
    data_path = Column(String, nullable=False)
    content_hash = Column(String)
    is_default = Column(Boolean, default=False)
    uploaded_at = Column(DateTime, default=_now)
    note = Column(Text)
    __table_args__ = (UniqueConstraint("task_id", "tag"),)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    dataset_version_id = Column(Integer, ForeignKey("dataset_versions.id"))
    status = Column(Enum("pending", "running", "success", "failed"), default="pending")
    output_task_id = Column(String)  # ais_bench 的 task_id
    output_path = Column(String)
    num_samples = Column(Integer)
    duration_sec = Column(Float)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    created_at = Column(DateTime, default=_now)
    finished_at = Column(DateTime)
    error_msg = Column(Text)


class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)
    eval_version = Column(String, nullable=False)
    judge_id = Column(Integer, ForeignKey("judges.id"))
    status = Column(Enum("pending", "running", "success", "failed"), default="pending")
    accuracy = Column(Float)
    details_path = Column(String)
    num_samples = Column(Integer)
    duration_sec = Column(Float)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    created_at = Column(DateTime, default=_now)
    finished_at = Column(DateTime)
    error_msg = Column(Text)


class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    mode = Column(String, default="all")  # infer | eval | all
    default_eval_version = Column(String, default="eval_init")
    default_judge_id = Column(Integer, ForeignKey("judges.id"))
    notes = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    last_modified_by_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    last_modified_by = relationship("User", foreign_keys=[last_modified_by_user_id])


class BatchCell(Base):
    __tablename__ = "batch_cells"
    batch_id = Column(Integer, ForeignKey("batches.id"), primary_key=True)
    model_id = Column(Integer, ForeignKey("models.id"), primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), primary_key=True)
    dataset_version_id = Column(Integer, ForeignKey("dataset_versions.id"))
    current_prediction_id = Column(Integer, ForeignKey("predictions.id"))
    current_evaluation_id = Column(Integer, ForeignKey("evaluations.id"))
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class BatchRevision(Base):
    __tablename__ = "batch_revisions"
    id = Column(Integer, primary_key=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    rev_num = Column(Integer, nullable=False)
    change_type = Column(String, nullable=False)
    change_summary = Column(Text)
    snapshot_json = Column(JSON)
    actor_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("batch_id", "rev_num"),)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False)  # infer | eval
    params_json = Column(JSON, default=dict)
    status = Column(Enum("pending", "running", "success", "failed", "cancelled"), default="pending")
    log_path = Column(String)
    pid = Column(Integer)
    returncode = Column(Integer)
    batch_id = Column(Integer, ForeignKey("batches.id"))
    model_id = Column(Integer, ForeignKey("models.id"))
    task_id = Column(Integer, ForeignKey("tasks.id"))
    produces_prediction_id = Column(Integer, ForeignKey("predictions.id"))
    produces_evaluation_id = Column(Integer, ForeignKey("evaluations.id"))
    dependency_job_id = Column(Integer, ForeignKey("jobs.id"))
    created_by_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=_now)
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    error_msg = Column(Text)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin | operator | viewer
    display_name = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=_now)
    last_used_at = Column(DateTime, default=_now)
    expires_at = Column(DateTime, nullable=False)


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    version = Column(Integer, primary_key=True)
