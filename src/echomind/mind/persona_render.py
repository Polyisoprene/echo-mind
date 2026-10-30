"""Stage 30 S30-6: cheap persona rendering — one-slot cache and a probe digest."""

from __future__ import annotations

_CACHE: dict[str, str] = {}
_HITS = 0
_SUMMARY = ""


def render_lookup(key: str) -> str | None:
    """Return a cached directive for this state, counting hits."""
    global _HITS
    found = _CACHE.get(key)
    if found is not None:
        _HITS += 1
    return found


def render_store(key: str, directive: str) -> str:
    """Remember the newest directive (single slot: personality changes are incremental)."""
    _CACHE.clear()
    _CACHE[key] = directive
    return directive


def cache_hits() -> int:
    """Diagnostics: how many renders were served from cache."""
    return _HITS


def set_summary(text: str) -> None:
    """Publish the one-line digest consumed by the subconscious probe."""
    global _SUMMARY
    _SUMMARY = text


def persona_summary() -> str:
    """Current digest ('' before the first render)."""
    return _SUMMARY
