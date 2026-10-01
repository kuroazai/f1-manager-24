"""Operations: one named, self-describing edit each.

Importing this package registers every operation. `base.REGISTRY` is the single
source of truth the CLI reads, so adding a module here is all it takes for a new
operation to appear in `f1manager list`.
"""
from __future__ import annotations

# Imported for their registration side effect. Keep alphabetical.
from . import (  # noqa: E402,F401  (side-effect imports)
    difficulty,
    drivers,
    facilities,
    finance,
    parts,
)
from .base import REGISTRY, Operation, all_operations, get, operation

__all__ = ["REGISTRY", "Operation", "all_operations", "get", "operation"]
