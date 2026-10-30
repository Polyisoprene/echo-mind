"""Stage 29 A4/H3: wake aliases come from configuration, never from literals."""

from __future__ import annotations

from echomind.domain.models import Percept


class _Caller:
    async def call_api(self, api: str, **data: object) -> dict[str, str]:
        _ = (api, data)
        return {"text": "星野早上好"}


async def test_voice_wake_uses_configured_aliases_only() -> None:
    from echomind.adapters.onebot.live_client import transcribe_incoming_voice

    percept = Percept(chat_key="g", scene="group", message_id="1", timestamp_ms=1,
                      sender_id="u", sender_name="u", text="[语音]")
    out = await transcribe_incoming_voice(_Caller(), percept, ("星野", "小星"))
    assert out.is_called_by_name is True

    class _Other(_Caller):
        async def call_api(self, api: str, **data: object) -> dict[str, str]:
            _ = (api, data)
            return {"text": "尾尾早上好"}

    fallback = await transcribe_incoming_voice(_Other(), percept, ("星野", "小星"))
    assert fallback.is_called_by_name is False, "a stale literal alias must not wake her"
