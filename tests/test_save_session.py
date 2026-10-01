"""The safety model. These are the tests that justify pointing this tool at a
real save: if any of them fail, someone loses their career file."""
from __future__ import annotations

import pytest

from f1manager.save import NotASaveError, SaveSession

from .conftest import balance_of

SET_BALANCE = "UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?;"
SET_ALL_BALANCES = "UPDATE Finance_TeamBalance SET Balance = ?;"


# -- validation ------------------------------------------------------------
def test_rejects_a_database_that_is_not_a_save(not_a_save):
    with pytest.raises(NotASaveError, match="does not look like"):
        SaveSession(not_a_save).open()


def test_rejects_a_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        SaveSession(tmp_path / "absent.db").open()


def test_validation_runs_before_any_backup_is_taken(not_a_save):
    """A wrong path must fail cleanly, not leave a backup of the wrong file."""
    with pytest.raises(NotASaveError):
        SaveSession(not_a_save).open()
    assert not (not_a_save.parent / "backups").exists()


# -- backups ---------------------------------------------------------------
def test_backup_is_taken_before_writing(save_path):
    with SaveSession(save_path) as session:
        assert session.backup_path is not None
        assert session.backup_path.exists()
        session.run("set balance", SET_BALANCE, (10**9, 1))

    backups = list((save_path.parent / "backups").glob("main_*.db"))
    assert len(backups) == 1


def test_backup_holds_the_pre_change_value(save_path):
    original = balance_of(save_path, 1)
    with SaveSession(save_path) as session:
        session.run("set balance", SET_BALANCE, (10**9, 1))
        backup = session.backup_path

    assert balance_of(save_path, 1) == 10**9, "the save should have changed"
    assert balance_of(backup, 1) == original, "the backup should not have"


def test_backup_can_be_disabled_explicitly(save_path):
    with SaveSession(save_path, backup=False) as session:
        assert session.backup_path is None
        session.run("set balance", SET_BALANCE, (1, 1))
    assert not (save_path.parent / "backups").exists()


def test_backup_directory_is_configurable(save_path, tmp_path):
    target = tmp_path / "elsewhere"
    with SaveSession(save_path, backup_dir=target) as session:
        session.run("set balance", SET_BALANCE, (1, 1))
    assert list(target.glob("main_*.db"))


def test_dry_run_takes_no_backup(save_path):
    """Nothing is being changed, so there is nothing to protect."""
    with SaveSession(save_path, dry_run=True) as session:
        session.run("set balance", SET_BALANCE, (10**9, 1))
        assert session.backup_path is None
    assert not (save_path.parent / "backups").exists()


# -- dry run ---------------------------------------------------------------
def test_dry_run_writes_nothing(save_path):
    before = balance_of(save_path, 1)
    with SaveSession(save_path, dry_run=True) as session:
        session.run("set balance", SET_BALANCE, (10**9, 1))
    assert balance_of(save_path, 1) == before


def test_dry_run_reports_real_row_counts(save_path):
    """Counts are measured by executing inside a rolled-back transaction, not
    predicted by parsing SQL — so they cannot drift from reality."""
    with SaveSession(save_path, dry_run=True) as session:
        change = session.run("set every balance", SET_ALL_BALANCES, (1,))
    assert change.rows_affected == 11
    assert change.applied is False


def test_dry_run_leaves_the_file_byte_identical(save_path):
    before = save_path.read_bytes()
    with SaveSession(save_path, dry_run=True) as session:
        session.run("a", SET_ALL_BALANCES, (1,))
        session.run("b", "UPDATE Difficulty_RaceSim SET AIPerformance = ?;", (4,))
    assert save_path.read_bytes() == before


def test_dry_run_summary_says_so(save_path):
    with SaveSession(save_path, dry_run=True) as session:
        session.run("set balance", SET_BALANCE, (1, 1))
        text = session.summary()
    assert "DRY RUN" in text
    assert "nothing was written" in text


# -- applying --------------------------------------------------------------
def test_changes_are_recorded(save_path):
    with SaveSession(save_path) as session:
        session.run("balance", SET_BALANCE, (10**9, 1))
        session.run("difficulty", "UPDATE Difficulty_RaceSim SET AIPerformance = ?;", (4,))
    assert len(session.changes) == 2
    assert all(c.applied for c in session.changes)
    assert session.changes[0].rows_affected == 1


def test_a_targeted_update_leaves_rivals_alone(save_path):
    """The defect this package exists to fix: the original UPDATE had no WHERE,
    so all 11 teams got the money, including every AI rival."""
    rival_before = balance_of(save_path, 7)
    with SaveSession(save_path) as session:
        change = session.run("my balance", SET_BALANCE, (10**9, 1))

    assert change.rows_affected == 1
    assert balance_of(save_path, 1) == 10**9
    assert balance_of(save_path, 7) == rival_before


def test_exception_rolls_back_every_change_in_the_session(save_path):
    before = balance_of(save_path, 1)
    with pytest.raises(RuntimeError), SaveSession(save_path) as session:
        session.run("balance", SET_BALANCE, (10**9, 1))
        raise RuntimeError("interrupted mid-session")
    assert balance_of(save_path, 1) == before, "a partial edit must not survive"


def test_backup_survives_a_rolled_back_session(save_path):
    """The write is undone but the backup stays — if the rollback itself were
    unreliable, the copy is the fallback."""
    with pytest.raises(RuntimeError), SaveSession(save_path) as session:
        backup = session.backup_path
        session.run("balance", SET_BALANCE, (1, 1))
        raise RuntimeError("boom")
    assert backup.exists()


# -- schema guards ---------------------------------------------------------
def test_require_columns_passes_on_the_real_schema(save_path):
    with SaveSession(save_path, dry_run=True) as session:
        session.require_columns("Finance_TeamBudget_SpendingBuckets", "UsedAmount", "TeamID")


def test_require_columns_fails_on_a_renamed_column(save_path):
    """Game patches move columns. Failing up front beats a half-applied edit."""
    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(NotASaveError, match="missing expected column"):
            session.require_columns("Finance_TeamBalance", "CashMoney")


def test_require_columns_fails_on_a_missing_table(save_path):
    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(NotASaveError, match="not in this save"):
            session.require_columns("Table_That_Does_Not_Exist", "x")


def test_session_outside_a_with_block_raises(save_path):
    session = SaveSession(save_path)
    with pytest.raises(RuntimeError, match="not open"):
        _ = session.db


def test_summary_with_no_changes(save_path):
    with SaveSession(save_path, dry_run=True) as session:
        assert session.summary() == "no changes"
