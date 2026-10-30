"""Pure OneBot v11 event -> Percept parsing (no I/O, fully unit-testable)."""

from __future__ import annotations

import re
import time
from typing import Any, Literal

from echomind.domain.models import MediaAttachment, Percept

CQ_CODE_RE = re.compile(r"\[CQ:([a-zA-Z_]+)(?:,[^\]]*)?\]")
CQ_LABELS = {
    "image": "[图片]",
    "face": "[表情]",
    "mface": "[表情]",
    "record": "[语音]",
    "video": "[视频]",
    "forward": "[合并转发聊天记录]",
}


def humanize_cq(raw: str) -> str:
    """Replace OneBot CQ codes with readable placeholders."""

    def _sub(match: re.Match[str]) -> str:
        return CQ_LABELS.get(match.group(1), "")

    return CQ_CODE_RE.sub(_sub, raw).strip()


def _iter_valid_segs(segs: list[Any]) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    for seg in segs:
        if isinstance(seg, dict) and isinstance(seg.get("data"), dict):
            out.append((str(seg.get("type", "")), seg["data"]))
    return out


MEDIA_KIND_MAP: dict[str, Literal["image", "voice", "video_frames"]] = {
    "image": "image",
    "record": "voice",
    "video": "video_frames",
}


def _extract_media_list(
    valid: list[tuple[str, dict[str, Any]]], ev_mid: str = ""
) -> list[MediaAttachment]:
    return [
        MediaAttachment(
            kind=MEDIA_KIND_MAP[t],
            url=str(d.get("url", "")),
            local_path=str(d.get("file", "")),
            message_id=str(d.get("message_id") or ev_mid),
        )
        for t, d in valid
        if t in MEDIA_KIND_MAP
    ]


def _extract_reply_mid(valid: list[tuple[str, dict[str, Any]]]) -> str:
    for t, d in valid:
        if t == "reply":
            return str(d.get("id", ""))
    return ""


def _seg_to_text(seg_type: str, data: dict[str, Any], self_id: str) -> str:
    if seg_type in ("text", "json"):
        return str(data.get("text", data.get("data", "")))
    if seg_type == "forward":
        fid = str(data.get("id") or data.get("res_id") or "").strip()
        return f"[合并转发聊天记录 id={fid}] " if fid else "[合并转发聊天记录] "
    if seg_type == "at":
        qq = str(data.get("qq", "")).strip()
        if qq and qq != self_id:
            name = str(data.get("name", "")).strip().lstrip("@")
            return f"@{name or qq}(QQ:{qq}) "
    return ""


def _extract_segments_info(
    segs: list[Any], self_id: str, ev_mid: str = ""
) -> tuple[str, bool, str, list[MediaAttachment]]:
    valid = _iter_valid_segs(segs)
    texts = [_seg_to_text(t, d, self_id) for t, d in valid]
    is_at = any(t == "at" and str(d.get("qq", "")) == self_id for t, d in valid)
    return (
        "".join(texts).strip(),
        is_at,
        _extract_reply_mid(valid),
        _extract_media_list(valid, ev_mid),
    )


def _parse_poke_event(
    ev: dict[str, Any], self_id: str, allowed_groups: frozenset[str], now_ms: int
) -> Percept | None:
    if str(ev.get("sub_type", "")) != "poke" or str(ev.get("target_id", "")) != self_id:
        return None
    gid = str(ev.get("group_id", ""))
    uid = str(ev.get("user_id", ""))
    if gid and gid not in allowed_groups:
        return None
    return Percept(
        chat_key=f"group:{gid}" if gid else f"private:{uid}",
        scene="group" if gid else "private",
        message_id=f"poke_{now_ms}",
        timestamp_ms=now_ms,
        sender_id=uid,
        sender_name=uid,
        text="[拍了拍你]",
        is_poke_me=True,
    )


def _is_allowed_message(
    ev: dict[str, Any],
    self_id: str,
    allowed_groups: frozenset[str],
    operator_ids: tuple[str, ...],
    allowed_private: frozenset[str] = frozenset(),
) -> bool:
    uid = str(ev.get("user_id", ""))
    if uid == self_id:
        return False
    mtype = str(ev.get("message_type", ""))
    if mtype == "group":
        return str(ev.get("group_id", "")) in allowed_groups
    if not operator_ids and not allowed_private:
        return True
    return uid in operator_ids or (uid in allowed_private)


def _resolve_sender_name(ev: dict[str, Any], uid: str) -> str:
    sender = ev.get("sender")
    if not isinstance(sender, dict):
        return uid
    card = str(sender.get("card", "")).strip()
    nick = str(sender.get("nickname", "")).strip()
    return card or nick or uid


def parse_onebot_event(
    ev: dict[str, Any], self_id: str, allowed_groups: frozenset[str],
    operator_ids: tuple[str, ...], allowed_private: frozenset[str] = frozenset(),
) -> Percept | None:
    """Parse a raw OneBot v11 message/poke event dict into an immutable Percept."""
    post_type = str(ev.get("post_type", ""))
    now_ms = int(ev.get("time", time.time()) * 1000)
    if post_type == "notice":
        return _parse_poke_event(ev, self_id, allowed_groups, now_ms)
    if post_type != "message" or not _is_allowed_message(
        ev, self_id, allowed_groups, operator_ids, allowed_private
    ):
        return None
    uid, mtype = str(ev.get("user_id", "")), str(ev.get("message_type", ""))
    gid, ev_mid = str(ev.get("group_id", "")), str(ev.get("message_id", ""))
    raw_msg = ev.get("message", [])
    segs = raw_msg if isinstance(raw_msg, list) else []
    txt, is_at, reply_mid, media = _extract_segments_info(segs, self_id, ev_mid)
    if txt:
        final_txt = txt
    elif media:
        final_txt = {"image": "[图片]", "voice": "[语音]", "video_frames": "[视频]"}.get(
            media[0].kind, "[媒体]"
        )
    else:
        final_txt = humanize_cq(str(ev.get("raw_message", "")))
    return Percept(
        chat_key=f"group:{gid}" if mtype == "group" else f"private:{uid}",
        scene="group" if mtype == "group" else "private",
        message_id=ev_mid, timestamp_ms=now_ms, sender_id=uid,
        sender_name=_resolve_sender_name(ev, uid), text=final_txt or "[图片/表情]",
        is_at_me=is_at, quoted_message_id=reply_mid, media=tuple(media),
    )
