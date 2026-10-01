"""Name resolution and driver stats.

Name resolution is the part most likely to go quietly wrong: the game stores
`[StaffName_Forename_Male_Max]`, and a surname alone can match two people.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from f1manager.db import SaveDatabase
from f1manager.enums import PerformanceStatTypes
from f1manager.operations import get
from f1manager.operations.drivers import resolve_stat
from f1manager.save import SaveSession
from f1manager.staff import clean_name_token, find_by_name, load_staff, normalise, resolve_one

from .conftest import read_one


# -- name decoding ---------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("[StaffName_Forename_Male_Max]", "Max"),
        ("[StaffName_Surname_Verstappen]", "Verstappen"),
        ("[StaffName_Forename_Female_Susie]", "Susie"),
        ("[StaffName_Surname_Van_Der_Garde]", "Van Der Garde"),
        ("Plain", "Plain"),
        ("", ""),
        (None, ""),
    ],
)
def test_clean_name_token(raw, expected):
    assert clean_name_token(raw) == expected


def test_normalise_collapses_whitespace_and_case():
    assert normalise("  Max   VERSTAPPEN ") == "max verstappen"
    assert normalise(None) == ""


def test_load_staff_decodes_every_name(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        people = load_staff(db)
    full_names = {p.full for p in people}
    assert "Max Verstappen" in full_names
    assert not any("[" in n for n in full_names), "brackets should be gone"
    assert not any("StaffName" in n for n in full_names), "prefixes should be gone"


# -- lookup ----------------------------------------------------------------
def test_find_by_full_name(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        matches = find_by_name(db, "max verstappen")
    assert len(matches) == 1
    assert matches[0].staff_id == 1


def test_find_by_surname_alone(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        matches = find_by_name(db, "Norris")
    assert [m.staff_id for m in matches] == [2]


def test_ambiguous_surname_returns_both(save_path):
    """There have been two Schumachers. Returning one silently would edit the
    wrong driver's stats and look like it worked."""
    with SaveDatabase(save_path, read_only=True) as db:
        matches = find_by_name(db, "Schumacher")
    assert {m.staff_id for m in matches} == {3, 4}


