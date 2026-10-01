"""Money."""
from __future__ import annotations

from ..save import SaveSession
from .base import operation

DEFAULT_TEAM_ID = 1


@operation(
    "finance.balance",
    "Set a team's cash balance",
    requires={"Finance_TeamBalance": ("TeamID", "Balance")},
)
def set_balance(
    session: SaveSession,
    *,
    team_id: int = DEFAULT_TEAM_ID,
    amount: int = 1_000_000_000,
) -> None:
    """Set one team's balance.

    The original script ran this without a WHERE clause, so all eleven teams -
    every AI rival included - received the money. Targeting a single TeamID is
    the fix, and `--team-id` makes it explicit who benefits.
    """
    session.run(
        f"balance for team {team_id} -> {amount:,}",
        "UPDATE Finance_TeamBalance SET Balance = ? WHERE TeamID = ?;",
        (amount, team_id),
    )


@operation(
    "finance.clear-spend",
    "Reset a team's used budget back to zero",
    requires={"Finance_TeamBudget_SpendingBuckets": ("TeamID", "UsedAmount")},
)
def clear_spending(
    session: SaveSession,
    *,
    team_id: int = DEFAULT_TEAM_ID,
    used_amount: int = 0,
) -> None:
    """Zero the cost-cap spend for one team.

    Also previously unscoped, which reset the cap usage for the whole grid.
    """
    session.run(
        f"used budget for team {team_id} -> {used_amount:,}",
        "UPDATE Finance_TeamBudget_SpendingBuckets SET UsedAmount = ? WHERE TeamID = ?;",
        (used_amount, team_id),
    )
