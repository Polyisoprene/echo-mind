"""In-process typed asynchronous EventBus with fault isolation."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TypeVar

from echomind.domain.models import FrozenValueObject

TEvent = TypeVar("TEvent", bound=FrozenValueObject)
EventHandler = Callable[[TEvent], Awaitable[None]]


class AsyncEventBus:
    """Typed pub/sub bus isolating subscriber exceptions so one failure never halts others."""

    def __init__(self) -> None:
        self._subscribers: dict[type[FrozenValueObject], list[Callable[..., Awaitable[None]]]] = (
            defaultdict(list)
        )
        self._error_log: list[str] = []

    @property
    def recent_errors(self) -> tuple[str, ...]:
        """Return captured handler errors for observability."""
        return tuple(self._error_log[-50:])

    def subscribe(self, event_type: type[TEvent], handler: EventHandler[TEvent]) -> None:
        """Register an async handler for a specific FrozenValueObject event type."""
        self._subscribers[event_type].append(handler)

    async def _invoke_safe(
        self, handler: Callable[[FrozenValueObject], Awaitable[None]], event: FrozenValueObject
    ) -> None:
        try:
            await handler(event)
        except Exception as exc:
            self._error_log.append(f"{type(event).__name__}:{exc}")

    async def publish(self, event: FrozenValueObject) -> int:
        """Publish an event to all registered subscribers and return handler count."""
        handlers = list(self._subscribers.get(type(event), ()))
        if not handlers:
            return 0
        for handler in handlers:
            await self._invoke_safe(handler, event)
        return len(handlers)
