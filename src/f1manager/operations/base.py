"""The operation registry.

An operation is one named, self-describing edit. Each declares the tables and
columns it touches, and the registry verifies that declaration against the actual
save before the operation runs.

That check is the point. Game patches rename and move columns, and an UPDATE
against a column that no longer exists either raises halfway through a batch or -
worse, with a renamed table - silently matches nothing and reports success. A
declared schema turns both into a clear error before a single byte is written.

Declaring an operation:

    @operation(
        "finance.balance",
        "Set your team's cash balance",
        requires={"Finance_TeamBalance": ("TeamID", "Balance")},
    )
    def set_balance(session, *, team_id: int = 1, amount: int = 1_000_000_000) -> None:
        session.run(
            f"balance -> {amount:,}",
            "UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?;",
            (amount, team_id),
        )
"""
from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from ..save import SaveSession


@dataclass(frozen=True)
class Parameter:
    """One tunable input, derived from the function signature."""

    name: str
    default: Any
    annotation: Any

    @property
    def type_name(self) -> str:
        ann = self.annotation
        return getattr(ann, "__name__", str(ann)) if ann is not inspect.Parameter.empty else "str"


@dataclass(frozen=True)
class Operation:
    """A named edit, with the schema it depends on declared up front."""

    name: str
    summary: str
    func: Callable[..., None]
    requires: Mapping[str, Sequence[str]] = field(default_factory=dict)

    @property
    def parameters(self) -> list[Parameter]:
        """Keyword-only parameters of the underlying function, minus `session`."""
        out = []
        for p in inspect.signature(self.func).parameters.values():
            if p.name == "session" or p.kind is inspect.Parameter.VAR_KEYWORD:
                continue
            out.append(Parameter(p.name, p.default, p.annotation))
        return out

    def check(self, session: SaveSession) -> None:
        """Verify every declared table and column exists in this save."""
        for table, columns in self.requires.items():
            session.require_columns(table, *columns)

    def __call__(self, session: SaveSession, **params: Any) -> None:
        self.check(session)
        self.func(session, **params)


REGISTRY: dict[str, Operation] = {}


def operation(
    name: str,
    summary: str,
    *,
    requires: Mapping[str, Sequence[str]] | None = None,
) -> Callable[[Callable[..., None]], Operation]:
    """Register an operation under `name`.

    Returns the `Operation`, not the raw function, so the only way to invoke it is
    through the path that runs the schema check.
    """

    def decorate(func: Callable[..., None]) -> Operation:
        if name in REGISTRY:
            raise ValueError(f"operation {name!r} is already registered")
        op = Operation(name=name, summary=summary, func=func, requires=dict(requires or {}))
        REGISTRY[name] = op
        return op

    return decorate


def get(name: str) -> Operation:
    """Look up an operation. An unknown name lists what is available."""
    if name not in REGISTRY:
        known = ", ".join(sorted(REGISTRY)) or "(none registered)"
        raise KeyError(f"unknown operation {name!r}. Available: {known}")
    return REGISTRY[name]


def all_operations() -> list[Operation]:
    return [REGISTRY[k] for k in sorted(REGISTRY)]
