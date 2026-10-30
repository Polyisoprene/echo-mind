"""Stage 29 A3b-1: bans are issued by operators, not by the old owner identity."""

from __future__ import annotations

from echomind.domain.models import Percept
from echomind.mind.ban_control import extract_new_bans

OP = "10001001"
OTHER_OP = "2005"


def _p(uid: str) -> Percept:
    return Percept(chat_key="g", scene="group", message_id=uid, timestamp_ms=1,
                   sender_id=uid, sender_name=uid, text="以后说话不许带诶")


def test_only_operators_issue_bans() -> None:
    assert extract_new_bans((_p("3003"),), (OP,)) == ()
    assert extract_new_bans((_p(OP),), (OP,)) == ("诶",)


def test_any_configured_operator_can_issue_bans() -> None:
    assert extract_new_bans((_p(OTHER_OP),), (OP, OTHER_OP)) == ("诶",)


def test_no_operator_configured_means_no_bans() -> None:
    assert extract_new_bans((_p(OP),), ()) == ()
