"""SQLite access for an F1 Manager save database.

Deliberately boring: open, query, execute, commit, close. The interesting
behaviour - backups, dry-run, validation - lives in `save.py`, because mixing
safety policy into the database wrapper is how you end up with a `close()` that
silently commits.

Three rules this module enforces that the original did not:

1. **Commits are explicit.** `execute()` never commits. The old wrapper committed
   inside `close()`, which meant an UPDATE persisted only as a side effect of
   closing, an exception before close silently discarded it, and a read-only
   session committed anyway.
2. **Read-only means read-only**, via SQLite's `mode=ro` URI, so the file cannot
   be written even by a bug.
3. **Identifiers are validated, not interpolated.** PRAGMA statements cannot take
   bound parameters, so table names are checked against a strict pattern before
   they go anywhere near SQL.
"""
from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

#: SQLite identifiers we are willing to interpolate into a PRAGMA.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DatabaseError(RuntimeError):
    """Raised for misuse of this wrapper, as distinct from sqlite3's own errors."""


def _check_identifier(name: str) -> str:
    """Reject anything that is not a plain SQL identifier.

    PRAGMA cannot be parameterised, so a table name has to be interpolated. This
    is the guard that makes that safe.
    """
    if not _IDENTIFIER.match(name):
        raise ValueError(f"not a valid SQL identifier: {name!r}")
    return name


class SaveDatabase:
    """A connection to an F1 Manager save.

    Use as a context manager. On a clean exit a writable connection commits; on an
    exception it rolls back. A read-only connection does neither.

        with SaveDatabase("main.db", read_only=True) as db:
            print(len(db.tables()))
    """

    def __init__(self, path: str | Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        self._conn: sqlite3.Connection | None = None

    # -- lifecycle ---------------------------------------------------------
    def connect(self) -> SaveDatabase:
        if self._conn is not None:
            return self
        if not self.path.exists():
            raise FileNotFoundError(f"no save database at {self.path}")
        if self.read_only:
            # The URI form is the only way to get a genuinely read-only handle.
            uri = f"file:{self.path.as_posix()}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
        else:
            self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        return self

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DatabaseError("not connected - call connect() or use a with block")
        return self._conn

    @property
    def connected(self) -> bool:
        return self._conn is not None

    def commit(self) -> None:
        if self.read_only:
            raise DatabaseError("cannot commit a read-only connection")
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        """Close without committing. Closing twice is safe."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> SaveDatabase:
        return self.connect()

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._conn is not None and not self.read_only:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        self.close()

    # -- introspection -----------------------------------------------------
    def tables(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        return [row["name"] for row in rows]

    def has_table(self, table: str) -> bool:
        rows = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;",
            (table,),
        )
        return rows.fetchone() is not None

    def columns(self, table: str) -> list[str]:
        _check_identifier(table)
        rows = self.conn.execute(f"PRAGMA table_info({table});")
        return [row[1] for row in rows]

    def has_column(self, table: str, column: str) -> bool:
        return column in self.columns(table)

    def row_count(self, table: str) -> int:
        _check_identifier(table)
        row = self.conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()
        return int(row[0])

    # -- statements --------------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        """Run a SELECT and return every row."""
        return self.conn.execute(sql, params).fetchall()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run a statement and return the number of rows it affected.

        Does **not** commit. Returning the row count is what lets a caller check
        that a statement touched what it expected - the original wrapper returned
        `fetchall()` for an UPDATE, which is always empty and therefore told the
        caller nothing.
        """
        cursor = self.conn.execute(sql, params)
        return cursor.rowcount

    def executemany(self, sql: str, rows: Iterable[Sequence[Any]]) -> int:
        """Run a statement over many parameter sets. Does not commit."""
        cursor = self.conn.executemany(sql, rows)
        return cursor.rowcount
