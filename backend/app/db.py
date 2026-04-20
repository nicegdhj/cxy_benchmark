from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.app.config import get_settings
from backend.app.models import Base


_engine = None
_SessionLocal = None


def init_db():
    global _engine, _SessionLocal
    settings = get_settings()
    settings.backend_data_dir.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{settings.db_path}",
        connect_args={"check_same_thread": False},
    )
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()
