"""Stage 28 RGR-F8: the vision caption dependency must be a narrow typed port, not Any."""

from __future__ import annotations

from typing import get_type_hints

from echomind.adapters.onebot.enrichers import ImageCaptionCacheEnricher


def test_rg_f8_vision_gateway_is_port_typed() -> None:
    """The injected caption gateway must be annotated with a Protocol, never Any."""
    hints = get_type_hints(ImageCaptionCacheEnricher.__init__)
    assert "ICaptionGateway" in str(hints["vision_gw"]), (
        f"vision_gw must be typed as ICaptionGateway, got {hints['vision_gw']}"
    )


class _CaptionStub:
    async def describe_image(self, ref: str) -> str:
        return f"caption:{ref}"

    async def cache_media_description(self, item: object, caption: str) -> None:
        _ = (item, caption)


def test_rg_f8_caption_port_is_structural() -> None:
    """Any adapter exposing the two caption methods satisfies the port structurally."""
    from echomind.domain.ports import ICaptionGateway

    assert isinstance(_CaptionStub(), ICaptionGateway)
