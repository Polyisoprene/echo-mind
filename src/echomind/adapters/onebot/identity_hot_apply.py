"""Stage 29 A5: hot-apply console identity edits onto the live OneBot runtime."""

from __future__ import annotations

from echomind.domain.live_ports import IHotReloadableRuntime


def apply_identity(
    runtime: IHotReloadableRuntime, *, bot_name: str = "", groups: tuple[str, ...] = (),
    private: tuple[str, ...] = (), self_id: str = "",
    operators: tuple[str, ...] = (),
) -> None:
    """Update allow-lists, self id and wake names without restarting the WS loop."""
    runtime.apply_identity(
        bot_name=bot_name, groups=groups, private=private,
        self_id=self_id, operators=operators,
    )


__all__ = ["apply_identity"]
