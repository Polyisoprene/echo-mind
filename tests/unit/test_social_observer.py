"""Stage 40: every observed message must build/refresh the sender's bond."""

from __future__ import annotations

from echomind.domain.models import Percept, SocialBondProfile
from echomind.mind.social_observer import observe_contact


class _Repo:
    def __init__(self) -> None:
        self.bonds: dict[tuple[str, str], SocialBondProfile] = {}

    async def get_social_bond(self, chat_key: str, user_id: str) -> SocialBondProfile | None:
        return self.bonds.get((chat_key, user_id))

    async def upsert_social_bond(self, bond: SocialBondProfile) -> None:
        self.bonds[(bond.chat_key, bond.user_id)] = bond


def _percept(ts: int, uid: str = "42", name: str = "群友") -> Percept:
    return Percept(chat_key="group:1", scene="group", message_id=str(ts),
                   timestamp_ms=ts, sender_id=uid, sender_name=name, text="hi")


async def test_first_message_creates_bond() -> None:
    repo = _Repo()
    bond = await observe_contact(repo, repo, _percept(1000))
    assert bond.msg_count == 1 and bond.last_seen_ms == 1000
    assert bond.affinity_score == 30.0


async def test_repeated_messages_increment_count_and_recency() -> None:
    repo = _Repo()
    await observe_contact(repo, repo, _percept(1000))
    bond = await observe_contact(repo, repo, _percept(2000, name="改名"))
    assert bond.msg_count == 2 and bond.last_seen_ms == 2000
    assert bond.user_name == "改名"


async def test_observation_does_not_change_affinity() -> None:
    repo = _Repo()
    first = await observe_contact(repo, repo, _percept(1000))
    second = await observe_contact(repo, repo, _percept(2000))
    assert first.affinity_score == second.affinity_score


async def test_operator_is_marked_admin() -> None:
    repo = _Repo()
    bond = await observe_contact(repo, repo, _percept(1000), operator_ids=("42",))
    assert bond.group_role == "admin"
