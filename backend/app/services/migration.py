"""SQLite schema 迁移：幂等 ALTER TABLE。

不引入 Alembic。版本管理由 schema_version 表承担。
- v1：旧版本（仅原始 10 张表）
- v2：加入用户/会话表，并给 batches/batch_revisions/jobs 加 user FK
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.models import SchemaVersion


CURRENT_VERSION = 3


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

    # v2 → v3：models.host / models.port 改为可空（支持 common_gateway 等无需 host/port 的配置）
    _migrate_models_host_port_nullable(session)

    _write_version(session, CURRENT_VERSION)


def _migrate_models_host_port_nullable(session: Session):
    """将 models 表的 host/port 列从 NOT NULL 改为可空（SQLite 需重建表）。"""
    rows = session.execute(text("PRAGMA table_info(models)")).fetchall()
    col_map = {r[1]: r[3] for r in rows}  # name -> notnull
    if not col_map.get("host", 0) and not col_map.get("port", 0):
        return  # 已经是可空，无需迁移

    session.execute(text("""
        CREATE TABLE models_v3 (
            id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE,
            model_config_key VARCHAR,
            host VARCHAR,
            port INTEGER,
            url TEXT,
            api_key TEXT,
            model_name VARCHAR NOT NULL,
            concurrency INTEGER,
            gen_kwargs_json JSON,
            created_at DATETIME,
            updated_at DATETIME
        )
    """))
    session.execute(text("""
        INSERT INTO models_v3
            (id, name, model_config_key, host, port, url, api_key,
             model_name, concurrency, gen_kwargs_json, created_at, updated_at)
        SELECT id, name, model_config_key, host, port, url, api_key,
               model_name, concurrency, gen_kwargs_json, created_at, updated_at
        FROM models
    """))
    session.execute(text("DROP TABLE models"))
    session.execute(text("ALTER TABLE models_v3 RENAME TO models"))
