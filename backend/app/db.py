from contextlib import contextmanager

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

    # 权限系统：迁移 + admin 初始化
    from backend.app.services.migration import run_migrations
    from backend.app.services.init_admin import ensure_admin

    with _SessionLocal() as session:
        run_migrations(session)
        ensure_admin(session, settings.admin_username, settings.admin_password)
        session.commit()


@contextmanager
def get_session():
    """带 rollback 保障的 session 上下文管理器。异常时自动回滚。"""
    if _SessionLocal is None:
        init_db()
    session = _SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
