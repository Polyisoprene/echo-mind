"""Stage 29 A5: hot-apply console identity edits onto the live OneBot runtime."""

from __future__ import annotations

from typing import Any


def apply_identity(
    runtime: Any, *, bot_name: str = "", groups: tuple[str, ...] = (),
    private: tuple[str, ...] = (), self_id: str = "",
) -> None:
    """Update allowlists, self id and wake names without restarting the WS loop."""
    if groups:
        runtime._groups = frozenset(groups)
    if private is not None:
        runtime._priv_users = frozenset(private)
    if self_id:
        runtime._self_id = self_id
    if bot_name:
        runtime._bot_names = tuple(dict.fromkeys([bot_name, *runtime._bot_names]))
