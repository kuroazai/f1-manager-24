# AGENTS.md

Guidance for AI coding agents working in this repository. Humans will find it
useful too — it is the architecture doc.

## What this package is

A CLI and library for editing an F1 Manager save database safely. The save is
SQLite, 322 tables, and there is no undo.

**The scope is edits that already work in the game.** This reads what a save
contains and changes values within it. It does not invent content, patch the
executable, or touch anything outside the save file.

## The one invariant

> **Nothing writes to a save except through `SaveSession`.**

`SaveSession` is what guarantees the backup, the dry-run, the schema check and the
single-transaction rollback. A module that opens `SaveDatabase` directly in write
mode has bypassed every one of those, and no amount of care at the call site
replaces them.

If you need to read, `SaveDatabase(path, read_only=True)` is fine and correct.

## Layout

```
src/f1manager/
├── db.py              SQLite wrapper. Explicit commits, genuine read-only,
│                      validated identifiers. No policy.
├── save.py            SaveSession: backups, dry-run, schema guards, Change log.
│                      All the safety policy lives here.
├── staff.py           Decoding the game's mangled names and matching them.
├── enums.py           Reverse-engineered game enums. Hard-won; treat as data.
├── operations/
│   ├── base.py        Operation, the @operation decorator, REGISTRY
│   ├── finance.py     balance, clear-spend
│   ├── difficulty.py  ai
│   ├── parts.py       max-stats, dev-speed
│   ├── facilities.py  max
│   └── drivers.py     set-stats, load-file
└── cli.py             Entry point. Flags are generated from the registry.
```

## Rules that matter

### Every operation declares the schema it touches.

```python
@operation(
    "finance.balance",
    "Set a team's cash balance",
    requires={"Finance_TeamBalance": ("TeamID", "Balance")},
)
def set_balance(session, *, team_id: int = 1, amount: int = 1_000_000_000) -> None:
    session.run(
        f"balance for team {team_id} -> {amount:,}",
        "UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?;",
        (amount, team_id),
    )
```

`requires` is checked before the function body runs. **An operation with an empty
`requires` is a bug** — there is a test asserting none exists. Without it, a game
patch that renames a column turns into either a half-applied batch or a silent
no-op that reports success.

### Scope your UPDATEs.

The defect this package was built around: `UPDATE Finance_TeamBalance SET Balance = ?`
with no WHERE changed all eleven teams, handing every AI rival the same cheat.
Before you write an UPDATE, ask how many rows the table holds. If the answer is
"one per team", you need a WHERE.

`session.run()` returns a `Change` carrying `rows_affected`. Use it — in dry-run
that number is what the user sees, and a surprising count is the signal that the
statement is wrong.

### Adding an operation needs no CLI changes.

The registry drives both `f1manager list` and the argument parser. Keyword-only
parameters become `--kebab-case` flags automatically, with types inferred from
their defaults. Just write the function, decorate it, and import the module in
`operations/__init__.py`.

### Respect the game's own limits.

`Staff_PerformanceStats` carries a per-stat `Max`. Writing above it produces a
value the game's interface cannot display. `drivers.set-stats` clamps by default
and makes opting out explicit. Look for this pattern elsewhere before writing a
raw value — the save often tells you its own bounds.

### Never guess at column semantics.

Verify against a real save before writing an operation. During this package's
build, a column was assumed missing because a listing had been truncated to eight
entries — the column was at index 8. Check unbounded, then write.

If you cannot determine what a column means, say so and stop. A tool that
confidently corrupts saves is worse than one that admits a gap.

### Identifiers are validated, never interpolated blindly.

PRAGMA cannot take bound parameters, so table names reach SQL by interpolation.
`db._check_identifier()` is the guard. Use it for any new path that interpolates
a name; parameterise everything else.

## Testing

```bash
pytest                                  # 100 tests, no save file needed
pytest tests/test_save_session.py       # the safety guarantees
```

**Every test builds its own SQLite fixture** in `tests/conftest.py`. No test reads
or writes a real save, and CI has no game data available. The fixture mirrors the
real schema — including `Finance_TeamBalance` holding eleven teams, the
`PartStat` column using values 0–15, and names stored as
`[StaffName_Forename_Male_Max]`.

**Keep the fixture honest.** It was briefly wrong: it had a `StatType` column
where the real schema has `StatID`, plus no `Max` column at all. Tests written
against that would have passed while the real thing failed. When you add a table,
verify its columns against a live save first.

Tests that assert "nothing was written" must read the file **directly** via
`sqlite3`, not through this package — see `balance_of()` and `read_one()` in
`conftest.py`. An abstraction cannot be the witness to its own correctness.

## Things not to do

- Don't open a save writable outside `SaveSession`.
- Don't write an operation without `requires`.
- Don't write an UPDATE without checking whether it needs a WHERE.
- Don't commit a save, a backup, or anything from `data/` that came out of the
  game. `.gitignore` excludes `*.db` and `backups/`; keep it that way.
- Don't add a runtime dependency. It is stdlib-only and that is worth keeping.
- Don't make dry-run the opt-in. It is the default on purpose.

## Using this as a library

```python
from f1manager import SaveSession
from f1manager.operations import get

# See what would change
with SaveSession("main.db", dry_run=True) as session:
    get("parts.max-stats")(session)
    print(session.summary())

# Do it
with SaveSession("main.db") as session:
    get("finance.balance")(session, team_id=1, amount=10**9)
    print(f"backup at {session.backup_path}")
```

Read-only inspection skips the session entirely:

```python
from f1manager.db import SaveDatabase

with SaveDatabase("main.db", read_only=True) as db:
    print(len(db.tables()))
    print(db.query("SELECT TeamID, Balance FROM Finance_TeamBalance;"))
```
