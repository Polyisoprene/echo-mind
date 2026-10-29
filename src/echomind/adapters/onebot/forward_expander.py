"""M18.1 Recursive Multi-Level Forward Message Unpacker & ReadForwardTool."""

from __future__ import annotations

import re
from typing import Any

from echomind.domain.models import MediaAttachment, Percept
from echomind.domain.ports import IAsyncSqlStore, IOneBotApiCaller

CQ_STRIP_RE = re.compile(r"\[CQ:[^\]]*\]")
FWD_ID_RE = re.compile(r"id=([^\s\]]+)")


def _node_sender_label(node: dict[str, Any]) -> str:
    sender = node.get("sender")
    s_dict = sender if isinstance(sender, dict) else {}
    name = str(
        s_dict.get("card")
        or s_dict.get("nickname")
        or node.get("nickname")
        or node.get("user_id")
        or "群友"
    ).strip()
    uid = str(s_dict.get("user_id") or node.get("user_id") or "").strip()
    return f"{name}(QQ:{uid})" if (uid and uid != name) else name


def _extract_node_List_from_resp(resp: Any) -> list[dict[str, Any]]:
    if not isinstance(resp, dict):
        return []
    msgs = resp.get("messages")
    if isinstance(msgs, list):
        return [m for m in msgs if isinstance(m, dict)]
    data = resp.get("data")
    if isinstance(data, dict) and isinstance(data.get("messages"), list):
        return [m for m in data["messages"] if isinstance(m, dict)]
    return []


async def _try_call_forward(caller: IOneBotApiCaller, **params: Any) -> list[dict[str, Any]]:
    try:
        resp = await caller.call_api("get_forward_msg", **params)
        return _extract_node_List_from_resp(resp)
    except Exception:
        return []


async def _fetch_forward_nodes(
    caller: IOneBotApiCaller, message_id: str = "", res_id: str = ""
) -> list[dict[str, Any]]:
    clean_mid = message_id.lstrip("#").strip()
    if clean_mid.lstrip("-").isdigit():
        nodes = await _try_call_forward(caller, message_id=int(clean_mid))
        if nodes:
            return nodes
    target_id = res_id.strip() or clean_mid
    if not target_id:
        return []
    return await _try_call_forward(caller, id=target_id, message_id=target_id)


