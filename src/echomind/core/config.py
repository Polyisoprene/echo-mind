"""Strongly-typed immutable configuration loader (pure & generic defaults)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ConfigDict, Field

from echomind.domain.models import FrozenValueObject


class GatewayEndpointConfig(FrozenValueObject):
    """LLM gateway endpoint configuration."""

    name: str
    base_url: str
    api_key: str = ""
    model: str
    timeout_ms: int = 120000


class OneBotConnConfig(FrozenValueObject):
    """NapCat OneBot v11 connection settings."""

    ws_url: str = "ws://127.0.0.1:3001"
    http_url: str = "http://127.0.0.1:3000"
    access_token_value: str = Field(default="", alias="access_token")
    http_token_value: str = Field(default="", alias="http_token")

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class AppConfig(FrozenValueObject):
    """Top-level immutable application configuration (zero personal hardcoded IDs)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bot_name: str = "Echo"
    self_qq: str = ""
    operator_ids: tuple[str, ...] = ()
    role_text: str = ""
    probe_model: str = ""
    server_host: str = "127.0.0.1"
    server_port: int = 3310
    auth_key: str = ""
    allowed_groups: tuple[str, ...] = ()
    allowed_private: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    primary_llm: GatewayEndpointConfig = Field(
        default_factory=lambda: GatewayEndpointConfig(
            name="PrimaryGateway",
            base_url="http://127.0.0.1:9000/v1",
            model="deepseek-chat",
        )
    )
    fallback_llm: GatewayEndpointConfig = Field(
        default_factory=lambda: GatewayEndpointConfig(
            name="FallbackGateway",
            base_url="http://127.0.0.1:9914/v1",
            model="deepseek-chat",
        )
    )
    fallback_chain: tuple[GatewayEndpointConfig, ...] = ()
    temperature: float = 0.8
    onebot: OneBotConnConfig = OneBotConnConfig()
    feiyu_base_url: str = "http://192.168.3.2:9880"
    feiyu_api_key: str = ""
    feiyu_style: str = "cute"


def _sub_dict(raw: dict[str, Any], key: str) -> dict[str, Any]:
    val = raw.get(key)
    return val if isinstance(val, dict) else {}


def _get_str(data: dict[str, Any], key: str, default: str = "") -> str:
    val = str(data.get(key, "")).strip()
    return val if val else default


def _get_float(data: dict[str, Any], key: str, default: float) -> float:
    val = data.get(key)
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _get_int(data: dict[str, Any], key: str, default: int) -> int:
    val = data.get(key)
    return int(val) if val else default


