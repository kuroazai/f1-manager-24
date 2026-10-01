"""Command line interface.

One safety decision shapes this whole module: **dry-run is the default.** Writing
requires `--apply`. Editing a save is irreversible and the cost of the two modes
is asymmetric - a dry run you meant to apply costs you one more command, while an
apply you meant to dry-run costs you a career file. So the dangerous thing is the
one you have to ask for.

    f1manager list
    f1manager inspect --save main.db
    f1manager apply finance.balance --save main.db --team-id 1
    f1manager apply finance.balance --save main.db --team-id 1 --apply
"""
from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .db import SaveDatabase
from .enums import DifficultyLevels
from .operations import all_operations, get
from .save import NotASaveError, SaveSession

DEFAULT_SAVE = "main.db"


def _flag(param_name: str) -> str:
    """team_id -> --team-id"""
    return "--" + param_name.replace("_", "-")


def _cmd_list(_: argparse.Namespace) -> int:
    print("Available operations (dry-run by default; add --apply to write):\n")
    for op in all_operations():
        print(f"  {op.name}")
        print(f"      {op.summary}")
        if op.parameters:
            params = "  ".join(f"{_flag(p.name)} {p.default!r}" for p in op.parameters)
            print(f"      options: {params}")
        tables = ", ".join(sorted(op.requires))
        print(f"      reads/writes: {tables}")
        print()
    print("Difficulty levels:", ", ".join(d.name for d in DifficultyLevels))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.save)
    try:
        with SaveDatabase(path, read_only=True) as db:
            tables = db.tables()
            print(f"{path}  -  {len(tables)} tables")
            interesting = [
                "Finance_TeamBalance", "Difficulty_RaceSim",
                "Parts_Designs_StatValues", "Buildings_HQ", "Staff_BasicData",
            ]
            print("\n  table                           rows")
            for name in interesting:
                if db.has_table(name):
                    print(f"  {name:<32}{db.row_count(name)}")
            if db.has_table("Finance_TeamBalance"):
                print("\n  team balances")
                for row in db.query(
                    "SELECT TeamID, Balance FROM Finance_TeamBalance ORDER BY TeamID;"
                ):
                    print(f"    team {row['TeamID']:<3} {row['Balance']:>18,}")
            if args.stat_types and db.has_table("Staff_Enum_PerformanceStatTypes"):
                print("\n  performance stat types")
                for row in db.query(
                    "SELECT Value, Name FROM Staff_Enum_PerformanceStatTypes ORDER BY Value;"
                ):
                    print(f"    {row['Value']:>3}  {row['Name']}")
    except FileNotFoundError:
        print(f"no save database at {path}", file=sys.stderr)
        return 1
    return 0


def _coerce(raw: Any, default: Any) -> Any:
    """Convert a CLI string using the default's type as the hint."""
    if raw is None or not isinstance(raw, str):
        return raw
    if isinstance(default, bool):
        return raw.lower() in ("1", "true", "yes", "on")
    if isinstance(default, int):
        # Allow 1_000_000_000 and 1000000000 alike.
        return int(raw.replace("_", "").replace(",", ""))
    if isinstance(default, float):
        return float(raw)
    return raw


def _cmd_apply(args: argparse.Namespace) -> int:
    try:
        op = get(args.operation)
    except KeyError as exc:
        print(str(exc).strip('"'), file=sys.stderr)
        return 1

    params: dict[str, Any] = {}
    for p in op.parameters:
        raw = getattr(args, p.name, None)
        if raw is not None:
            params[p.name] = _coerce(raw, p.default)

    dry_run = not args.apply
    try:
        with SaveSession(
            args.save, dry_run=dry_run, backup=not args.no_backup
        ) as session:
            op(session, **params)
            print(session.summary())
    except NotASaveError as exc:
        print(f"refusing to continue: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"bad option: {exc}", file=sys.stderr)
        return 1

    if dry_run:
        print("\nThis was a dry run. Nothing was written. Re-run with --apply to commit.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="f1manager",
        description="Safe, scriptable edits to an F1 Manager save database.",
        epilog="Dry-run is the default. Add --apply to write.",
    )
    parser.add_argument("--version", action="version", version=f"f1manager {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list available operations")
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("inspect", help="summarise a save database")
    p.add_argument("-s", "--save", default=DEFAULT_SAVE)
    p.add_argument("--stat-types", action="store_true", help="also list performance stat types")
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("apply", help="run one operation")
    p.add_argument("operation", help="operation name - see `f1manager list`")
    p.add_argument("-s", "--save", default=DEFAULT_SAVE)
    p.add_argument("--apply", action="store_true",
                   help="actually write (without this, nothing is changed)")
    p.add_argument("--no-backup", action="store_true",
                   help="skip the automatic backup - not recommended")
    # Every operation's keyword arguments become flags, so the registry is the
    # single source of truth and a new operation needs no CLI changes.
    seen: set[str] = set()
    for op in all_operations():
        for param in op.parameters:
            if param.name in seen:
                continue
            seen.add(param.name)
            default = param.default
            help_text = f"{param.name} (default {default!r})"
            if default is inspect.Parameter.empty:
                help_text = f"{param.name} (required by some operations)"
            p.add_argument(_flag(param.name), dest=param.name, default=None, help=help_text)
    p.set_defaults(func=_cmd_apply)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
