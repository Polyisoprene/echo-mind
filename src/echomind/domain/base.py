"""Shared immutable value-object base for the domain layer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FrozenValueObject(BaseModel):
    """Base class for all immutable cross-layer value objects."""

    model_config = ConfigDict(frozen=True, extra="forbid")


__all__ = ["FrozenValueObject"]
