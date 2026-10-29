"""Voice skills: speak with her own voice, and listen to voice messages."""

from __future__ import annotations

import json
from typing import Any

from echomind.domain.models import SkillConfigField
from echomind.domain.ports import (
    IBiliClient,
    IMessageSender,
    IQQMediaGateway,
    ISongCoverBackend,
    IVoiceBackend,
)

MAX_SPEAK_CHARS = 120

FEIYU_FIELDS = (
    SkillConfigField(
        key="base_url",
        label="语音服务地址",
        kind="text",
        default="http://192.168.3.2:9880",
        placeholder="http://192.168.3.2:9880",
    ),
    SkillConfigField(
        key="api_key",
        label="API Key",
        kind="password",
        secret=True,
        placeholder="飞鱼语音服务 Bearer Key",
    ),
    SkillConfigField(
        key="default_style",
        label="默认语气风格",
        kind="text",
        default="cute",
        placeholder="cute（活泼）或 gentle（温柔）",
    ),
)


class FeiyuSayTool:
    """Synthesize and send a short voice message through the Feiyu GPU service."""

    config_key = "feiyu_voice"

    def config_fields(self) -> tuple[SkillConfigField, ...]:
        return FEIYU_FIELDS

    def __init__(self, voice: IVoiceBackend, sender: IMessageSender) -> None:
        self._voice = voice
        self._sender = sender

    @property
    def category(self) -> str:
        return "语音表达"

    @property
    def name(self) -> str:
        return "feiyu_say"

    @property
    def description(self) -> str:
        return (
            "用你自己的声音发一条真正的 QQ 语音消息（GPU 常驻，约10秒合成）。"
            "这是你日常说话的方式之一——想发就主动发，不必等别人要求！"
            "亲近互动、哄人、晚安、吃醋哼哼、情绪化短句或想让人听见你语气时直接调用本工具代替发文字。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要亲口说的话（纯口语，勿写emoji/markdown/动作，60字内）",
                },
                "mood": {
                    "type": "string",
                    "description": "语气风格：cute（活泼可爱）/ gentle（温柔轻声）",
                },
            },
            "required": ["text"],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        text = str(args.get("text", "")).strip()[:MAX_SPEAK_CHARS]
        if not text:
            return "语音文本为空"
        mood = str(args.get("mood", "cute")).strip() or "cute"
        audio_b64 = await self._voice.synthesize_tts(text, mood)
        if not audio_b64:
            return "语音合成失败，没有拿到音频。"
        mid = await self._sender.send_voice(chat_key, audio_b64, text)
        return json.dumps(
            {
                "ok": bool(mid),
                "message_id": mid or "",
                "text": text,
                "note": "语音已直接发出，切勿再用 send_message 重复把同一句话发成文字。",
            },
            ensure_ascii=False,
        )


class FeiyuCoverTool:
    """Sing a complete song with accompaniment via Bilibili audio + Feiyu GPU RVC cover."""

    config_key = "feiyu_voice"

    def config_fields(self) -> tuple[SkillConfigField, ...]:
        return FEIYU_FIELDS

    def __init__(
        self, voice: ISongCoverBackend, bili: IBiliClient, sender: IMessageSender
    ) -> None:
        self._voice = voice
        self._bili = bili
        self._sender = sender

    @property
    def category(self) -> str:
        return "语音表达"

    @property
    def name(self) -> str:
        return "feiyu_cover"

    @property
    def description(self) -> str:
        return (
            "用你自己的声音唱一整首带伴奏的完整歌曲（全曲 AI 翻唱，点歌/唱歌首选工具！）："
            "传入歌名（如『周杰伦 晴天』『花泽香菜 恋爱循环』）或 B站 BV 号，自动检索原曲、"
            "分离伴奏并用你的声音合成完整翻唱语音发到群聊或私聊。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "song": {
                    "type": "string",
                    "description": "要唱的歌名（建议『歌手 歌名』，如『周杰伦 晴天』）或 B站 BV 号",
                },
                "pitch_shift": {
                    "type": "integer",
                    "description": "可选：升降调半音数（-12~12；男声原曲建议填 12，女声填 0）",
                },
                "max_seconds": {
                    "type": "integer",
                    "description": "可选：最长演唱秒数（默认 240 秒唱完一整首，只想唱半首可设 90）",
                },
            },
            "required": ["song"],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        song = str(args.get("song", "")).strip()
        if not song:
            return "缺少要唱的歌名（song）"
        raw_pitch = args.get("pitch_shift")
        pitch = int(raw_pitch) if isinstance(raw_pitch, (int, float)) else None
        try:
            max_sec = int(args.get("max_seconds", 240) or 240)
        except (TypeError, ValueError):
            max_sec = 240
        audio_bytes, title, bvid = await self._bili.fetch_song_audio(song)
        audio_b64 = await self._voice.synthesize_cover(
            audio_bytes, pitch_shift=pitch, max_seconds=max_sec
        )
        if not audio_b64:
            return f"《{title}》翻唱合成失败，未拿到音频。"
        mid = await self._sender.send_voice(chat_key, audio_b64, f"[翻唱]《{title}》")
        return json.dumps(
            {
                "ok": bool(mid),
                "message_id": mid or "",
                "song": title,
                "bvid": bvid,
                "note": "完整翻唱语音已发出，可简短搭一句短话（勿重复汇报已发送）。",
            },
            ensure_ascii=False,
        )


class ReadVoiceTool:
    """Listen to the newest voice message and turn it into text."""

    def __init__(self, media: IQQMediaGateway) -> None:
        self._media = media

    @property
    def category(self) -> str:
        return "媒体感知"

    @property
    def name(self) -> str:
        return "read_voice"

    @property
    def description(self) -> str:
        return "把群里最新发来的语音消息转写成文字。"

    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        item = await self._media.newest_media(chat_key, "voice")
        if item is None:
            return "最近没有找到可以听的语音。"
        text = await self._media.voice_to_text(item)
        if not text:
            return "语音转文字失败了，可能协议端没开语音转写。"
        return f"🎧 语音内容是：「{text}」"
