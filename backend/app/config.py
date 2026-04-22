from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    backend_data_dir: Path = Path("./backend_data")
    workspace_dir: Path = Path("/opt/eval_workspace")
    code_dir: Path = Path("/opt/eval_workspace/code")
    docker_image_tag: str = "benchmark-eval:latest"
    worker_poll_interval_sec: float = 1.0
    default_job_concurrency: int = 4
    auth_token: str | None = None

    @property
    def db_path(self) -> Path:
        return self.backend_data_dir / "eval_backend.db"

    @property
    def envs_dir(self) -> Path:
        return self.backend_data_dir / "envs"

    @property
    def logs_dir(self) -> Path:
        return self.backend_data_dir / "logs"

    class Config:
        env_prefix = "EVAL_BACKEND_"
        env_file = ".env"
        extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