def _extract_str_tuple(raw_list: Any, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if not isinstance(raw_list, list):
        return default
    items = tuple(str(x).strip() for x in raw_list if str(x).strip())
    return items if items else default


def _build_primary_llm(api: dict[str, Any]) -> GatewayEndpointConfig:
    return GatewayEndpointConfig(
        name="PrimaryGateway",
        base_url=_get_str(api, "baseUrl", "http://127.0.0.1:9000/v1"),
        api_key=_get_str(api, "apiKey", ""),
        model=_get_str(api, "model", "deepseek-chat"),
        timeout_ms=_get_int(api, "timeoutMs", 120000),
    )


def _build_fallback_llm(api: dict[str, Any]) -> GatewayEndpointConfig:
    return GatewayEndpointConfig(
        name="FallbackGateway",
        base_url=_get_str(api, "fallbackBaseUrl", "http://127.0.0.1:9914/v1"),
        api_key=_get_str(api, "fallbackApiKey", ""),
        model=_get_str(api, "fallbackModel", "deepseek-chat"),
        timeout_ms=_get_int(api, "fallbackTimeoutMs", 90000),
    )


def _provider_lookup(raw: dict[str, Any]) -> dict[str, dict[str, str]]:
    provs = raw.get("providers")
    dsh_keys = _sub_dict(raw, "dshProviderKeys")
    if not isinstance(provs, list):
        return {}
    out: dict[str, dict[str, str]] = {}
    for item in provs:
        if not isinstance(item, dict):
            continue
        pid = _get_str(item, "id")
        if not pid:
            continue
        key = _get_str(item, "apiKey") or _get_str(dsh_keys, pid)
        out[pid] = {
            "name": _get_str(item, "displayName", pid),
            "base_url": _get_str(item, "baseURL"),
            "api_key": key,
        }
    return out


def _fb_entry_to_endpoint(
    idx: int,
    entry: Any,
    p_map: dict[str, dict[str, str]],
    default_fb: GatewayEndpointConfig,
) -> GatewayEndpointConfig | None:
    if not isinstance(entry, dict):
        return None
    model = _get_str(entry, "model")
    if not model:
        return None
    p_info = p_map.get(_get_str(entry, "provider"), {})
    b_url = _get_str(entry, "baseUrl", p_info.get("base_url", default_fb.base_url))
    a_key = _get_str(entry, "apiKey", p_info.get("api_key", default_fb.api_key))
    return GatewayEndpointConfig(
        name=p_info.get("name", f"Fallback#{idx}"),
        base_url=b_url,
        api_key=a_key,
        model=model,
        timeout_ms=_get_int(entry, "timeoutMs", default_fb.timeout_ms),
    )


def _build_fallback_chain(
    raw: dict[str, Any], api: dict[str, Any], default_fb: GatewayEndpointConfig
) -> tuple[GatewayEndpointConfig, ...]:
    fb_list = api.get("fallbackModels")
    if not isinstance(fb_list, list):
        return (default_fb,)
    p_map = _provider_lookup(raw)
    items = [_fb_entry_to_endpoint(i, e, p_map, default_fb) for i, e in enumerate(fb_list, 1)]
    chain = tuple(x for x in items if x is not None)
    return chain if chain else (default_fb,)


def _build_onebot_cfg(sl: dict[str, Any]) -> OneBotConnConfig:
    ws_tok = _get_str(sl, "accessToken", "")
    return OneBotConnConfig(
        ws_url=_get_str(sl, "wsUrl", "ws://127.0.0.1:3001"),
        http_url=_get_str(sl, "httpUrl", "http://127.0.0.1:3000"),
        access_token=ws_tok,
        http_token=_get_str(sl, "httpAccessToken", ws_tok),
    )


def _resolve_operators(raw: dict[str, Any], legacy_owner: str) -> tuple[str, ...]:
    """Read operatorIds (list or comma string); fall back to the owner for compatibility."""
    value = raw.get("operatorIds")
    if isinstance(value, str):
        value = [v.strip() for v in value.split(",")]
    ids = tuple(str(v).strip() for v in value if str(v).strip()) if isinstance(value, list) else ()
    return ids or ((legacy_owner,) if legacy_owner else ())


def _resolve_identities(raw: dict[str, Any]) -> tuple[str, str]:
    aff = _sub_dict(_sub_dict(raw, "skills"), "affinity")
    self_qq = _get_str(raw, "selfQq") or _get_str(aff, "botQq")
    legacy_owner = _get_str(raw, "ownerQq") or _get_str(aff, "ownerQq")
    return self_qq, legacy_owner


def _resolve_feiyu(raw: dict[str, Any]) -> tuple[str, str, str]:
    top = _sub_dict(raw, "feiyuVoice")
    skill = _sub_dict(_sub_dict(raw, "skills"), "feiyu-voice")
    base_url = _get_str(top, "baseUrl") or _get_str(skill, "baseUrl", "http://192.168.3.2:9880")
    api_key = _get_str(top, "apiKey") or _get_str(skill, "apiKey")
    style = _get_str(top, "defaultStyle") or _get_str(skill, "defaultStyle", "cute")
    return base_url, api_key, style


def load_config_from_json(path: Path) -> AppConfig:
    """Load AppConfig from a JSON configuration file using guard clauses."""
    if not path.is_file():
        return AppConfig()

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    persona = _sub_dict(raw, "persona")
    server = _sub_dict(raw, "server")
    allow = _sub_dict(raw, "allow")
    api_section = _sub_dict(raw, "api")
    store = _sub_dict(raw, "store")
    self_qq, legacy_owner = _resolve_identities(raw)
    f_url, f_key, f_style = _resolve_feiyu(raw)
    fb_one = _build_fallback_llm(api_section)

    return AppConfig(
        bot_name=_get_str(persona, "botName", "Echo"),
        self_qq=self_qq,
        operator_ids=_resolve_operators(raw, legacy_owner),
        role_text=_get_str(persona, "roleText", ""),
        probe_model=_get_str(raw, "probeModel", ""),
        server_host=_get_str(server, "host", "127.0.0.1"),
        server_port=_get_int(server, "port", 3310),
        auth_key=_get_str(server, "token", ""),
        allowed_groups=_extract_str_tuple(allow.get("groups")),
        allowed_private=_extract_str_tuple(allow.get("private")),
        keywords=_extract_str_tuple(store.get("keywords")),
        temperature=_get_float(api_section, "temperature", 0.8),
        primary_llm=_build_primary_llm(api_section),
        fallback_llm=fb_one,
        fallback_chain=_build_fallback_chain(raw, api_section, fb_one),
        onebot=_build_onebot_cfg(_sub_dict(raw, "snowluma")),
        feiyu_base_url=f_url,
        feiyu_api_key=f_key,
        feiyu_style=f_style,
    )
