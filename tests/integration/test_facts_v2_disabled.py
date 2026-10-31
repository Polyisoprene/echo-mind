"""D12: enabling FACTS_V2 fails fast instead of dropping provenance silently."""

from __future__ import annotations

from pathlib import Path

import pytest

from echomind.core.bootstrap import EchoMindContainer


@pytest.mark.asyncio
async def test_facts_v2_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FACTS_V2", "on")
    with pytest.raises(RuntimeError, match="FACTS_V2"):
        await EchoMindContainer.create(db_path=tmp_path / "v2.db")
