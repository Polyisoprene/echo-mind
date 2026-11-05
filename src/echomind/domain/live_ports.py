"""Ports for live (no-restart) reconfiguration of running components.

The console can change identity, allow-lists and LLM endpoints while the bot is
online. These ports name the minimum surface each live component exposes so the
console layer can talk to them through an interface instead of reaching into
private attributes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from echomind.domain.gateway import GatewayEndpointConfig
from echomind.domain.models import ProactiveProposal


@runtime_checkable
class IProactiveScheduler(Protocol):
    """Execute an autonomous proposal produced by the cognitive core (<=5 methods)."""

    async def execute_proposal(self, proposal: ProactiveProposal, now_ms: int) -> str: ...


@runtime_checkable
class IHotReloadableRuntime(Protocol):
    """Live OneBot runtime whose allow-lists and identity can change without restart."""

    def apply_identity(
        self,
        *,
        bot_name: str = "",
        groups: tuple[str, ...] = (),
        private: tuple[str, ...] | None = None,
        self_id: str = "",
        operators: tuple[str, ...] = (),
    ) -> None: ...


@runtime_checkable
class IReloadableVision(Protocol):
    """Vision describer that can adopt a new LLM endpoint at runtime."""

    async def describe(self, image_urls: tuple[str, ...], prompt: str) -> str: ...

    def reload_endpoint(self, endpoint: GatewayEndpointConfig) -> None: ...
