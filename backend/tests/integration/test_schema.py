import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from app.models import AuditLog

EXPECTED_TABLES = {
    "smes",
    "documents",
    "ai_results",
    "profile_field_values",
    "opportunities",
    "embeddings",
    "match_runs",
    "match_results",
    "info_requests",
    "shortlist_entries",
    "readiness_actions",
    "audit_log",
    "app_settings",
}


def test_all_tables_exist(db):
    assert EXPECTED_TABLES <= set(inspect(db.get_bind()).get_table_names())


def test_vector_extension_present(db):
    assert db.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar() == "vector"


def test_ai_mode_defaults_to_cached(db):
    assert db.execute(text("SELECT value FROM app_settings WHERE key = 'ai_mode'")).scalar() == "cached"


def _insert_audit_row(db) -> int:
    row = AuditLog(actor_role="admin", actor_label="YES Admin", action="test", details={"k": 1})
    db.add(row)
    db.commit()
    return row.id


def test_audit_log_update_is_rejected(db):
    row_id = _insert_audit_row(db)
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("UPDATE audit_log SET reason = 'tamper' WHERE id = :id"), {"id": row_id})
    db.rollback()


def test_audit_log_delete_is_rejected(db):
    row_id = _insert_audit_row(db)
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("DELETE FROM audit_log WHERE id = :id"), {"id": row_id})
    db.rollback()
    assert db.execute(text("SELECT count(*) FROM audit_log")).scalar() == 1
