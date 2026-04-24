"""SQLite schema 迁移：幂等 ALTER TABLE。

不引入 Alembic。版本管理由 schema_version 表承担。
- v1：旧版本（仅原始 10 张表）
- v2：加入用户/会话表，并给 batches/batch_revisions/jobs 加 user FK
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.models import SchemaVersion


CURRENT_VERSION = 2


def _has_table(session: Session, name: str) -> bool:
    row = session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).first()
    return row is not None


def _has_column(session: Session, table: str, column: str) -> bool:
    if not _has_table(session, table):
        return False
    rows = session.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _add_column_if_missing(session: Session, table: str, column: str, ddl: str):
    if not _has_table(session, table):
        return
    if _has_column(session, table, column):
        return
    session.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def _read_version(session: Session) -> int:
    if not _has_table(session, "schema_version"):
        return 0
    row = session.query(SchemaVersion).first()
    return row.version if row else 0


def _write_version(session: Session, version: int):
    session.query(SchemaVersion).delete()
    session.add(SchemaVersion(version=version))


def run_migrations(session: Session):
    """幂等迁移。可在每次启动时调用。"""
    if not _has_table(session, "schema_version"):
        session.execute(text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"))

    current = _read_version(session)
    if current >= CURRENT_VERSION:
        return

    # v1 → v2：补 user FK 列（新表 users / user_sessions / schema_version 由 create_all 建）
    _add_column_if_missing(session, "batches", "created_by_user_id",
                           "created_by_user_id INTEGER REFERENCES users(id)")
    _add_column_if_missing(session, "batches", "last_modified_by_user_id",
                           "last_modified_by_user_id INTEGER REFERENCES users(id)")
    _add_column_if_missing(session, "batch_revisions", "actor_user_id",
                           "actor_user_id INTEGER REFERENCES users(id)")
    _add_column_if_missing(session, "jobs", "created_by_user_id",
                           "created_by_user_id INTEGER REFERENCES users(id)")

    _write_version(session, CURRENT_VERSION)
