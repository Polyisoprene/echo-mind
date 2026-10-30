"""Read, validate and hot-apply Multi-Provider & Fallback Chain LLM configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from echomind.core.bootstrap import EchoMindContainer
from echomind.core.config import load_config_from_json
from echomind.web.reconcile_service import run_persona_reconciliation

API_DEFAULTS: dict[str, Any] = {
    "baseUrl": "http://127.0.0.1:9000/v1",
    "apiKey": "",
    "model": "deepseek-chat",
    "temperature": 0.8,
    "timeoutMs": 90000,
    "fallbackBaseUrl": "http://127.0.0.1:9914/v1",
    "fallbackApiKey": "",
    "fallbackModel": "deepseek-chat",
    "fallbackTimeoutMs": 90000,
}


def _mask(secret: str) -> str:
    """Show only the head and tail of an API key."""
    if not secret:
        return ""
    if len(secret) <= 10:
        return "***"
    return secret[:6] + "…" + secret[-4:]


def _load_raw(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _section(raw: dict[str, Any]) -> dict[str, Any]:
    api = raw.get("api")
    return api if isinstance(api, dict) else {}


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _str_val(data: dict[str, Any], key1: str, key2: str = "", default: str = "") -> str:
    v1 = str(data.get(key1, "")).strip()
    if v1:
        return v1
    v2 = str(data.get(key2, "")).strip() if key2 else ""
    return v2 if v2 else default


def _clean_models(raw_models: Any) -> list[str]:
    if not isinstance(raw_models, list):
        return []
    return [str(m).strip() for m in raw_models if str(m).strip()]


def _serialize_one_provider(p: Any, k_map: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(p, dict):
        return None
    pid = _str_val(p, "id")
    if not pid:
        return None
    raw_key = _str_val(p, "apiKey", default=str(k_map.get(pid, "")))
    return {
        "id": pid,
        "display_name": _str_val(p, "displayName", default=pid),
        "base_url": _str_val(p, "baseURL"),
        "api_key_masked": _mask(raw_key),
        "models": _clean_models(p.get("models")),
    }


def _serialize_providers(raw: dict[str, Any]) -> list[dict[str, Any]]:
    provs = raw.get("providers")
    dsh_keys = raw.get("dshProviderKeys")
    k_map = dsh_keys if isinstance(dsh_keys, dict) else {}
    if not isinstance(provs, list):
        return []
    items = [_serialize_one_provider(p, k_map) for p in provs]
    return [x for x in items if x is not None]


def _resolve_provider_key(in_key: str, prev_key: str) -> str:
    if not in_key or "…" in in_key or "***" in in_key:
        return prev_key
    return in_key


def _merge_single_provider(
    item: dict[str, Any], old_by_id: dict[str, dict[str, Any]], dsh_keys: dict[str, Any]
) -> dict[str, Any] | None:
    pid = _str_val(item, "id")
    if not pid:
        return None
    prev = old_by_id.get(pid, {})
    prev_key = _str_val(prev, "apiKey", default=str(dsh_keys.get(pid, "")))
    in_key = _str_val(item, "api_key", "apiKey")
    raw_m = item.get("models", prev.get("models", []))
    return {
        **prev,
        "id": pid,
        "displayName": _str_val(item, "display_name", "displayName", pid),
        "api": _str_val(prev, "api", default="openai"),
        "baseURL": _str_val(item, "base_url", "baseURL"),
        "apiKey": _resolve_provider_key(in_key, prev_key),
        "models": _clean_models(raw_m),
    }


def _merge_providers_patch(
    old_provs: list[Any], new_provs: list[dict[str, Any]], dsh_keys: dict[str, Any]
) -> list[dict[str, Any]]:
    old_by_id = {str(p.get("id")): p for p in old_provs if isinstance(p, dict) and p.get("id")}
    merged = [_merge_single_provider(it, old_by_id, dsh_keys) for it in new_provs]
    return [m for m in merged if m is not None]


def _apply_provider_endpoint(
    p_map: dict[str, dict[str, Any]], pid: str, api: dict[str, Any], url_key: str, key_key: str
) -> None:
    p_obj = p_map.get(pid)
    if not p_obj:
        return
    if p_obj.get("baseURL"):
        api[url_key] = p_obj["baseURL"]
    if p_obj.get("apiKey"):
        api[key_key] = p_obj["apiKey"]


def _sync_primary_and_first_fb(raw: dict[str, Any], api: dict[str, Any]) -> None:
    provs = raw.get("providers")
    p_list = provs if isinstance(provs, list) else []
    p_map = {str(p.get("id")): p for p in p_list if isinstance(p, dict)}
    _apply_provider_endpoint(p_map, str(api.get("provider") or ""), api, "baseUrl", "apiKey")
    fbs = api.get("fallbackModels")
    if isinstance(fbs, list) and fbs and isinstance(fbs[0], dict):
        fb0 = fbs[0]
        api["fallbackModel"] = str(fb0.get("model") or api.get("fallbackModel", ""))
        _apply_provider_endpoint(
            p_map, str(fb0.get("provider") or ""), api, "fallbackBaseUrl", "fallbackApiKey"
        )


def _clean_fallback_list(raw_fbs: Any) -> list[dict[str, str]]:
    if not isinstance(raw_fbs, list):
        return []
    out: list[dict[str, str]] = []
    for x in raw_fbs:
        if isinstance(x, dict) and _str_val(x, "model"):
            out.append({"provider": _str_val(x, "provider"), "model": _str_val(x, "model")})
    return out


class LlmConfigService:
    """Backing service for the 模型 tab: inspect and rewrite the LLM gateway config."""

    def __init__(self, container: EchoMindContainer, config_path: Path) -> None:
        self._c = container
        self._path = config_path

    def _current(self) -> dict[str, Any]:
        api = _section(_load_raw(self._path))
        merged = dict(API_DEFAULTS)
        merged.update({k: api[k] for k in API_DEFAULTS if k in api})
        return merged

    def read(self) -> dict[str, Any]:
        """Return the active configuration, providers registry, and ordered fallback chain."""
        raw = _load_raw(self._path)
        api = _section(raw)
        cfg = self._current()
        fb_raw = api.get("fallbackModels")
        fb_list = [
            {"provider": str(x.get("provider", "")), "model": str(x.get("model", ""))}
            for x in (fb_raw if isinstance(fb_raw, list) else [])
            if isinstance(x, dict) and x.get("model")
        ]
        return {
            "ok": True,
            "config_path": str(self._path),
            "active_provider": str(api.get("provider", "")),
            "primary": {
                "provider": str(api.get("provider", "")),
                "base_url": str(cfg["baseUrl"]),
                "model": str(cfg["model"]),
                "api_key_masked": _mask(str(cfg["apiKey"])),
                "timeout_ms": int(_num(cfg["timeoutMs"], 90000)),
            },
            "fallback": {
                "base_url": str(cfg["fallbackBaseUrl"]),
                "model": str(cfg["fallbackModel"]),
                "api_key_masked": _mask(str(cfg["fallbackApiKey"])),
                "timeout_ms": int(_num(cfg["fallbackTimeoutMs"], 90000)),
            },
            "providers": _serialize_providers(raw),
            "fallback_models": fb_list,
            "temperature": _num(cfg["temperature"], 0.8),
        }

    def _write(self, patch: dict[str, Any]) -> None:
        raw = _load_raw(self._path)
        api = dict(_section(raw))
        if isinstance(patch.get("providers"), list):
            old_p = raw.get("providers")
            dsh_k = raw.get("dshProviderKeys")
            raw["providers"] = _merge_providers_patch(
                old_p if isinstance(old_p, list) else [],
                patch["providers"],
                dsh_k if isinstance(dsh_k, dict) else {},
            )
        if patch.get("fallbackModels") is not None:
            api["fallbackModels"] = _clean_fallback_list(patch["fallbackModels"])
        for key, value in patch.items():
            if key not in ("providers", "fallbackModels") and value is not None and value != "":
                api[key] = value
        _sync_primary_and_first_fb(raw, api)
        raw["api"] = api
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    async def apply(self, patch: dict[str, Any]) -> dict[str, Any]:
        """Persist the patch and hot-swap the running gateway and full fallback chain."""
        self._write(patch)
        loaded = load_config_from_json(self._path)
        gateway = self._c.llm_gateway
        if gateway is not None:
            await gateway.reload_endpoints(
                loaded.primary_llm, loaded.fallback_llm, extra_fallbacks=loaded.fallback_chain
            )
        vision = getattr(self._c, "vision_describer", None)
        if vision is not None and hasattr(vision, "reload_endpoint"):
            vision.reload_endpoint(loaded.primary_llm)
        result = self.read()
        result["applied"] = gateway is not None
        result["temperature"] = loaded.temperature
        return result

    def read_persona(self) -> dict[str, Any]:
        """Return the base persona (botName + roleText) from config.json or live composer."""
        raw = _load_raw(self._path)
        raw_p = raw.get("persona")
        p = raw_p if isinstance(raw_p, dict) else {}
        bot_name = str(p.get("botName", "回音"))
        role_text = str(p.get("roleText", ""))
        if self._c.prompt_composer is not None:
            live_name, live_role = self._c.prompt_composer.role_card()
            bot_name = live_name or bot_name
            role_text = live_role or role_text
        return {"ok": True, "bot_name": bot_name, "role_text": role_text}

    def apply_persona(self, bot_name: str, role_text: str) -> dict[str, Any]:
        """Persist base persona to config.json and hot-update PromptComposer in memory."""
        raw = _load_raw(self._path)
        raw_p = raw.get("persona")
        persona = dict(raw_p) if isinstance(raw_p, dict) else {}
        if bot_name.strip():
            persona["botName"] = bot_name.strip()
        persona["roleText"] = role_text.strip()
        raw["persona"] = persona
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if self._c.prompt_composer is not None:
            self._c.prompt_composer.update_role_card(bot_name, role_text)
        section = _load_raw(self._path).get("store")
        ids = section.get("keywords") if isinstance(section, dict) else None
        kept = [str(k).strip() for k in ids] if isinstance(ids, list) else []
        aliases = tuple(dict.fromkeys([bot_name.strip(), *kept]))
        for sensor in self._c.registry.sensors:
            set_fn = getattr(sensor, "set_bot_names", None)
            if callable(set_fn) and bot_name.strip():
                set_fn(aliases)
        res = self.read_persona()
        res["applied"] = self._c.prompt_composer is not None
        return res

    async def reconcile_persona_memory(self, chat_key: str = "") -> dict[str, Any]:
        """Audit and prune memories that conflict with the current base persona via LLM."""
        info = self.read_persona()
        return await run_persona_reconciliation(
            self._c, str(info.get("bot_name", "回音")), str(info.get("role_text", "")), chat_key
        )
