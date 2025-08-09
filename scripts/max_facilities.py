from databases.db_engine import SQLiteDB
from loguru import logger
from typing import  Dict, Tuple
from data_classes.enums import BuildingEnumsTypes, BuildingStates


def get_max_upgrade_by_type(db: SQLiteDB) -> Dict[BuildingEnumsTypes, Tuple[int, int]]:
    vals = tuple(int(v) for v in BuildingEnumsTypes)
    placeholders = ",".join(["?"] * len(vals))

    sql = f"""
    SELECT b.Type, b.BuildingID, b.UpgradeLevel
    FROM Buildings b
    INNER JOIN (
        SELECT Type, MAX(UpgradeLevel) AS MaxUpgrade
        FROM Buildings
        WHERE Type IN ({placeholders})
        GROUP BY Type
    ) m ON b.Type = m.Type AND b.UpgradeLevel = m.MaxUpgrade
    ORDER BY b.Type;
    """

    rows = db.execute(sql, vals)
    out: Dict[BuildingEnumsTypes, Tuple[int, int]] = {}
    for r in rows:
        bt = int(r["Type"])
        bid = int(r["BuildingID"])
        lvl = int(r["UpgradeLevel"])
        try:
            out[BuildingEnumsTypes(bt)] = (bid, lvl)
        except ValueError:
            continue
    return out


def set_hq_to_max_level(db: SQLiteDB) -> None:
    max_levels = get_max_upgrade_by_type(db)

    for btype, (bid, _) in max_levels.items():
        logger.info(f"Setting HQ for {btype.name} to BuildingID {bid}")
        db.execute(
            """
            UPDATE Buildings_HQ
            SET BuildingID = ?,
                BuildingState = ?,
                WorkDone = NULL
            WHERE BuildingType = ?;
            """,
            (bid, BuildingStates.OPEN.value, int(btype))
        )


if __name__ == "__main__":
    json_file = "../data/drivers/drivers_at_peak_2025.json"
    db = SQLiteDB("../main.db")
    db.connect()
    tbls = db.tables()
    print(f"Tables in the database: {tbls}")

    set_hq_to_max_level(db)

    db.close()