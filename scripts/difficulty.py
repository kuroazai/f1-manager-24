from databases.db_engine import SQLiteDB
from loguru import logger
from data_classes.enums import DifficultyLevels
from typing import Union


def set_difficulty_level(
    db: SQLiteDB,
    level: Union[int, str] = DifficultyLevels.VERYHARD.value
) -> None:
    if isinstance(level, str):
        level = DifficultyLevels[level.upper()].value

    logger.info(f"Setting Difficulty_RaceSim - AIPerformance to {level}")

    db.execute(
        "UPDATE Difficulty_RaceSim SET AIPerformance = ?;",
        (level,)
    )

    logger.info("Difficulty levels updated successfully.")


if __name__ == "__main__":
    db = SQLiteDB("../main.db")
    db.connect()
    tbls = db.tables()
    print(f"Tables in the database: {tbls}")

    set_difficulty_level(db, DifficultyLevels.VERYHARD.value)

    db.close()