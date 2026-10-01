"""Car parts: stat values and development speed."""
from __future__ import annotations

from ..enums import PartsEnumStats
from ..save import SaveSession
from .base import operation

#: Matches the shipped game values. "Emergency" at 0 means no time penalty.
DEFAULT_DEV_SPEEDS = {
    "Normal": 3,
    "Rushed": 4,
    "Intense": 2,
    "Emergency": 0,
}


@operation(
    "parts.max-stats",
    "Raise every part stat to the best value already present in the save",
    requires={"Parts_Designs_StatValues": ("PartStat", "Value", "UnitValue")},
)
def max_part_stats(session: SaveSession) -> None:
    """For each part stat, set every design to the best value in the save.

    The original iterated `PartsEnumType` (Engine, ERS, Gearbox...) while
    filtering on the `PartStat` column, which holds `PartsEnumStats` values. The
    data uses 0-15; `PartsEnumType` only covers 0-8, so seven stats were silently
    skipped - among them Power, HighSpeedDownforce, OperationalRange and
    Durability. It also logged the wrong names throughout.
    """
    for stat in PartsEnumStats:
        row = session.db.query(
            "SELECT MAX(Value) AS v, MAX(UnitValue) AS u "
            "FROM Parts_Designs_StatValues WHERE PartStat = ?;",
            (stat.value,),
        )[0]
        best_value, best_unit = row["v"], row["u"]

        if best_value is None and best_unit is None:
            continue  # stat not present in this save

        if best_value is not None:
            session.run(
                f"{stat.name}: Value -> {best_value}",
                "UPDATE Parts_Designs_StatValues SET Value = ? WHERE PartStat = ?;",
                (best_value, stat.value),
            )
        if best_unit is not None:
            session.run(
                f"{stat.name}: UnitValue -> {best_unit}",
                "UPDATE Parts_Designs_StatValues SET UnitValue = ? WHERE PartStat = ?;",
                (best_unit, stat.value),
            )


@operation(
    "parts.dev-speed",
    "Set the part development speed multipliers",
    requires={"Parts_Enum_DevSpeeds": ("Name", "SpeedMultiplier")},
)
def set_dev_speeds(session: SaveSession) -> None:
    """Rewrite the development speed multipliers."""
    for name, multiplier in DEFAULT_DEV_SPEEDS.items():
        session.run(
            f"dev speed {name} -> {multiplier}",
            "UPDATE Parts_Enum_DevSpeeds SET SpeedMultiplier = ? WHERE Name = ?;",
            (multiplier, name),
        )
