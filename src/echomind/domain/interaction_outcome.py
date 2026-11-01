"""Shadow response-attribution records; never used as trait evidence directly."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from echomind.domain.base import FrozenValueObject


class InteractionOutcome(FrozenValueObject):
    """First later non-self message after one of her messages."""

    self_message_id: int = Field(ge=1)
    response_message_id: int = Field(ge=1)
    chat_key: str
    self_ts: int = Field(ge=0)
    response_ts: int = Field(ge=0)
    delay_ms: int = Field(ge=0)
    attribution: Literal["mention", "temporal"]
    sender_id: str = ""
    sender_name: str = ""
    response_text: str = ""
    created_ms: int = Field(default=0, ge=0)
