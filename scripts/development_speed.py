from databases.db_engine import SQLiteDB
from loguru import logger

def set_development_speeds(db: SQLiteDB) -> None:
    logger.info("Setting development speeds...")

    speed_multipliers = {
        "Normal": 3,
        "Rushed": 4,
        "Intense": 2,
        "Emergency": 0
    }

    for name, multiplier in speed_multipliers.items():
        logger.info(f"Setting {name} speed multiplier to {multiplier}")
        db.execute(
            "UPDATE Parts_Enum_DevSpeeds SET SpeedMultiplier = ? WHERE Name = ?;",
            (multiplier, name)
        )

    logger.info("Development speeds updated successfully.")

if __name__ == "__main__":
    db = SQLiteDB("../main.db")
    db.connect()
    tbls = db.tables()
    print(f"Tables in the database: {tbls}")

    set_development_speeds(db)

    db.close()