def test_resolve_one_refuses_an_ambiguous_name(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        with pytest.raises(LookupError, match="ambiguous"):
            resolve_one(db, "Schumacher")


def test_resolve_one_rejects_an_unknown_name(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        with pytest.raises(LookupError, match="no one in this save"):
            resolve_one(db, "Ayrton Senna")


def test_resolve_one_disambiguates_with_a_full_name(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        assert resolve_one(db, "Mick Schumacher").staff_id == 3
        assert resolve_one(db, "Ralf Schumacher").staff_id == 4


def test_empty_name_matches_nothing(save_path):
    with SaveDatabase(save_path, read_only=True) as db:
        assert find_by_name(db, "   ") == []


# -- stat name resolution --------------------------------------------------
@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("Speed", PerformanceStatTypes.SPEED),
        ("speed", PerformanceStatTypes.SPEED),
        ("high speed downforce", PerformanceStatTypes.HIGH_SPEED_DOWNFORCE),
        ("high-speed-downforce", PerformanceStatTypes.HIGH_SPEED_DOWNFORCE),
        (36, PerformanceStatTypes.SPEED),
    ],
)
def test_resolve_stat(key, expected):
    assert resolve_stat(key) is expected


def test_unknown_stat_name_is_rejected_with_the_valid_list(save_path):
    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(ValueError, match="unknown stat"):
            get("drivers.set-stats")(
                session, name="Max Verstappen", stats='{"Turbo Boost": 99}'
            )


# -- applying stats --------------------------------------------------------
def test_set_stats_updates_the_named_driver(save_path):
    with SaveSession(save_path) as session:
        get("drivers.set-stats")(
            session, name="Max Verstappen", stats='{"Speed": 20, "Consistency": 19}'
        )
    speed = read_one(
        save_path,
        "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
        (1, PerformanceStatTypes.SPEED.value),
    )
    assert speed == 20


def test_set_stats_leaves_other_drivers_alone(save_path):
    before = read_one(
        save_path,
        "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
        (2, PerformanceStatTypes.SPEED.value),
    )
    with SaveSession(save_path) as session:
        get("drivers.set-stats")(session, name="Max Verstappen", stats='{"Speed": 20}')
    after = read_one(
        save_path,
        "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
        (2, PerformanceStatTypes.SPEED.value),
    )
    assert after == before


def test_stats_are_clamped_to_the_per_stat_max(save_path):
    """Mick's Speed has Max 15 in the fixture. Writing 20 should land on 15,
    because a value above Max is one the game's own UI cannot show."""
    with SaveSession(save_path) as session:
        get("drivers.set-stats")(session, name="Mick Schumacher", stats='{"Speed": 20}')
    value = read_one(
        save_path,
        "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
        (3, PerformanceStatTypes.SPEED.value),
    )
    assert value == 15


def test_clamping_can_be_turned_off(save_path):
    with SaveSession(save_path) as session:
        get("drivers.set-stats")(
            session, name="Mick Schumacher", stats='{"Speed": 20}', respect_max=False
        )
    value = read_one(
        save_path,
        "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
        (3, PerformanceStatTypes.SPEED.value),
    )
    assert value == 20


def test_missing_arguments_are_rejected(save_path):
    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(ValueError, match="needs --name"):
            get("drivers.set-stats")(session)
        with pytest.raises(ValueError, match="needs --stats"):
            get("drivers.set-stats")(session, name="Max Verstappen")


def test_malformed_json_is_rejected_clearly(save_path):
    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(ValueError, match="not valid JSON"):
            get("drivers.set-stats")(session, name="Max Verstappen", stats="{oops")


def test_set_stats_writes_nothing_in_dry_run(save_path):
    before = save_path.read_bytes()
    with SaveSession(save_path, dry_run=True) as session:
        get("drivers.set-stats")(session, name="Max Verstappen", stats='{"Speed": 20}')
        assert session.changes
    assert save_path.read_bytes() == before


# -- bulk file -------------------------------------------------------------
def test_load_file_applies_every_resolvable_driver(save_path, tmp_path):
    payload = {"Max Verstappen": {"Speed": 20}, "Lando Norris": {"Speed": 19}}
    f = tmp_path / "drivers.json"
    f.write_text(json.dumps(payload), encoding="utf-8")

    with SaveSession(save_path) as session:
        get("drivers.load-file")(session, path=str(f))

    assert read_one(
        save_path,
        "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
        (1, PerformanceStatTypes.SPEED.value),
    ) == 20
    assert read_one(
        save_path,
        "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
        (2, PerformanceStatTypes.SPEED.value),
    ) == 19


def test_load_file_skips_unknown_drivers_by_default(save_path, tmp_path):
    """One retired driver in a file of twenty should not cost the other nineteen."""
    payload = {"Ayrton Senna": {"Speed": 20}, "Max Verstappen": {"Speed": 20}}
    f = tmp_path / "drivers.json"
    f.write_text(json.dumps(payload), encoding="utf-8")

    with SaveSession(save_path) as session:
        get("drivers.load-file")(session, path=str(f))

    assert read_one(
        save_path,
        "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
        (1, PerformanceStatTypes.SPEED.value),
    ) == 20


def test_load_file_can_be_strict(save_path, tmp_path):
    f = tmp_path / "drivers.json"
    f.write_text(json.dumps({"Ayrton Senna": {"Speed": 20}}), encoding="utf-8")

    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(LookupError):
            get("drivers.load-file")(session, path=str(f), skip_missing=False)


def test_load_file_rejects_a_missing_path(save_path, tmp_path):
    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(ValueError, match="no driver file"):
            get("drivers.load-file")(session, path=str(tmp_path / "absent.json"))


def test_bundled_driver_file_loads_without_raising(save_path):
    """Regression: the shipped preset carries OVR, Growth, Aggression and
    Marketability, none of which are performance stats. Before load-file became
    tolerant, the first of them aborted the whole file."""
    bundled = Path(__file__).resolve().parents[1] / "data/drivers/drivers_at_peak_2025.json"
    if not bundled.exists():
        pytest.skip("bundled driver preset not present")

    with SaveSession(save_path, dry_run=True) as session:
        get("drivers.load-file")(session, path=str(bundled))

    assert session.changes, "should have planned changes for the drivers it found"
    applied_stats = {c.label.split(": ")[1].split(" ->")[0] for c in session.changes}
    assert "OVR" not in applied_stats
    assert "CORNERING" in applied_stats


def test_unknown_stats_still_raise_for_a_single_explicit_edit(save_path):
    """Tolerance is for bulk files. A hand-typed stat name that does not exist is
    a typo and should say so."""
    with SaveSession(save_path, dry_run=True) as session:
        with pytest.raises(ValueError, match="unknown stat"):
            get("drivers.set-stats")(session, name="Max Verstappen", stats='{"OVR": 99}')
