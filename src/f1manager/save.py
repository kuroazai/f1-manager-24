"""Safe mutation of an F1 Manager save.

A save file is hours of someone's play and there is no undo. So every write in
this package goes through `SaveSession`, which guarantees three things:

1. **A timestamped backup exists before the first write.** Not advice in a README
   - a copy on disk, made automatically.
2. **`dry_run=True` cannot touch the save.** The statements genuinely run - but
   against a temporary copy, which is then deleted. The real file is never opened
   for writing, so "unchanged" is guaranteed by construction rather than by
   trusting a rollback to work. Row counts are measured, not predicted by parsing
   SQL.
3. **The file is checked for being an F1 Manager save** before anything runs, so a
   mistyped path fails immediately rather than part-way through.

    with SaveSession("main.db") as session:
        session.run(
            "set team balance",
            "UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?",
            (10**9, 1),
        )

    for change in session.changes:
        print(change)
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .db import SaveDatabase

#: Tables that any real F1 Manager save has. Used as a cheap sanity check so a
#: wrong path fails before a backup is taken, not after a statement half-runs.
SENTINEL_TABLES = (
    "Finance_TeamBalance",
    "Staff_BasicData",
    "Staff_Enum_PerformanceStatTypes",
)

BACKUP_SUFFIX = "%Y%m%d_%H%M%S"


class NotASaveError(ValueError):
    """The file opened does not look like an F1 Manager save database."""


@dataclass
class Change:
    """One statement, and how many rows it touched."""

    label: str
    sql: str
    params: tuple[Any, ...]
    rows_affected: int
    applied: bool

    def __str__(self) -> str:
        verb = "applied" if self.applied else "would affect"
        return f"{self.label}: {verb} {self.rows_affected} row(s)"


@dataclass
class SaveSession:
    """A scoped, backed-up, optionally read-only editing session.

    Args:
        path: the save database.
        dry_run: report what would change and write nothing.
        backup: take a timestamped copy before the first write. Leave this on
            unless you have your own backup; it is the only undo that exists.
        backup_dir: where copies go. Defaults to a `backups/` folder beside the save.
    """

    path: Path
    dry_run: bool = False
    backup: bool = True
    backup_dir: Path | None = None

    changes: list[Change] = field(default_factory=list)
    backup_path: Path | None = None
    _db: SaveDatabase | None = None
    _temp_path: Path | None = None

    def __init__(
        self,
        path: str | Path,
        *,
        dry_run: bool = False,
        backup: bool = True,
        backup_dir: str | Path | None = None,
    ) -> None:
        self.path = Path(path)
        self.dry_run = dry_run
        self.backup = backup
        self.backup_dir = Path(backup_dir) if backup_dir else None
        self.changes = []
        self.backup_path = None
        self._db = None
        self._temp_path = None

    # -- lifecycle ---------------------------------------------------------
    @property
    def db(self) -> SaveDatabase:
        if self._db is None:
            raise RuntimeError("session is not open - use a with block")
        return self._db

    def open(self) -> SaveSession:
        if self.dry_run:
            # Work on a throwaway copy. Statements have to really execute for the
            # reported row counts to mean anything, and executing means writing -
            # so write somewhere disposable and never open the real save at all.
            handle, temp = tempfile.mkstemp(prefix="f1m-dryrun-", suffix=self.path.suffix)
            os.close(handle)
            self._temp_path = Path(temp)
            shutil.copy2(self.path, self._temp_path)
            self._db = SaveDatabase(self._temp_path).connect()
        else:
            self._db = SaveDatabase(self.path).connect()
        try:
            self._validate()
        except Exception:
            self.close()
            raise
        if not self.dry_run and self.backup:
            self.backup_path = self._take_backup()
        return self

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None
        if self._temp_path is not None:
            self._temp_path.unlink(missing_ok=True)
            self._temp_path = None

    def __enter__(self) -> SaveSession:
        return self.open()

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._db is not None and not self.dry_run:
            if exc_type is None:
                self._db.commit()
            else:
                # Leave the save as it was and point at the backup in the message
                # the caller will see alongside their exception.
                self._db.rollback()
        self.close()

    # -- guards ------------------------------------------------------------
    def _validate(self) -> None:
        missing = [t for t in SENTINEL_TABLES if not self.db.has_table(t)]
        if missing:
            raise NotASaveError(
                f"{self.path} does not look like an F1 Manager save "
                f"(missing: {', '.join(missing)})"
            )

    def _take_backup(self) -> Path:
        target_dir = self.backup_dir or self.path.parent / "backups"
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime(BACKUP_SUFFIX)
        target = target_dir / f"{self.path.stem}_{stamp}{self.path.suffix}"
        # copy2 keeps mtime, which makes it obvious which save a backup came from.
        shutil.copy2(self.path, target)
        return target

    # -- the only way to change anything -----------------------------------
    def run(self, label: str, sql: str, params: Sequence[Any] = ()) -> Change:
        """Execute one statement, recording what it touched.

        In dry-run the statement really is executed, against the temporary copy
        made when the session opened, so `rows_affected` is measured rather than
        guessed. The copy is deleted on close and the real save is never opened
        for writing.
        """
        rows = self.db.execute(sql, params)
        change = Change(label, sql, tuple(params), rows, applied=not self.dry_run)
        self.changes.append(change)
        return change

    def require_columns(self, table: str, *columns: str) -> None:
        """Fail before writing if the schema is not what an operation expects.

        Game updates rename and move columns between versions. Checking up front
        turns "silently did nothing" or "half-applied" into a clear error.
        """
        if not self.db.has_table(table):
            raise NotASaveError(f"table {table!r} is not in this save")
        present = set(self.db.columns(table))
        missing = [c for c in columns if c not in present]
        if missing:
            raise NotASaveError(
                f"table {table!r} is missing expected column(s): {', '.join(missing)}. "
                "This save may be from a different game version."
            )

    # -- reporting ---------------------------------------------------------
    def summary(self) -> str:
        if not self.changes:
            return "no changes"
        mode = "DRY RUN - nothing was written" if self.dry_run else "applied"
        lines = [f"{mode}:"]
        lines += [f"  {c}" for c in self.changes]
        total = sum(c.rows_affected for c in self.changes)
        lines.append(f"  total rows: {total}")
        if self.backup_path:
            lines.append(f"  backup: {self.backup_path}")
        return "\n".join(lines)
