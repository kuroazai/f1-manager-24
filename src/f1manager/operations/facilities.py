"""Headquarters buildings."""
from __future__ import annotations

from ..enums import BuildingEnumsTypes, BuildingStates
from ..save import SaveSession
from .base import operation


def best_building_per_type(session: SaveSession) -> dict[BuildingEnumsTypes, int]:
    """Highest-upgrade BuildingID available for each building type.

    Reads what the save already contains rather than inventing IDs, so this cannot
    point the HQ at a building the game does not know about.
    """
    types = tuple(int(t) for t in BuildingEnumsTypes)
    placeholders = ",".join("?" * len(types))
    rows = session.db.query(
        f"""
        SELECT b.Type, b.BuildingID, b.UpgradeLevel
        FROM Buildings b
        INNER JOIN (
            SELECT Type, MAX(UpgradeLevel) AS MaxUpgrade
            FROM Buildings
            WHERE Type IN ({placeholders})
            GROUP BY Type
        ) m ON b.Type = m.Type AND b.UpgradeLevel = m.MaxUpgrade
        ORDER BY b.Type;
        """,
        types,
    )

    out: dict[BuildingEnumsTypes, int] = {}
    for row in rows:
        try:
            out[BuildingEnumsTypes(int(row["Type"]))] = int(row["BuildingID"])
        except ValueError:
            continue  # a type this package does not know about; leave it alone
    return out


@operation(
    "facilities.max",
    "Set every HQ building to its highest available upgrade",
    requires={
        "Buildings": ("Type", "BuildingID", "UpgradeLevel"),
        "Buildings_HQ": ("BuildingID", "BuildingState", "BuildingType"),
    },
)
def max_facilities(session: SaveSession) -> None:
    """Point each HQ slot at the best building of its type and mark it open."""
    best = best_building_per_type(session)
    if not best:
        raise RuntimeError(
            "no buildings found - this save may not have an HQ yet, "
            "or the Buildings table is laid out differently in this game version"
        )

    for building_type, building_id in best.items():
        session.run(
            f"{building_type.name} -> building {building_id}, OPEN",
            "UPDATE Buildings_HQ SET BuildingID = ?, BuildingState = ?, WorkDone = NULL "
            "WHERE BuildingType = ?;",
            (building_id, BuildingStates.OPEN.value, int(building_type)),
        )
