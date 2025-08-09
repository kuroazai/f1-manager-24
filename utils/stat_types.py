from databases.db_engine import SQLiteDB

def print_performance_stat_types(db: SQLiteDB) -> None:
    rows = db.execute("SELECT Value, Name FROM Staff_Enum_PerformanceStatTypes;")
    for r in rows:
        print(f"Value: {r['Value']}, Name: {r['Name']}")

if __name__ == "__main__":
    db = SQLiteDB("../main.db")
    db.connect()
    tbls = db.tables()
    print(f"Tables in the database: {tbls}")
    print_performance_stat_types(db)
    db.close()
