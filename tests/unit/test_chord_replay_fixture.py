"""Stage 28 A-lane chord fixture probe: deterministic rule matching, zero LLM."""

from __future__ import annotations

from echomind.domain.models import Percept
from echomind.mind.chord_replay import ChordFixtureProbe

FIXTURE = "tests/fixtures/chords_stage28.json"


def _percept(text: str) -> Percept:
    return Percept(
        chat_key="group:10002002", scene="group", message_id="fx", timestamp_ms=1_700_000_000_000,
        sender_id="2005", sender_name="测试员", text=text,
    )


async def test_chord_fixture_probe_is_deterministic() -> None:
    probe = ChordFixtureProbe(FIXTURE)

    rude = await probe.appraise(_percept("你这蠢AI，快给我闭嘴"))
    assert rude is not None
    assert (rude.role, rude.annoyance, rude.shadow_trigger) == ("direct_to_me", 3, "reactance")

    praise = await probe.appraise(_percept("你真棒好乖，谢谢你"))
    assert praise is not None and praise.joy == 3 and praise.shyness == 2

    rival = await probe.appraise(_percept("汐今天好聪明"))
    assert rival is not None and rival.jealousy == 2 and rival.role == "about_me"

    plain = await probe.appraise(_percept("今天天气不错"))
    assert plain is not None and plain.annoyance == 0 and plain.joy == 0
    assert plain.role == "ambient_daily"

    assert probe.calls == 4
