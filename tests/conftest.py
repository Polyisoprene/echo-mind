"""Shared pytest guards: the suite must never mutate live runtime state."""

from __future__ import annotations

from pathlib import Path

import pytest

LIVE_CONFIG = Path("data/config.json")


@pytest.fixture(scope="session", autouse=True)
def _protect_live_config() -> object:
    """Fail the session if any test rewrites the production config file."""
    before = LIVE_CONFIG.read_bytes() if LIVE_CONFIG.exists() else None
    yield
    if before is None:
        return
    after = LIVE_CONFIG.read_bytes() if LIVE_CONFIG.exists() else None
    assert after == before, (
        "a test modified data/config.json — build the app with config_path=tmp_path instead"
    )