def _inline_child_nodes(seg_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = seg_data.get("content") or seg_data.get("messages")
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


SIMPLE_SEG_LABELS = {"face": "[表情]", "mface": "[表情]", "video": "[视频]", "record": "[语音]"}


def _seg_simple_text(seg_type: str, s_data: dict[str, Any], media: list[MediaAttachment]) -> str:
    if seg_type == "text":
        return str(s_data.get("text", ""))
    if seg_type == "image":
        url, f_key = str(s_data.get("url", "")), str(s_data.get("file", ""))
        if url or f_key:
            media.append(MediaAttachment(kind="image", url=url, local_path=f_key))
        return "[图片]"
    if seg_type == "at":
        qq = str(s_data.get("qq", ""))
        return f"@{s_data.get('name') or qq} "
    return SIMPLE_SEG_LABELS.get(seg_type, "")


async def _render_one_seg(
    caller: IOneBotApiCaller,
    seg: dict[str, Any],
    media: list[MediaAttachment],
    depth: int,
    max_depth: int,
) -> str:
    s_type = str(seg.get("type", ""))
    raw_d = seg.get("data")
    s_data: dict[str, Any] = raw_d if isinstance(raw_d, dict) else {}
    if s_type not in ("forward", "node"):
        return _seg_simple_text(s_type, s_data, media)
    if depth < max_depth:
        return await _expand_nested_segment(caller, s_data, media, depth + 1, max_depth)
    return "[深层嵌套转发]"


async def _render_segments_recursive(
    caller: IOneBotApiCaller,
    segs: list[Any],
    media: list[MediaAttachment],
    depth: int,
    max_depth: int,
) -> str:
    dict_segs = [s for s in segs if isinstance(s, dict)]
    parts = [await _render_one_seg(caller, s, media, depth, max_depth) for s in dict_segs]
    return " ".join(p.strip() for p in parts if p.strip())


async def _expand_nested_segment(
    caller: IOneBotApiCaller,
    s_data: dict[str, Any],
    media: list[MediaAttachment],
    next_depth: int,
    max_depth: int,
) -> str:
    child_nodes = _inline_child_nodes(s_data)
    if not child_nodes:
        nested_id = str(s_data.get("id") or s_data.get("res_id") or "").strip()
        if nested_id:
            child_nodes = await _fetch_forward_nodes(caller, res_id=nested_id)
    if not child_nodes:
        return "[嵌套转发记录]"
    sub_lines = await _format_node_list(caller, child_nodes, media, next_depth, max_depth)
    indent = "  " * (next_depth - 1)
    header = f"\n{indent}📦 [第{next_depth}层嵌套转发 共{len(child_nodes)}条]"
    return header + ("\n" + "\n".join(sub_lines) if sub_lines else "")


async def _format_single_node(
    caller: IOneBotApiCaller,
    node: dict[str, Any],
    media: list[MediaAttachment],
    depth: int,
    max_depth: int,
) -> str:
    raw_msg = node.get("message", node.get("content", ""))
    if isinstance(raw_msg, str):
        body = CQ_STRIP_RE.sub("", raw_msg).strip()
    else:
        segs = (
            [raw_msg]
            if isinstance(raw_msg, dict)
            else (raw_msg if isinstance(raw_msg, list) else [])
        )
        body = await _render_segments_recursive(caller, segs, media, depth, max_depth)
    if not body:
        return ""
    indent = "  " * (depth - 1)
    prefix = "├─ " if depth > 1 else ""
    return f"{indent}{prefix}{_node_sender_label(node)}: {body[:260]}"


async def _format_node_list(
    caller: IOneBotApiCaller,
    nodes: list[dict[str, Any]],
    media: list[MediaAttachment],
    depth: int,
    max_depth: int,
) -> list[str]:
    lines: list[str] = []
    for node in nodes[:25]:
        line = await _format_single_node(caller, node, media, depth, max_depth)
        if line:
            lines.append(line)
    return lines


async def expand_forward_tree(
    caller: IOneBotApiCaller,
    *,
    message_id: str = "",
    res_id: str = "",
    max_depth: int = 4,
) -> tuple[str, tuple[MediaAttachment, ...]]:
    """Unpack a 1-to-N-level nested OneBot forward message tree into readable text and media."""
    nodes = await _fetch_forward_nodes(caller, message_id=message_id, res_id=res_id)
    if not nodes:
        return "", ()
    media: list[MediaAttachment] = []
    lines = await _format_node_list(caller, nodes, media, depth=1, max_depth=max_depth)
    if not lines:
        return f"[合并转发 共{len(nodes)}条]", tuple(media)
    head = f"📨 [合并转发聊天记录 共{len(nodes)}条]"
    return head + "\n" + "\n".join(lines)[:2800], tuple(media)


async def expand_incoming_forward(caller: IOneBotApiCaller, percept: Percept) -> Percept:
    """Automatically unpack incoming forward messages before storing and evaluating."""
    if "[合并转发" not in percept.text:
        return percept
    m = FWD_ID_RE.search(percept.text)
    res_id = m.group(1) if m else ""
    expanded_text, extra_media = await expand_forward_tree(
        caller, message_id=percept.message_id, res_id=res_id
    )
    if not expanded_text:
        return percept
    merged_media = (*percept.media, *extra_media)
    return percept.model_copy(update={"text": expanded_text, "media": merged_media})


class ReadForwardTool:
    """Tool allowing the LLM to expand and inspect single or multi-level nested forward records."""

    category = "信息探索"

    def __init__(self, caller: IOneBotApiCaller, db: IAsyncSqlStore) -> None:
        self._caller = caller
        self._db = db

    @property
    def name(self) -> str:
        return "read_forward"

    @property
    def description(self) -> str:
        return (
            "展开查看合并转发聊天记录（支持多层套娃嵌套转发自动逐层展开）："
            "传入那条转发消息开头的 #数字（message_id）或转发 id。"
        )

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "要展开的转发消息编号（聊天记录里的 #数字，去掉 #）或转发 id",
                },
            },
            "required": ["message_id"],
        }

    async def execute(self, chat_key: str, args: dict[str, Any]) -> str:
        raw_id = str(args.get("message_id", "")).lstrip("#").strip()
        if not raw_id:
            return "缺少要展开的 message_id"
        text, _ = await expand_forward_tree(self._caller, message_id=raw_id, res_id=raw_id)
        if not text:
            return f"展开转发记录 #{raw_id} 失败：内容为空或已过期。"
        async with self._db.connect() as conn:
            await conn.execute(
                "UPDATE chat_messages SET text = ? WHERE chat_key = ? AND mid = ?",
                (text, chat_key, raw_id),
            )
            await conn.commit()
        return text
