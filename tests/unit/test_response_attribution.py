"""P0: reply attribution is tiered and never guesses across the window."""

from __future__ import annotations

from echomind.mind.response_attribution import ChatMessageRow, attribute_messages


def _row(mid: int, ts: int, self_: bool, text: str, sender: str = "u") -> ChatMessageRow:
    return ChatMessageRow(
        message_id=mid, chat_key="g", ts=ts, is_self=self_,
        sender_id=sender, sender_name=sender, text=text,
    )


def test_mention_and_temporal_attribution() -> None:
    rows = (
        _row(1, 0, True, "她说话"),
        _row(2, 1_000, False, "回音你怎么看"),
        _row(3, 2_000, True, "她又说话"),
        _row(4, 3_000, False, "随便聊聊"),
    )
    outcomes = attribute_messages(rows, ("回音", "尾尾"))
    assert [(o.self_message_id, o.attribution) for o in outcomes] == [
        (1, "mention"), (3, "temporal"),
    ]


def test_no_reply_outside_window() -> None:
    rows = (
        _row(1, 0, True, "她说话"),
        _row(2, 31 * 60 * 1000, False, "回音"),
    )
    assert attribute_messages(rows, ("回音",)) == ()
