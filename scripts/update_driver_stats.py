from typing import Any, Dict
from databases.db_engine import SQLiteDB
import json
from utils.find_drivers import find_staff_id_by_name
from loguru import logger
from data_classes.enums import PerformanceStatTypes
from typing import Union, Dict, Any


def get_stat_enum(x: Union[int, str]) -> PerformanceStatTypes:
    if isinstance(x, int):
        return PerformanceStatTypes(x)
    key = x.upper().replace(" ", "_")
    return PerformanceStatTypes[key]


def update_driver_stats(
    db: SQLiteDB,
    driver_id: int,
    updates: Dict[str, Any]
) -> None:
    logger.info(f"Updating DriverID {driver_id} with data: {json.dumps(updates)}")
    # Show current row
    before = db.execute(
        "SELECT * FROM Staff_PerformanceStats WHERE StaffID = ?;",
        (driver_id,)
    )
    if not before:
        logger.info(f"No driver found with DriverID={driver_id}")
        return

    for stat_name, stat_value in updates.items():
        try:
            stat_enum = get_stat_enum(stat_name)
            stat_id = stat_enum.value
        except Exception as e:
            logger.warning(f"Stat '{stat_name}' not found in PerformanceStatTypes enum. Skipping. Error: {e}")
            continue
        # Update stat value in DB
        db.execute(
            "UPDATE Staff_PerformanceStats SET Val = ? WHERE StaffID = ? AND StatID = ?;",
            (stat_value, driver_id, stat_id)
        )
        # Show updated value
        after = db.execute(
            "SELECT Val FROM Staff_PerformanceStats WHERE StaffID = ? AND StatID = ?;",
            (driver_id, stat_id)
        )
        if after:
            logger.info(f"Updated {stat_name} (StatID {stat_id}): {after[0]['Val']}")
        else:
            logger.warning(f"Failed to fetch updated value for {stat_name} (StatID {stat_id})")
    # TODO: map the before to our driver class


def load_drivers(json_file: str) -> Dict[int, Dict[str, Any]]:
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data

def update_all_drivers(
    db: SQLiteDB,
    json_file: str
) -> None:
    drivers = load_drivers(json_file)
    for driver_name, updates in drivers.items():
        logger.info(f"Updating DriverID {driver_name} with data: {json.dumps(updates)}")
        driver_id, _ = find_staff_id_by_name(db, driver_name)
        if driver_id is None:
            logger.warning(f"Driver '{driver_name}' not found in database.")
            continue
        update_driver_stats(db, driver_id, updates)

if __name__ == "__main__":
    json_file = "../data/drivers/drivers_at_peak_2025.json"
    db = SQLiteDB("../main.db")
    db.connect()
    update_all_drivers(db, json_file)

    db.close()
