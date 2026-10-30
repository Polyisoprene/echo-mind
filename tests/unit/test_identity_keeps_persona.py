"""Regression: editing identity must never blank the live persona text."""

from __future__ import annotations

import json
from pathlib import Path

from echomind.mind.naming import BotNaming, set_bot_naming
from echomind.runtime.prompt_composer import PromptComposer
from echomind.web.identity_service import IdentityConfigService


class _Container:
    def __init__(self) -> None:
        self.prompt_composer = PromptComposer("原始人设正文", bot_name="回音")
        self.onebot_runtime = None


def test_identity_save_keeps_existing_role_text(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"persona": {"botName": "回音", "roleText": "原始人设正文"}}),
                   encoding="utf-8")
    container = _Container()
    try:
        IdentityConfigService(cfg, container).save({"bot_name": "星野"})
        name, role = container.prompt_composer.role_card()
        assert name == "星野"
        assert role == "原始人设正文", "identity edit must not erase the persona text"
    finally:
        set_bot_naming(BotNaming())
