"""Prompt Prefix Cache Anchor Engine maximizing DeepSeek prefix cache hit rates."""

from __future__ import annotations

from typing import Literal

from echomind.domain.models import FrozenValueObject


class AnchorDecision(FrozenValueObject):
    """Immutable decision for prompt prefix cache anchoring."""

    mode: Literal["anchored", "reset"]
    anchored_ids: tuple[int, ...]
    extra_ids: tuple[int, ...]
    active_member_ids: tuple[str, ...]


class PrefixAnchorEngine:
    """Maintain per-chat prefix anchors so consecutive turns reuse identical leading tokens."""

    def __init__(self, max_extra_read: int = 16, window_size: int = 80) -> None:
        self._max_extra = max_extra_read
        self._window = window_size
        self._anchors: dict[str, tuple[tuple[int, ...], frozenset[str]]] = {}

    def resolve(
        self,
        chat_key: str,
        all_read_ids: tuple[int, ...],
        current_member_ids: tuple[str, ...],
    ) -> AnchorDecision:
        if not all_read_ids:
            return AnchorDecision(
                mode="reset",
                anchored_ids=(),
                extra_ids=(),
                active_member_ids=current_member_ids,
            )

        sliding = all_read_ids[-self._window :]
        member_set = frozenset(current_member_ids)
        prev = self._anchors.get(chat_key)

        if prev is not None:
            decision = self._try_reuse_anchor(prev[0], prev[1], sliding, all_read_ids, member_set)
            if decision is not None:
                return decision

        # Reset anchor: reserve tail room for future extra appends
        reserve = min(len(sliding) // 4, self._max_extra // 2)
        cut = max(1, len(sliding) - reserve)
        new_anchor = sliding[:cut]
        new_extra = sliding[cut:]
        self._anchors[chat_key] = (new_anchor, member_set)
        return AnchorDecision(
            mode="reset",
            anchored_ids=new_anchor,
            extra_ids=new_extra,
            active_member_ids=tuple(sorted(member_set)),
        )

    def _try_reuse_anchor(
        self,
        anchor_ids: tuple[int, ...],
        anchor_members: frozenset[str],
        sliding: tuple[int, ...],
        all_read_ids: tuple[int, ...],
        current_members: frozenset[str],
    ) -> AnchorDecision | None:
        if not anchor_ids or not current_members.issubset(anchor_members):
            return None
        first_id = anchor_ids[0]
        last_id = anchor_ids[-1]
        if first_id not in sliding or last_id not in all_read_ids:
            return None
        last_idx = all_read_ids.index(last_id)
        extra = all_read_ids[last_idx + 1 :]
        if len(extra) > self._max_extra:
            return None
        return AnchorDecision(
            mode="anchored",
            anchored_ids=anchor_ids,
            extra_ids=extra,
            active_member_ids=tuple(sorted(anchor_members)),
        )
