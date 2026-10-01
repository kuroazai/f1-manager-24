"""AI difficulty."""
from __future__ import annotations

from ..enums import DifficultyLevels
from ..save import SaveSession
from .base import operation


@operation(
    "difficulty.ai",
    "Set AI performance difficulty",
    requires={"Difficulty_RaceSim": ("AIPerformance",)},
)
def set_difficulty(session: SaveSession, *, level: str = "VERYHARD") -> None:
    """Set the race-sim AI difficulty.

    Accepts a level name (case-insensitive) rather than a bare integer, so a typo
    fails here with the valid options listed instead of writing a nonsense value
    the game then has to interpret.
    """
    try:
        value = DifficultyLevels[level.upper()].value
    except KeyError:
        valid = ", ".join(d.name for d in DifficultyLevels)
        raise ValueError(f"unknown difficulty {level!r}. Valid: {valid}") from None

    session.run(
        f"AI difficulty -> {level.upper()} ({value})",
        "UPDATE Difficulty_RaceSim SET AIPerformance = ?;",
        (value,),
    )
