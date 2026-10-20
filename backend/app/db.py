"""Database engine, sessions and schema initialisation (no Alembic; see plan A4)."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


engine: Engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def configure_engine(url: str) -> Engine:
    """Rebind the module engine and SessionLocal (used by tests to target TEST_DATABASE_URL)."""
    global engine
    engine.dispose()
    engine = _make_engine(url)
    SessionLocal.configure(bind=engine)
    return engine


def get_engine() -> Engine:
    return engine


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_AUDIT_TRIGGER_SQL = [
    """
    CREATE OR REPLACE FUNCTION audit_log_append_only() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE OR REPLACE TRIGGER audit_log_no_update_delete
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_append_only()
    """,
]

# Arbitrary constant key so concurrent init_db calls (app startup + test run) serialise.
_INIT_LOCK_KEY = 4242001


def init_db(bind: Engine | None = None) -> None:
    """Create the vector extension, all tables, the audit trigger and default settings."""
    from app import models  # noqa: F401  (register tables on Base.metadata)

    bind = bind or engine
    with bind.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _INIT_LOCK_KEY})
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(conn)
        for stmt in _AUDIT_TRIGGER_SQL:
            conn.execute(text(stmt))
        conn.execute(
            text(
                "INSERT INTO app_settings (key, value) VALUES ('ai_mode', 'cached') "
                "ON CONFLICT (key) DO NOTHING"
            )
        )
