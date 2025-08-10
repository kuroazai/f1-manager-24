import sqlite3
from typing import Any, Iterable, List, Sequence

class SQLiteDB:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.conn = None

    def connect(self) -> None:
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.commit()

        if self.conn:
            self.conn.close()
            self.conn = None

    def tables(self) -> List[str]:
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        return [row["name"] for row in cur.fetchall()]

    def execute(self, sql: str, params: Sequence[Any] = ()) -> List[sqlite3.Row]:
        cur = self.conn.execute(sql, params)
        return cur.fetchall()

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]) -> None:
        self.conn.executemany(sql, seq_of_params)
        self.conn.commit()

    def has_column(self, table: str, column_name: str) -> bool:
        cur = self.conn.execute(f"PRAGMA table_info({table});")
        cols = [row[1] for row in cur.fetchall()]
        return column_name in cols