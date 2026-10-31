"""Domain-level errors shared by storage and mind layers."""

from __future__ import annotations


class WorkingStateConflict(RuntimeError):
    """The working snapshot changed since it was loaded (optimistic lock)."""


__all__ = ["WorkingStateConflict"]
