"""Value objects describing an external LLM/media gateway endpoint.

Lives in `domain/` because several ports (`ILlmGateway`, `IReloadableVision`)
declare it in their signatures, and the domain layer must not depend on
`core/` where the console-side config loader lives.
"""

from __future__ import annotations

from echomind.domain.base import FrozenValueObject


class GatewayEndpointConfig(FrozenValueObject):
    """LLM gateway endpoint configuration."""

    name: str
    base_url: str
    api_key: str = ""
    model: str
    timeout_ms: int = 120000


__all__ = ["GatewayEndpointConfig"]
