"""Driver and staff performance stats."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..enums import PerformanceStatTypes
from ..save import SaveSession
from ..staff import resolve_one
from .base import operation


def resolve_stat(key: int | str) -> PerformanceStatTypes:
    """Accept either a stat id or a name like "Speed" / "high speed downforce"."""
    if isinstance(key, int):
        return PerformanceStatTypes(key)
    return PerformanceStatTypes[key.upper().replace(" ", "_").replace("-", "_")]


def _apply_stats(
    session: SaveSession,
    staff_id: int,
    label: str,
    stats: dict[str, Any],
    *,
    respect_max: bool,
    skip_unknown_stats: bool = False,
) -> list[str]:
    """Apply a name -> value mapping. Returns the stat names that were skipped.

    `skip_unknown_stats` exists because a driver file can legitimately carry
    attributes this table does not hold - OVR, Growth, Aggression and
    Marketability all appear in the bundled preset and are not performance stats.
    For a single explicit edit, an unknown name is a typo and should raise; for a
    bulk file it should not cost you the other 30 drivers.
    """
    skipped: list[str] = []
    for stat_name, value in stats.items():
        try:
            stat = resolve_stat(stat_name)
        except (KeyError, ValueError):
            if skip_unknown_stats:
                skipped.append(stat_name)
                continue
            valid = ", ".join(s.name for s in PerformanceStatTypes)
            raise ValueError(f"unknown stat {stat_name!r}. Valid: {valid}") from None

        target = int(value)
        if respect_max:
            # Staff_PerformanceStats carries a per-stat Max. Writing above it
            # produces a value the game's own UI cannot represent, so clamp by
            # default and let the caller opt out deliberately.
            rows = session.db.query(
                "SELECT Max FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
                (staff_id, stat.value),
            )
            if rows and rows[0]["Max"] is not None:
                ceiling = int(rows[0]["Max"])
                if target > ceiling:
                    target = ceiling

        session.run(
            f"{label}: {stat.name} -> {target}",
            "UPDATE Staff_PerformanceStats SET Val = ? WHERE StaffID = ? AND StatID = ?;",
            (target, staff_id, stat.value),
        )
    return skipped


@operation(
    "drivers.set-stats",
    "Set one person's performance stats",
    requires={
        "Staff_BasicData": ("StaffID", "FirstName", "LastName"),
        "Staff_PerformanceStats": ("StaffID", "StatID", "Val", "Max"),
    },
)
def set_driver_stats(
    session: SaveSession,
    *,
    name: str = "",
    stats: str = "",
    respect_max: bool = True,
) -> None:
    """Set stats for one driver by name.

    `stats` is JSON: '{"Speed": 20, "Consistency": 19}'.
    """
    if not name:
        raise ValueError("drivers.set-stats needs --name")
    if not stats:
        raise ValueError('drivers.set-stats needs --stats, e.g. \'{"Speed": 20}\'')

    try:
        parsed = json.loads(stats) if isinstance(stats, str) else stats
    except json.JSONDecodeError as exc:
        raise ValueError(f"--stats is not valid JSON: {exc}") from None

    person = resolve_one(session.db, name)
    _apply_stats(session, person.staff_id, person.full, parsed,
                 respect_max=bool(respect_max))


@operation(
    "drivers.load-file",
    "Apply a JSON file of driver stats to everyone it names",
    requires={
        "Staff_BasicData": ("StaffID", "FirstName", "LastName"),
        "Staff_PerformanceStats": ("StaffID", "StatID", "Val", "Max"),
    },
)
def load_driver_file(
    session: SaveSession,
    *,
    path: str = "data/drivers/drivers_at_peak_2025.json",
    respect_max: bool = True,
    skip_missing: bool = True,
) -> None:
    """Bulk-apply stats from a `{"Driver Name": {"Stat": value}}` file.

    Unresolvable or ambiguous names are reported and skipped by default rather
    than aborting the batch — one retired driver in a file of twenty should not
    cost you the other nineteen. Pass `--skip-missing false` to be strict.
    """
    data_path = Path(path)
    if not data_path.exists():
        raise ValueError(f"no driver file at {data_path}")

    payload = json.loads(data_path.read_text(encoding="utf-8"))
    missing_people: list[str] = []
    unknown_stats: set[str] = set()

    for driver_name, stats in payload.items():
        try:
            person = resolve_one(session.db, driver_name)
        except LookupError as exc:
            if skip_missing:
                missing_people.append(f"{driver_name}: {exc}")
                continue
            raise
        unknown_stats.update(
            _apply_stats(
                session,
                person.staff_id,
                person.full,
                stats,
                respect_max=bool(respect_max),
                skip_unknown_stats=True,
            )
        )

    if missing_people:
        print(f"not in this save ({len(missing_people)}):")
        for line in missing_people:
            print(f"  {line}")
    if unknown_stats:
        print(
            "not performance stats, ignored: "
            + ", ".join(sorted(unknown_stats))
        )
