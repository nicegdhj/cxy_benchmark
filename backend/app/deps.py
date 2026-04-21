from typing import Generator

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import init_db


def verify_token(authorization: str | None = Header(None)):
    """Bearer token 鉴权。若未配置 auth_token，则跳过校验（内网信任模式）。"""
    settings = get_settings()
    if settings.auth_token is None:
        return
    if authorization != f"Bearer {settings.auth_token}":
        raise HTTPException(status_code=401, detail="Unauthorized")


def db_session() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：自动 commit，异常自动 rollback。"""
    from backend.app.db import _SessionLocal

    if _SessionLocal is None:
        init_db()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
