"""The operations, and the registry that guards them."""
from __future__ import annotations

import pytest

from f1manager.enums import BuildingStates, DifficultyLevels, PartsEnumStats
from f1manager.operations import all_operations, get
from f1manager.save import NotASaveError, SaveSession

from .conftest import balance_of, read_one


# -- registry --------------------------------------------------------------
def test_operations_are_registered():
    names = {op.name for op in all_operations()}
    assert {
        "finance.balance", "finance.clear-spend", "difficulty.ai",
        "parts.max-stats", "parts.dev-speed", "facilities.max",
    } <= names


def test_unknown_operation_lists_the_valid_ones():
    with pytest.raises(KeyError, match="unknown operation"):
        get("finance.print-money")


def test_every_operation_declares_what_it_touches():
    """An operation with no declared schema cannot be schema-checked, which
    defeats the guard. Treat an empty `requires` as a bug."""
    for op in all_operations():
        assert op.requires, f"{op.name} declares no tables"


def test_every_operation_has_a_summary():
    for op in all_operations():
        assert op.summary and op.summary[0].isupper()


def test_parameters_are_introspectable(save_path):
    op = get("finance.balance")
    names = {p.name for p in op.parameters}
    assert names == {"team_id", "amount"}
    assert "session" not in names


def test_schema_check_runs_before_the_operation(save_path, monkeypatch):
    """A save missing a required column must fail without any write."""
    op = get("finance.balance")
    with SaveSession(save_path, dry_run=True) as session:
        def refuse(*_a, **_k):
            raise NotASaveError("simulated schema mismatch")

        monkeypatch.setattr(session, "require_columns", refuse)
        with pytest.raises(NotASaveError):
            op(session, team_id=1, amount=1)
    assert not session.changes, "nothing should have run"


# -- finance ---------------------------------------------------------------
def test_balance_targets_one_team_only(save_path):
    rival_before = balance_of(save_path, 7)
    with SaveSession(save_path) as session:
        get("finance.balance")(session, team_id=1, amount=10**9)

    assert balance_of(save_path, 1) == 10**9
    assert balance_of(save_path, 7) == rival_before
    assert session.changes[0].rows_affected == 1


def test_balance_can_target_a_different_team(save_path):
    with SaveSession(save_path) as session:
        get("finance.balance")(session, team_id=5, amount=42)
    assert balance_of(save_path, 5) == 42
    assert balance_of(save_path, 1) != 42


def test_clear_spend_targets_one_team(save_path):
    with SaveSession(save_path) as session:
        get("finance.clear-spend")(session, team_id=2)
    used = read_one(save_path,
                    "SELECT UsedAmount FROM Finance_TeamBudget_SpendingBuckets WHERE TeamID = ?;",
                    (2,))
    other = read_one(
        save_path,
        "SELECT UsedAmount FROM Finance_TeamBudget_SpendingBuckets WHERE TeamID = ?;",
        (3,),
    )
    assert used == 0
    assert other == 250000, "another team's cap usage must be untouched"


# -- difficulty ------------------------------------------------------------
def test_difficulty_accepts_a_level_name(save_path):
    with SaveSession(save_path) as session:
        get("difficulty.ai")(session, level="veryhard")
    assert read_one(save_path, "SELECT AIPerformance FROM Difficulty_RaceSim;") \
        == DifficultyLevels.VERYHARD.value


def test_difficulty_rejects_an_unknown_level(save_path):
    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(ValueError, match="unknown difficulty"):
            get("difficulty.ai")(session, level="nightmare")


# -- parts -----------------------------------------------------------------
def test_max_stats_covers_all_sixteen_stats(save_path):
    """The original iterated PartsEnumType (0-8) against a column holding
    PartsEnumStats (0-15), silently skipping Power, HighSpeedDownforce,
    OperationalRange and Durability."""
    with SaveSession(save_path) as session:
        get("parts.max-stats")(session)

    touched = {
        label.split(":")[0]
        for label in (c.label for c in session.changes)
    }
    assert PartsEnumStats.Power.name in touched
    assert PartsEnumStats.HighSpeedDownforce.name in touched
    assert PartsEnumStats.Durability.name in touched
    assert PartsEnumStats.OperationalRange.name in touched


def test_max_stats_raises_the_low_design_to_the_best(save_path):
    """Fixture gives each stat a high (10+stat) and a low (5+stat) design."""
    stat = PartsEnumStats.Power.value
    with SaveSession(save_path) as session:
        get("parts.max-stats")(session)

    values = read_one(
        save_path,
        "SELECT COUNT(DISTINCT Value) FROM Parts_Designs_StatValues WHERE PartStat = ?;",
        (stat,),
    )
    best = read_one(
        save_path,
        "SELECT MAX(Value) FROM Parts_Designs_StatValues WHERE PartStat = ?;",
        (stat,),
    )
    assert values == 1, "every design for the stat should now share one value"
    assert best == 10 + stat


def test_dev_speeds_are_rewritten(save_path):
    with SaveSession(save_path) as session:
        get("parts.dev-speed")(session)
    def multiplier(name: str) -> int:
        return read_one(
            save_path,
            "SELECT SpeedMultiplier FROM Parts_Enum_DevSpeeds WHERE Name = ?;",
            (name,),
        )

    assert multiplier("Emergency") == 0
    assert multiplier("Rushed") == 4


# -- facilities ------------------------------------------------------------
def test_facilities_picks_the_highest_upgrade_level(save_path):
    from f1manager.operations.facilities import best_building_per_type

    with SaveSession(save_path, dry_run=True) as session:
        best = best_building_per_type(session)

    assert len(best) == 16, "one building per type"
    for building_id in best.values():
        level = read_one(save_path, "SELECT UpgradeLevel FROM Buildings WHERE BuildingID = ?;",
                         (building_id,))
        assert level == 2, "should pick the top upgrade level, not the first row"


def test_facilities_sets_hq_open(save_path):
    with SaveSession(save_path) as session:
        get("facilities.max")(session)

    states = read_one(save_path,
                      "SELECT COUNT(*) FROM Buildings_HQ WHERE BuildingState != ?;",
                      (BuildingStates.OPEN.value,))
    assert states == 0, "every HQ slot should be marked OPEN"
    unfinished = read_one(
        save_path, "SELECT COUNT(*) FROM Buildings_HQ WHERE WorkDone IS NOT NULL;"
    )
    assert unfinished == 0


# -- dry run across every operation ---------------------------------------
@pytest.mark.parametrize("name", [
    "finance.balance", "finance.clear-spend", "difficulty.ai",
    "parts.max-stats", "parts.dev-speed", "facilities.max",
])
def test_no_operation_writes_in_dry_run(save_path, name):
    """The guarantee that makes this tool safe to point at a real save."""
    before = save_path.read_bytes()
    with SaveSession(save_path, dry_run=True) as session:
        get(name)(session)
        assert session.changes, f"{name} reported no planned changes"
        assert all(c.applied is False for c in session.changes)
    assert save_path.read_bytes() == before
