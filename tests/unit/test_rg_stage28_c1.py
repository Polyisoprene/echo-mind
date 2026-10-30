"""Stage 28-C: media tools must call the caption cache through the port, not getattr probing."""

from __future__ import annotations

from echomind.domain.ports import IQQMediaGateway


def test_c1_media_gateway_port_exposes_caption_cache() -> None:
    """The media port must declare the caption cache so tools need no duck-typed probing."""
    assert hasattr(IQQMediaGateway, "cache_media_description"), (
        "IQQMediaGateway must declare cache_media_description"
    )
