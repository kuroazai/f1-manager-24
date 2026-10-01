"""Fixtures. Every test runs against a database built here — never a real save."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

#: Mirrors the shape of the real tables these tests touch, including the 11-team
#: Finance_TeamBalance that exposed the missing-WHERE bug in the original scripts.
SCHEMA = """
CREATE TABLE Finance_TeamBalance (TeamID INTEGER PRIMARY KEY, Balance INTEGER);
CREATE TABLE Finance_TeamBudget_SpendingBuckets (
    TeamID INTEGER, SeasonID INTEGER, Category INTEGER, IsReserved INTEGER,
    EstimatedSpending INTEGER, AllocatedAmount INTEGER, RemainingAmount INTEGER,
    Weight REAL, UsedAmount INTEGER
);
CREATE TABLE Difficulty_RaceSim (AIPerformance INTEGER);
CREATE TABLE Staff_BasicData (StaffID INTEGER PRIMARY KEY, FirstName TEXT, LastName TEXT);
-- Real column names, verified against a live save: StatID (not StatType),
-- plus a per-stat Max the operations clamp to.
CREATE TABLE Staff_PerformanceStats (StaffID INTEGER, StatID INTEGER, Val INTEGER, Max INTEGER);
CREATE TABLE Staff_Enum_PerformanceStatTypes (Value INTEGER, Name TEXT);
CREATE TABLE Parts_Designs_StatValues (
    DesignID INTEGER, PartStat INTEGER, Value INTEGER, UnitValue REAL,
    DesignFocus INTEGER, ExpertiseGain INTEGER, ExpertiseEffect INTEGER
);
CREATE TABLE Parts_Enum_DevSpeeds (Name TEXT, SpeedMultiplier INTEGER);
CREATE TABLE Buildings (BuildingID INTEGER PRIMARY KEY, Type INTEGER, UpgradeLevel INTEGER);
CREATE TABLE Buildings_HQ (
    BuildingType INTEGER, BuildingID INTEGER, BuildingState INTEGER, WorkDone INTEGER
);
"""


def _populate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    # 11 teams, as the real save has.
    conn.executemany(
        "INSERT INTO Finance_TeamBalance (TeamID, Balance) VALUES (?, ?);",
        [(i, 5_000_000) for i in range(1, 12)],
    )
    conn.executemany(
        "INSERT INTO Finance_TeamBudget_SpendingBuckets "
        "(TeamID, SeasonID, Category, IsReserved, EstimatedSpending, "
        " AllocatedAmount, RemainingAmount, Weight, UsedAmount) "
        "VALUES (?, 1, 0, 0, 0, 0, 0, 1.0, 250000);",
        [(i,) for i in range(1, 12)],
    )
    conn.execute("INSERT INTO Difficulty_RaceSim (AIPerformance) VALUES (2);")
    conn.executemany(
        "INSERT INTO Staff_BasicData (StaffID, FirstName, LastName) VALUES (?, ?, ?);",
        [
            (1, "[StaffName_Forename_Male_Max]", "[StaffName_Surname_Verstappen]"),
            (2, "[StaffName_Forename_Male_Lando]", "[StaffName_Surname_Norris]"),
            (3, "[StaffName_Forename_Male_Mick]", "[StaffName_Surname_Schumacher]"),
            (4, "[StaffName_Forename_Male_Ralf]", "[StaffName_Surname_Schumacher]"),
        ],
    )
    conn.executemany(
        "INSERT INTO Staff_PerformanceStats (StaffID, StatID, Val, Max) VALUES (?, ?, ?, ?);",
        [(1, 36, 18, 20), (1, 37, 17, 20), (2, 36, 16, 20), (3, 36, 12, 15)],
    )
    conn.executemany(
        "INSERT INTO Staff_Enum_PerformanceStatTypes (Value, Name) VALUES (?, ?);",
        [(36, "Speed"), (37, "Consistency"), (43, "Composure")],
    )
    # Parts: PartStat uses 0-15 (PartsEnumStats). Two designs per stat with
    # different values, so "raise to the best present" has something to do.
    rows = []
    for stat in range(16):
        rows.append((100 + stat, stat, 10 + stat, 1.0 + stat))
        rows.append((200 + stat, stat, 5 + stat, 0.5 + stat))
    conn.executemany(
        "INSERT INTO Parts_Designs_StatValues "
        "(DesignID, PartStat, Value, UnitValue, DesignFocus, ExpertiseGain, ExpertiseEffect) "
        "VALUES (?, ?, ?, ?, 0, 0, 0);",
        rows,
    )
    conn.executemany(
        "INSERT INTO Parts_Enum_DevSpeeds (Name, SpeedMultiplier) VALUES (?, ?);",
        [("Normal", 1), ("Rushed", 1), ("Intense", 1), ("Emergency", 10)],
    )
    # Buildings: types 1-16, three upgrade levels each.
    buildings = []
    bid = 1
    for btype in range(1, 17):
        for level in (0, 1, 2):
            buildings.append((bid, btype, level))
            bid += 1
    conn.executemany(
        "INSERT INTO Buildings (BuildingID, Type, UpgradeLevel) VALUES (?, ?, ?);",
        buildings,
    )
    conn.executemany(
        "INSERT INTO Buildings_HQ (BuildingType, BuildingID, BuildingState, WorkDone) "
        "VALUES (?, ?, ?, ?);",
        [(btype, 0, 1, 50) for btype in range(1, 17)],
    )
    conn.commit()


@pytest.fixture
def save_path(tmp_path: Path) -> Path:
    """A throwaway database with the shape of a real save."""
    path = tmp_path / "main.db"
    conn = sqlite3.connect(path)
    try:
        _populate(conn)
    finally:
        conn.close()
    return path


@pytest.fixture
def not_a_save(tmp_path: Path) -> Path:
    """A valid SQLite file that is not an F1 Manager save."""
    path = tmp_path / "shopping.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE items (name TEXT);")
        conn.commit()
    finally:
        conn.close()
    return path


def balance_of(path: Path, team_id: int) -> int:
    """Read a balance straight from disk, bypassing the package entirely.

    Tests that assert "nothing was written" have to look at the file itself,
    not at an abstraction that could be lying.
    """
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT Balance FROM Finance_TeamBalance WHERE TeamID = ?;", (team_id,)
        ).fetchone()
        return int(row[0])
    finally:
        conn.close()


def read_one(path, sql, params=()):
    """Read a single value straight from disk, bypassing the package."""
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        conn.close()
