"""Outbound argument preparation shared by agent turns and cross-chat tools."""

from __future__ import annotations

from typing import Any

from echomind.mind.ban_control import purge_message_batch


def prepare_voice(
    chat_key: str, name: str, args: dict[str, Any], sent_texts: list[str],
    bans: tuple[str, ...],
) -> tuple[dict[str, Any] | None, str]:
    if name == "feiyu_say":
        if sent_texts:
            return None, "本轮已发送过文字或语音回复，请勿重复再用语音念一遍，直接结束即可。"
        kept = purge_message_batch(str(args.get("text", "")), bans)
        if not kept:
            return None, "已拦截：语音内容命中管理员禁用词，未发送"
        sent_texts.append(kept[0])
        return {**args, "text": kept[0]}, ""
    if name == "feiyu_cover":
        sent_texts.append(f"[翻唱:{args.get('song', '')}]")
    return args, ""


def prepare_cross_chat(
    chat_key: str, args: dict[str, Any], sent_texts: list[str],
    bans: tuple[str, ...],
) -> tuple[dict[str, Any] | None, str]:
    if sent_texts:
        return None, "本轮已发送过消息，请勿重复跨会话连发，直接结束即可。"
    kept = purge_message_batch(args.get("messages", []), bans)
    if not kept:
        return None, "已拦截：跨会话内容命中管理员禁用词，未发送"
    sent_texts.extend(kept)
    return {**args, "messages": list(kept)}, ""
