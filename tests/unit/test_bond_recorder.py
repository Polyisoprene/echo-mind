"""Stage 29 A2c: turn outcomes become per-member impact/betrayal observations."""

from __future__ import annotations

from echomind.domain.models import Percept, TurnOutcome
from echomind.domain.ports import IBondDepthStore
from echomind.mind.bond_recorder import record_turn_events


class _FakeStore(IBondDepthStore):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float, bool]] = []

    async def add_impact(
        self, chat_key: str, user_id: str, magnitude: float, *, betray: bool = False
    ) -> None:
        self.calls.append((chat_key, user_id, magnitude, betray))

    async def upsert_stats(self, stats: object) -> None:
        _ = stats

    async def get_stats(self, chat_key: str, user_id: str) -> None:
        _ = (chat_key, user_id)

    async def top_stats(self, limit: int = 50) -> tuple[()]:
        _ = limit
        return ()

    async def set_bond_depth(self, chat_key: str, user_id: str, depth: float) -> None:
        _ = (chat_key, user_id, depth)


def _outcome(reward: float, *, conflict: bool, senders: tuple[str, ...]) -> TurnOutcome:
    triggers = tuple(
        Percept(chat_key="group:A", scene="group", message_id=f"m{i}", timestamp_ms=1,
                sender_id=uid, sender_name=uid, text="hi")
        for i, uid in enumerate(senders)
    )
    return TurnOutcome(
        session_id="s", chat_key="group:A", triggers=triggers,
        social_reward=reward, epistemic_conflict_detected=conflict,
    )


async def test_records_one_impact_per_distinct_sender() -> None:
    store = _FakeStore()
    await record_turn_events(store, _outcome(-0.6, conflict=False, senders=("u1", "u1", "u2")))
    assert [(c[1], c[2], c[3]) for c in store.calls] == [("u1", 0.6, False), ("u2", 0.6, False)]


async def test_verified_deception_is_flagged_as_betrayal() -> None:
    store = _FakeStore()
    await record_turn_events(store, _outcome(0.4, conflict=True, senders=("u3",)))
    assert store.calls == [("group:A", "u3", 0.4, True)]


async def test_missing_store_is_a_noop() -> None:
    await record_turn_events(None, _outcome(0.4, conflict=False, senders=("u1",)))
