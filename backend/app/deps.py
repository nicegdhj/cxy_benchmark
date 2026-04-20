from typing import Generator
from sqlalchemy.orm import Session

from backend.app.db import init_db


# Import _SessionLocal lazily to avoid circular imports while ensuring init runs
def db_session() -> Generator[Session, None, None]:
    from backend.app.db import _SessionLocal

    if _SessionLocal is None:
        init_db()
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()