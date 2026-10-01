# f1manager save tools

Safe, scriptable edits to an **F1 Manager** save database.

A save is a SQLite file holding 322 tables. You can edit it by hand and many
people do, but there is no undo, and a mistyped UPDATE without a WHERE clause will
quietly change all eleven teams instead of yours. This package wraps the useful
edits in a CLI that backs up first, shows you what it intends to do, and refuses
to run against a save whose schema it does not recognise.

```bash
pip install -e .
f1manager inspect --save main.db
f1manager apply finance.balance --save main.db --team-id 1     # dry run
f1manager apply finance.balance --save main.db --team-id 1 --apply
```

---

## The safety model

This is the part worth reading. Everything else is a convenience.

**Dry-run is the default.** Writing requires `--apply`. The two mistakes are not
symmetrical: a dry run you meant to apply costs you one more command, while an
apply you meant to dry-run can cost you a career file. So the dangerous one is the
one you have to ask for.

**Dry-run cannot touch your save.** It copies the file to a temporary location,
runs the statements there for real, reports the exact row counts, and deletes the
copy. Your save is never opened for writing, so "unchanged" holds by construction
rather than by trusting a rollback to work. The test suite asserts the file is
byte-identical afterwards.

**A backup is taken before the first write.** Automatically, timestamped, into
`backups/` next to your save. Not a suggestion in a README — a copy on disk. You
can disable it with `--no-backup`, which you should not.

**Operations declare the tables and columns they touch**, and that declaration is
checked against your save before anything runs. Game patches rename and move
columns; without this, an UPDATE against a renamed column either raises halfway
through a batch or silently matches nothing and reports success. With it, you get
a clear error before a single byte changes.

**Everything in a session is one transaction.** If an operation fails halfway, the
save is left exactly as it was — no half-applied edits.

## Install

```bash
git clone <this repo>
cd f1-manager-25
pip install -e .
```

Python 3.10+. **No runtime dependencies** — `sqlite3` and `argparse` are standard
library, so this installs anywhere Python does.

For development:

```bash
pip install -e ".[dev]"
pytest          # 100 tests, no save file needed
ruff check src tests
mypy
```

## Finding your save

F1 Manager keeps saves under your user profile. On Windows, look in:

```
%LOCALAPPDATA%\F1Manager25\Saved\SaveGames\
```

Copy the one you want to work on somewhere convenient and point `--save` at the
copy. There is no reason to edit in place while you are still learning what these
operations do.

## Operations

`f1manager list` prints this, including each operation's options and the tables it
touches.

| Operation | What it does |
|---|---|
| `finance.balance` | Set one team's cash balance. `--team-id`, `--amount` |
| `finance.clear-spend` | Reset a team's used cost-cap budget. `--team-id` |
| `difficulty.ai` | Set AI difficulty. `--level VERYEASY…VERYHARD` |
| `parts.max-stats` | Raise every car-part stat to the best value already in the save |
| `parts.dev-speed` | Rewrite part development speed multipliers |
| `facilities.max` | Point every HQ slot at its highest available building, marked open |
| `drivers.set-stats` | Set one person's stats. `--name "Max Verstappen" --stats '{"Speed": 20}'` |
| `drivers.load-file` | Bulk-apply a JSON file of driver stats. `--path` |

### Examples

```bash
# What is in this save?
f1manager inspect --save main.db
f1manager inspect --save main.db --stat-types     # list the 44 stat names

# Give YOUR team money, not the whole grid
f1manager apply finance.balance --save main.db --team-id 1 --amount 1000000000 --apply

# Max out every part stat
f1manager apply parts.max-stats --save main.db --apply

# One driver
f1manager apply drivers.set-stats --save main.db \
    --name "Max Verstappen" --stats '{"Speed": 20, "Consistency": 20}' --apply

# A whole file of them
f1manager apply drivers.load-file --save main.db \
    --path data/drivers/drivers_at_peak_2025.json --apply
```

Driver stats are **clamped to each stat's `Max`** by default, because a value above
the cap is one the game's own interface cannot display. `--respect-max false` opts
out.

Names are resolved from the mangled form the game stores — `[StaffName_Surname_Hamilton]`
becomes `Hamilton`. A surname that matches two people (there have been two
Schumachers) is reported as ambiguous rather than guessed at.

## Bugs this fixes

Repackaging turned up four real defects in the original scripts, which is most of
why it was worth doing:

- **`UPDATE Finance_TeamBalance SET Balance = ?` had no WHERE clause.** The table
  holds eleven teams, so every AI rival got the money too. Verified: all eleven
  sat at exactly 1,000,000,000.
- **The part-stat script iterated the wrong enum.** It looped `PartsEnumType`
  (Engine, ERS, Gearbox — values 0–8) while filtering on the `PartStat` column,
  which holds `PartsEnumStats` values 0–15. Seven stats were never touched,
  including Power, HighSpeedDownforce, OperationalRange and Durability. It also
  logged the wrong names throughout.
- **`execute()` never committed; `close()` did.** An UPDATE persisted only as a
  side effect of closing, so anything raising first discarded it silently — and a
  read-only session committed anyway.
- **`close()` committed before its own `None` check**, so closing twice raised
  `AttributeError`.

## How it is laid out

```
src/f1manager/
├── db.py              SQLite wrapper: explicit commits, real read-only, no
│                      identifier interpolation
├── save.py            SaveSession — backups, dry-run, schema guards. The only
│                      sanctioned way to write
├── staff.py           Decoding and matching the game's mangled names
├── enums.py           Reverse-engineered game enums: 44 performance stats,
│                      building types, part stats, difficulty levels
├── operations/        One module per area; each operation declares its schema
└── cli.py             Entry point; flags are generated from the registry
```

Adding an operation needs no CLI changes — the registry is the single source of
truth and `f1manager list` and the argument parser both read from it. See
[AGENTS.md](AGENTS.md) for the architecture and a worked example.

## Caveats

- Written against **F1 Manager 25** saves. Other versions may differ; the schema
  checks will tell you rather than corrupting anything.
- This edits your save. Keep the backups.
- Not affiliated with or endorsed by the game's developers or publisher. No game
  assets are included or distributed here.

## Licence

MIT. See [LICENSE](LICENSE).
