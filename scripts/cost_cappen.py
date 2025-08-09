from databases.db_engine import SQLiteDB
from loguru import logger


def set_team_balance(db: SQLiteDB, balance: int = 1_000_000_000) -> None:
    logger.info(f"Setting team balance to {balance}")
    db.execute(
        "UPDATE Finance_TeamBalance SET Balance = ?;",
        (balance,)
    )
    logger.info("Team balance updated successfully.")

def set_spending_buckets(db: SQLiteDB, used_amount: int = 0) -> None:
    logger.info(f"Setting spending buckets used amount to {used_amount}")
    db.execute(
        "UPDATE Finance_TeamBudget_SpendingBuckets SET UsedAmount = ?;",
        (used_amount,)
    )
    logger.info("Spending buckets updated successfully.")


if __name__ == "__main__":
    db = SQLiteDB("../main.db")
    db.connect()
    tbls = db.tables()
    print(f"Tables in the database: {tbls}")

    set_team_balance(db, 1_000_000_000)
    set_spending_buckets(db, 0)

    db.close()
