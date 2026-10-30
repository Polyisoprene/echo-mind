"""Regression: an identity save with empty optional lists must not clear whitelists."""

from __future__ import annotations

import json
from pathlib import Path

from echomind.mind.naming import BotNaming, set_bot_naming
from echomind.web.identity_service import IdentityConfigService


def test_empty_lists_keep_existing_whitelists(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "persona": {"botName": "回音", "roleText": "人设"},
        "allow": {"groups": ["111"], "private": ["222"]},
    }), encoding="utf-8")
    try:
        IdentityConfigService(cfg).save({"bot_name": "回音"})
        raw = json.loads(cfg.read_text(encoding="utf-8"))
        assert raw["allow"]["groups"] == ["111"]
        assert raw["allow"]["private"] == ["222"], (
            "empty payload must not wipe the private whitelist"
        )
        assert raw["persona"]["roleText"] == "人设"
    finally:
        set_bot_naming(BotNaming())
