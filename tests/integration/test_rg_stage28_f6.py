"""Stage 28 RGR-F6: bounded chord cache under long sessions."""

from __future__ import annotations

from pathlib import Path

from echomind.core.bootstrap import EchoMindContainer
from echomind.mind.subconscious_probe import SubconsciousChordResult

CK = "group:10002002"
OWNER = "10001001"


async def test_rg_f6_chord_cache_bounded(tmp_path: Path) -> None:
    """F6: the per-facade chord cache must stay bounded under a long session."""
    container = await EchoMindContainer.create(
        db_path=tmp_path / "f6.db", owner_qq=OWNER, default_chat_key=CK
    )
    facade = container.cognitive_facade
    for idx in range(300):
        facade.cache_chord(f"m{idx}", SubconsciousChordResult())
    size = len(facade._chord_cache)
    assert size <= 256, f"chord cache must be bounded, got {size}"
