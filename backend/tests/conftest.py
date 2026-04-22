import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import db as db_mod
from backend.app.config import get_settings
from backend.app.main import app
from backend.app.models import Base


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(db_mod, "_engine", engine)
    monkeypatch.setattr(db_mod, "_SessionLocal", SessionLocal)
    # 设置可写的 workspace_dir，避免 PermissionError
    monkeypatch.setenv("EVAL_BACKEND_WORKSPACE_DIR", str(tmp_path / "workspace"))
    # 清除 settings 缓存，确保每个测试使用独立配置
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)
