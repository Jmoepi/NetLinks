"""Shared fixtures. DB fixtures target TEST_DATABASE_URL, never the demo database."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app import db as app_db
from app.config import get_settings


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    engine = app_db.configure_engine(get_settings().test_database_url)
    app_db.init_db(engine)
    yield engine
    engine.dispose()


def truncate_all(engine: Engine) -> None:
    tables = ", ".join(t.name for t in app_db.Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let tests write to (or reset) the demo's real upload volume."""
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path_factory.mktemp("uploads")))


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    """Fresh schema state per test: truncate everything, then restore defaults via init_db."""
    truncate_all(db_engine)
    app_db.init_db(db_engine)
    session = app_db.SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
