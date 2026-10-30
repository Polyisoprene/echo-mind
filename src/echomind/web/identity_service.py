"""Stage 29 A5: console-editable identity & access configuration with hot reload."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from echomind.adapters.onebot.identity_hot_apply import apply_identity
from echomind.mind.naming import BotNaming, bot_naming, set_bot_naming
from echomind.mind.probe_runtime import set_probe_model


@dataclass(frozen=True)
class IdentityDraft:
    """Submitted identity fields (empty means "leave unchanged")."""

    bot_name: str
    keywords: list[str]
    groups: list[str]
    private: list[str]
    self_qq: str
    default_group: str
    operators: list[str]
    probe_model: str

_IDENTITY_KEYS = ("botName", "keywords", "selfQq", "groups", "private", "defaultGroup")


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _operators(raw: dict[str, Any]) -> list[str]:
    """Operator ids: new `operatorIds`, falling back to the legacy affinity key."""
    explicit = _as_list(raw.get("operatorIds"))
    if explicit:
        return explicit
    legacy = _dict_of(_dict_of(raw, "skills"), "affinity").get("ownerQq")
    return _as_list(legacy)


def _self_qq(raw: dict[str, Any]) -> str:
    legacy = _dict_of(_dict_of(raw, "skills"), "affinity").get("botQq")
    return str(raw.get("selfQq") or legacy or "")


def _dict_of(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    return value if isinstance(value, dict) else {}


def _write_section(raw: dict[str, Any], key: str, value: Any) -> None:
    section = raw.get(key)
    if not isinstance(section, dict):
        section = {}
        raw[key] = section
    section.update(value)


class IdentityConfigService:
    """Read/write the identity block of `data/config.json` and apply it live."""

    def __init__(self, path: Path, container: Any = None) -> None:
        self._path = path
        self._c = container

    def _raw(self) -> dict[str, Any]:
        try:
            loaded: Any = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def read(self) -> dict[str, Any]:
        raw = self._raw()
        persona = _dict_of(raw, "persona")
        store = _dict_of(raw, "store")
        allow = _dict_of(raw, "allow")
        naming = bot_naming()
        return {
            "ok": True,
            "bot_name": str(persona.get("botName") or naming.label()),
            "keywords": _as_list(store.get("keywords")) or list(naming.aliases),
            "self_qq": _self_qq(raw),
            "groups": _as_list(allow.get("groups")),
            "private": _as_list(allow.get("private")),
            "default_group": str(raw.get("defaultGroup") or ""),
            "operators": _operators(raw),
            "probe_model": str(raw.get("probeModel") or ""),
        }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        raw = self._raw()
        bot_name = str(payload.get("bot_name") or "").strip()
        keywords = _as_list(payload.get("keywords"))
        groups = _as_list(payload.get("groups"))
        private = _as_list(payload.get("private"))
        self_qq = str(payload.get("self_qq") or "").strip()
        default_group = str(payload.get("default_group") or "").strip()
        operators = _as_list(payload.get("operators"))
        probe_model = str(payload.get("probe_model") or "").strip()
        if "operators" in payload and not operators:
            raise ValueError("operators must not be empty")

        self._merge(
            raw,
            IdentityDraft(
                bot_name, keywords, groups, private, self_qq, default_group, operators, probe_model
            ),
        )
        text = json.dumps(raw, ensure_ascii=False, indent=2) + "\n"
        self._path.write_text(text, encoding="utf-8")
        self._apply_naming(bot_name, keywords)
        set_probe_model(probe_model)
        self._apply_runtime(bot_name, groups, private, self_qq, operators)
        return self.read()

    @staticmethod
    def _merge(raw: dict[str, Any], draft: IdentityDraft) -> None:
        """Merge only the fields the operator actually submitted."""
        _write_section(raw, "persona", {"botName": draft.bot_name} if draft.bot_name else {})
        _write_section(raw, "store", {"keywords": draft.keywords} if draft.keywords else {})
        _write_section(raw, "allow", {"groups": draft.groups} if draft.groups else {})
        if draft.private:
            _write_section(raw, "allow", {"private": draft.private})
        if draft.probe_model is not None:
            raw["probeModel"] = draft.probe_model
        if draft.operators:
            raw["operatorIds"] = list(draft.operators)
            _dict_of(raw, "skills").setdefault("affinity", {}).pop("ownerQq", None)
        for key, value in (
            ("defaultGroup", draft.default_group), ("selfQq", draft.self_qq),
        ):
            if value:
                raw[key] = value

    @staticmethod
    def _apply_naming(bot_name: str, keywords: list[str]) -> None:
        if not (bot_name or keywords):
            return
        naming = bot_naming()
        set_bot_naming(
            BotNaming(name=bot_name or naming.label(), aliases=tuple(keywords) or naming.aliases)
        )

    def _apply_runtime(
        self, bot_name: str, groups: list[str], private: list[str], self_qq: str,
        operators: list[str],
    ) -> None:
        """Push the new filters into the live runtime and prompt composer, when present."""
        composer = getattr(self._c, "prompt_composer", None) if self._c is not None else None
        if composer is not None and bot_name:
            composer.update_role_card(bot_name, composer.role_card()[1])
        runtime = getattr(self._c, "onebot_runtime", None) if self._c is not None else None
        if runtime is not None:
            apply_identity(
                runtime, bot_name=bot_name, groups=tuple(groups),
                private=tuple(private), self_id=self_qq, operators=tuple(operators),
            )
        facade = getattr(self._c, "cognitive_facade", None) if self._c is not None else None
        if facade is not None and operators:
            facade._operator_ids = tuple(operators)
