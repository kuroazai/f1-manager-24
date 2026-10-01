"""The database wrapper. Each test here pins a defect the original had."""
from __future__ import annotations

import sqlite3

import pytest

from f1manager.db import DatabaseError, SaveDatabase, _check_identifier

from .conftest import balance_of


def test_connect_and_list_tables(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        tables = db.tables()
    assert "Finance_TeamBalance" in tables
    assert tables == sorted(tables), "tables() should come back sorted"


def test_missing_file_fails_immediately(tmp_path):
    with pytest.raises(FileNotFoundError):
        SaveDatabase(tmp_path / "nope.db").connect()


def test_using_before_connect_raises_clearly(save_path):
    db = SaveDatabase(save_path)
    with pytest.raises(DatabaseError, match="not connected"):
        db.tables()


def test_close_is_idempotent(save_path):
    """The original called conn.commit() before its own None guard, so closing
    twice raised AttributeError."""
    db = SaveDatabase(save_path).connect()
    db.close()
    db.close()  # must not raise
    assert db.connected is False


def test_execute_does_not_commit_on_its_own(save_path):
    """The original committed inside close(), so a write persisted as a side
    effect of closing and was lost if anything raised first."""
    before = balance_of(save_path, 1)
    db = SaveDatabase(save_path).connect()
    db.execute("UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?;", (99, 1))
    db.close()  # no commit
    assert balance_of(save_path, 1) == before


def test_explicit_commit_persists(save_path):
    db = SaveDatabase(save_path).connect()
    db.execute("UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?;", (99, 1))
    db.commit()
    db.close()
    assert balance_of(save_path, 1) == 99


def test_context_manager_commits_on_clean_exit(save_path):
    with SaveDatabase(save_path) as db:
        db.execute("UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?;", (123, 2))
    assert balance_of(save_path, 2) == 123


def test_context_manager_rolls_back_on_exception(save_path):
    before = balance_of(save_path, 3)
    with pytest.raises(ValueError), SaveDatabase(save_path) as db:
        db.execute("UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?;", (7, 3))
        raise ValueError("boom")
    assert balance_of(save_path, 3) == before


def test_read_only_connection_cannot_write(save_path):
    with SaveDatabase(save_path, read_only=True) as db, pytest.raises(sqlite3.OperationalError):
        db.execute("UPDATE Finance_TeamBalance SET Balance = 1;")


def test_read_only_connection_refuses_commit(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        with pytest.raises(DatabaseError, match="read-only"):
            db.commit()


def test_execute_returns_rows_affected(save_path):
    """The original returned fetchall() for an UPDATE — always empty, so the
    caller could not tell a no-op from a 500-row change."""
    with SaveDatabase(save_path) as db:
        affected = db.execute("UPDATE Finance_TeamBalance SET Balance = 1;")
    assert affected == 11, "the save has 11 teams"


def test_targeted_update_touches_one_row(save_path):
    with SaveDatabase(save_path) as db:
        affected = db.execute(
            "UPDATE Finance_TeamBalance SET Balance = 1 WHERE TeamID = ?;", (4,)
        )
    assert affected == 1


def test_columns_and_has_column(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        cols = db.columns("Finance_TeamBudget_SpendingBuckets")
        assert "UsedAmount" in cols
        assert db.has_column("Finance_TeamBalance", "Balance") is True
        assert db.has_column("Finance_TeamBalance", "Nonexistent") is False


def test_has_table(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        assert db.has_table("Difficulty_RaceSim") is True
        assert db.has_table("Difficulty_RaceSim; DROP TABLE x") is False


def test_row_count(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        assert db.row_count("Finance_TeamBalance") == 11
        assert db.row_count("Difficulty_RaceSim") == 1


@pytest.mark.parametrize(
    "bad",
    [
        "Finance_TeamBalance; DROP TABLE Finance_TeamBalance",
        "table name",
        "1table",
        "",
        "tbl--comment",
        "tbl'quote",
    ],
)
def test_identifier_validation_rejects_injection(bad):
    """PRAGMA cannot be parameterised, so table names reach SQL by interpolation.
    This is the guard that makes that acceptable."""
    with pytest.raises(ValueError, match="not a valid SQL identifier"):
        _check_identifier(bad)


def test_identifier_validation_accepts_real_names():
    for good in ("Finance_TeamBalance", "_private", "Table123", "a"):
        assert _check_identifier(good) == good


def test_columns_rejects_a_hostile_table_name(save_path):
    with SaveDatabase(save_path, read_only=True) as db, pytest.raises(ValueError):
        db.columns("Finance_TeamBalance); DROP TABLE Finance_TeamBalance;--")


def test_query_returns_mapping_rows(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        rows = db.query("SELECT Value, Name FROM Staff_Enum_PerformanceStatTypes ORDER BY Value;")
    assert rows[0]["Name"] == "Speed", "row_factory should give name access"
