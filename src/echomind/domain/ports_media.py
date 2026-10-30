"""Media, voice, OneBot & Bilibili ports (split from ports.py to honour SRP-01)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from echomind.domain.models import MediaAttachment


@runtime_checkable
class IMessageSender(Protocol):
    """Segregated actuator port for outbound QQ messaging (<=5 methods)."""

    async def send_text(
        self, chat_key: str, messages: tuple[str, ...], reply_to_mid: str | None = None,
        at_user_id: str | None = None,
    ) -> tuple[str, ...]: ...

    async def send_sticker(
        self, chat_key: str, sticker_id: str, reply_to_mid: str | None = None
    ) -> str | None: ...

    async def send_voice(self, chat_key: str, audio_b64: str, summary_text: str) -> str | None: ...

    async def send_poke(self, chat_key: str, target_user_id: str) -> bool: ...


@runtime_checkable
class IVisionDescriber(Protocol):
    """Port for describing images / video frames through a multimodal model."""

    async def describe(self, image_urls: tuple[str, ...], prompt: str) -> str: ...


@runtime_checkable
class IVoiceBackend(Protocol):
    """Port for the Feiyu GPU voice service (TTS synthesis)."""

    async def synthesize_tts(self, text: str, mood: str) -> str: ...


@runtime_checkable
class ISongCoverBackend(Protocol):
    """Segregated port for Feiyu GPU full-song AI cover synthesis."""

    async def synthesize_cover(
        self, audio_bytes: bytes, *, pitch_shift: int | None = None, max_seconds: int = 240
    ) -> str: ...


@runtime_checkable
class IQQMediaGateway(Protocol):
    """Port for pulling QQ media and turning it into model-consumable payloads."""

    async def newest_media(self, chat_key: str, kind: str) -> MediaAttachment | None: ...
    async def load_data_url(self, item: MediaAttachment) -> str: ...
    async def video_frame_urls(self, item: MediaAttachment, count: int) -> tuple[str, ...]: ...
    async def voice_to_text(self, item: MediaAttachment) -> str: ...


@runtime_checkable
class ICaptionGateway(Protocol):
    """Segregated port for on-demand image captioning plus durable caption caching."""
    async def describe_image(self, ref: str) -> str: ...
    async def cache_media_description(self, item: MediaAttachment, caption: str) -> None: ...


@runtime_checkable
class IOneBotApiCaller(Protocol):
    """Minimal protocol wrapping OneBot V11 call_api for DIP across layers (<=5 methods)."""

    async def call_api(self, api: str, **data: Any) -> Any: ...


@runtime_checkable
class IBiliClient(Protocol):
    """Segregated port for Bilibili video search, detail lookup, popular list & audio fetch."""

    async def search_videos(self, keyword: str, limit: int = 5) -> list[dict[str, Any]]: ...
    async def video_info(self, bvid: str) -> dict[str, Any]: ...
    async def popular(self, limit: int = 5) -> list[dict[str, Any]]: ...
    async def fetch_song_audio(self, query: str) -> tuple[bytes, str, str]: ...
