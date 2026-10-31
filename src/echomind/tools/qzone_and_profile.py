"""Qzone dynamic publishing & QQ personal signature tools with showcase config fields."""

from __future__ import annotations

import json
from typing import Any

from echomind.domain.models import SkillConfigField
from echomind.domain.ports import IOneBotApiCaller

QZONE_SHOWCASE_FIELDS: tuple[SkillConfigField, ...] = (
    SkillConfigField(key="token_budget_proactive", label="主动发言 token 预算",
                     kind="number", default="300", placeholder="默认 300"),
    SkillConfigField(key="token_budget_post", label="空间说说 token 预算",
                     kind="number", default="400", placeholder="默认 400"),
    SkillConfigField(key="token_budget_signature", label="签名 token 预算",
                     kind="number", default="120", placeholder="默认 120"),
    SkillConfigField(
        key="signature_enabled",
        label="自动改个性签名 (1=开/0=关)",
        default="1",
        placeholder="1 开启定时自动改签名，0 关闭",
    ),
    SkillConfigField(
        key="signature_per_day",
        label="签名每天最多改几次",
        kind="number",
        default="3",
        placeholder="默认 3 次",
    ),
    SkillConfigField(
        key="signature_interval_min",
        label="两次改签名最小间隔(分钟)",
        kind="number",
        default="240",
        placeholder="默认 240 分钟",
    ),
    SkillConfigField(
        key="qzone_enabled",
        label="自动发空间说说 (1=开/0=关)",
        default="1",
        placeholder="1 开启定时自动发说说，0 关闭",
    ),
    SkillConfigField(
        key="qzone_per_day",
        label="说说每天最多发几条",
        kind="number",
        default="10",
        placeholder="默认 10 条",
    ),
    SkillConfigField(
        key="qzone_interval_min",
        label="两条说说最小间隔(分钟)",
        kind="number",
        default="120",
        placeholder="默认 120 分钟",
    ),
    SkillConfigField(
        key="proactive_enabled",
        label="定时主动发消息 (1=开/0=关)",
        default="1",
        placeholder="1 开启在活动时段内主动找在意的人/群聊说话",
    ),
    SkillConfigField(
        key="proactive_interval_min",
        label="主动发消息最小间隔(分钟)",
        kind="number",
        default="35",
        placeholder="默认 35 分钟",
    ),
    SkillConfigField(
        key="proactive_target",
        label="主动发消息目标列表 (支持多群/多人)",
        default="private:10001001, group:10002002",
        placeholder="多个目标用逗号分隔：private:QQ, group:群号, group:群号@QQ",
        help="可同时填多个目标：private:QQ(私聊个人)、group:群号(群聊冒泡)、group:群号@QQ(在群里@某人搭话)。",
    ),
    SkillConfigField(
        key="active_hours",
        label="允许活动时段 (HH:MM-HH:MM)",
        default="06:30-23:30",
        placeholder="06:30-23:30",
    ),
)
VISIBILITY_MAP: dict[str, int] = {"public": 1, "friends": 4, "self": 64}


class QzoneAndProfileTool:
    """Publish a text post to QQ Space (Qzone) via OneBot send_qzone_msg."""

    category = "空间与资料"
    config_key = "qzone_showcase"

    def __init__(self, caller: IOneBotApiCaller) -> None:
        self._caller = caller

    def config_fields(self) -> tuple[SkillConfigField, ...]:
        return QZONE_SHOWCASE_FIELDS

    @property
    def name(self) -> str:
        return "qzone_showcase"

    @property
    def description(self) -> str:
        return "空间与资料：action=post 发一条 QQ 空间说说；action=signature 修改个性签名。"

    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "post=发说说；signature=改签名"},
                "content": {"type": "string", "description": "正文（说说 10~200字/签名 5~50字）"},
                "visibility": {
                    "type": "string",
                    "description": "可见范围：public(所有人) / friends(好友) / self(仅自己)",
                },
            },
            "required": ["content"],
        }

    async def execute(self, _chat_key: str, args: dict[str, Any]) -> str:
        content = str(args.get("content") or args.get("signature") or "").strip()[:400]
        default_action = "signature" if "signature" in args else "post"
        if not content:
            return "未修改：签名内容为空" if default_action == "signature" else "未发布：内容为空"
        if str(args.get("action", default_action)).strip() == "signature":
            try:
                await self._caller.call_api("set_self_longnick", longNick=content)
            except Exception as exc:
                return f"修改签名失败：{exc}"
            return json.dumps({"ok": True, "signature": content}, ensure_ascii=False)
        vis_key = str(args.get("visibility", "public")).strip()
        right = VISIBILITY_MAP.get(vis_key, 1)
        try:
            res = await self._caller.call_api("send_qzone_msg", content=content, ugc_right=right)
        except Exception as exc:
            return f"发布空间说说失败：{exc}"
        tid = str(res.get("tid", "")) if isinstance(res, dict) else ""
        return json.dumps({"ok": True, "tid": tid, "content": content}, ensure_ascii=False)



# Backwards-compatible aliases: the two plugins are now one tool.
QzonePublishTool = QzoneAndProfileTool
ProfileSignatureTool = QzoneAndProfileTool
