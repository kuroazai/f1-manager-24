from databases.db_engine import SQLiteDB
from loguru import logger
from data_classes.enums import PartsEnumType

def update_part_designs_stat_values(db: SQLiteDB) -> None:
    logger.info("Updating Parts_Designs_StatValues...")

    for part_type in PartsEnumType:
        logger.info(f"Processing part type: {part_type.name}")

        max_val = db.execute(
            "SELECT MAX(Value) AS MaxVal FROM Parts_Designs_StatValues WHERE PartStat = ?;",
            (part_type.value,)
        )[0]['MaxVal']

        max_unit_val = db.execute(
            "SELECT MAX(UnitValue) AS MaxUnitVal FROM Parts_Designs_StatValues WHERE PartStat = ?;",
            (part_type.value,)
        )[0]['MaxUnitVal']

        if max_val is not None:
            logger.info(f"Setting Value to {max_val} for part type {part_type.name}")
            db.execute(
                "UPDATE Parts_Designs_StatValues SET Value = ? WHERE PartStat = ?;",
                (max_val, part_type.value)
            )

        if max_unit_val is not None:
            logger.info(f"Setting UnitValue to {max_unit_val} for part type {part_type.name}")
            db.execute(
                "UPDATE Parts_Designs_StatValues SET UnitValue = ? WHERE PartStat = ?;",
                (max_unit_val, part_type.value)
            )

    logger.info("Parts_Designs_StatValues updated successfully.")


if __name__ == "__main__":
    db = SQLiteDB("../main.db")
    db.connect()
    tbls = db.tables()
    print(f"Tables in the database: {tbls}")

    update_part_designs_stat_values(db)

    db.close()