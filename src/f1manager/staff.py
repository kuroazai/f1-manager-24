"""Finding people in a save.

The game does not store readable names. A driver arrives as
`[StaffName_Forename_Male_Lewis]` / `[StaffName_Surname_Hamilton]`, so every
lookup has to strip the brackets, strip the token prefix, and normalise
whitespace before a human-typed name can match anything.

That is the whole reason this module exists, and why name lookup is not a
one-liner in the operation that needs it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .db import SaveDatabase

#: Token prefixes the game puts in front of the actual name.
NAME_PREFIXES = (
    "StaffName_Forename_Male_",
    "StaffName_Forename_Female_",
    "StaffName_Surname_",
)


@dataclass(frozen=True)
class Staff:
    """One person, with the name cleaned up."""

    staff_id: int
    first: str
    last: str

    @property
    def full(self) -> str:
        return f"{self.first} {self.last}".strip()


def _strip_brackets(value: str) -> str:
    if value.startswith("[") and value.endswith("]"):
        return value[1:-1]
    return value


def _strip_prefix(value: str) -> str:
    for prefix in NAME_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def clean_name_token(raw: str | None) -> str:
    """`[StaffName_Surname_Hamilton]` -> `Hamilton`."""
    value = _strip_brackets(raw or "")
    value = _strip_prefix(value)
    return value.replace("_", " ").strip()


def normalise(value: str | None) -> str:
    """Casefold and collapse whitespace, for comparison only."""
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def load_staff(db: SaveDatabase) -> list[Staff]:
    """Every person in the save, with names decoded."""
    return [
        Staff(
            staff_id=int(row["StaffID"]),
            first=clean_name_token(row["FirstName"]),
            last=clean_name_token(row["LastName"]),
        )
        for row in db.query("SELECT StaffID, FirstName, LastName FROM Staff_BasicData;")
    ]


def find_by_name(db: SaveDatabase, name: str) -> list[Staff]:
    """Match a human-typed name, most confident first.

    Returns a list rather than one result because a surname alone is genuinely
    ambiguous — there have been two Schumachers and two Verstappens. Callers
    decide whether to refuse or pick; this does not guess on their behalf.
    """
    query = normalise(name)
    if not query:
        return []
    people = load_staff(db)

    exact = [p for p in people if normalise(p.full) == query]
    if exact:
        return exact

    surname = [p for p in people if normalise(p.last) == query]
    if surname:
        return surname

    return [p for p in people if query in normalise(p.full)]


def resolve_one(db: SaveDatabase, name: str) -> Staff:
    """Find exactly one person, or raise with the alternatives listed."""
    matches = find_by_name(db, name)
    if not matches:
        raise LookupError(f"no one in this save matches {name!r}")
    if len(matches) > 1:
        names = ", ".join(f"{m.full} (id {m.staff_id})" for m in matches[:8])
        raise LookupError(f"{name!r} is ambiguous - matches: {names}")
    return matches[0]
