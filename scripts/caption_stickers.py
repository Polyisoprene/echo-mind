"""给表情包库补齐描述与场景标签：缺描述的用多模态看一眼，已描述的按关键词打标签。

用法：uv run python scripts/caption_stickers.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from echomind.core.config import load_config_from_json

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "echomind.db"
CONFIG_PATH = ROOT / "data" / "config.json"

VOCAB = ("开心", "卖萌", "无语", "委屈", "嫌弃", "惊讶", "害羞", "生气", "发呆")

TAG_RULES: dict[str, tuple[str, ...]] = {
    "开心": ("笑", "开心", "得意", "兴奋", "哈哈", "乐"),
    "卖萌": ("卖萌", "装傻", "撒娇", "可爱", "比心", "自恋"),
    "无语": ("无语", "憨", "扣着", "盆", "汗", "傻"),
    "委屈": ("委屈", "哭", "讨饶", "可怜", "求"),
    "嫌弃": ("嫌弃", "白眼", "不服", "皱眉", "啧", "鄙视"),
    "惊讶": ("惊", "吓", "!!?", "震", "呆滞"),
    "害羞": ("害羞", "脸红", "羞"),
    "生气": ("生气", "怒", "鼓", "凶"),
    "发呆": ("发呆", "无聊", "等回复", "托腮", "放空"),
}

CAPTION_PROMPT = (
    "这是一张 QQ 聊天用的表情包。请输出两行，不要多余文字：\n"
    "描述：<一句话说清画面里是谁/什么、表情动作、是否有文字，并点明适合在什么场景发>\n"
    f"标签：<从这些词里选 1~2 个最贴切的，用逗号分隔：{'、'.join(VOCAB)}>"
)


def derive_tags(description: str) -> tuple[str, ...]:
    """从描述文字里推断场景标签。"""
    hits = [tag for tag, words in TAG_RULES.items() if any(w in description for w in words)]
    return tuple(hits[:2])


def local_path_of(file_ref: str) -> Path | None:
    if not file_ref.lower().startswith("file://"):
        return None
    path = Path(unquote(urlparse(file_ref).path))
    return path if path.is_file() else None


def parse_caption(raw: str) -> tuple[str, tuple[str, ...]]:
    desc, tags = "", ()
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("描述："):
            desc = line[3:].strip()
        elif line.startswith("标签："):
            picked = [t.strip() for t in line[3:].replace("，", ",").split(",")]
            tags = tuple(t for t in picked if t in VOCAB)[:2]
    return desc or raw.strip()[:120], tags


async def caption_with_vision(
    client: httpx.AsyncClient, base_url: str, api_key: str, model: str, data_url: str
) -> tuple[str, tuple[str, ...]]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": CAPTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    resp = await client.post(f"{base_url.rstrip('/')}/chat/completions", headers=headers, json=payload)
    resp.raise_for_status()
    body = resp.json()
    choices = body.get("choices") or []
    content = ""
    if choices and isinstance(choices[0], dict):
        content = str(choices[0].get("message", {}).get("content") or "")
    return parse_caption(content)


async def main(dry_run: bool) -> None:
    cfg = load_config_from_json(CONFIG_PATH)
    endpoint = cfg.primary_llm
    conn = sqlite3.connect(DB_PATH)
    rows = list(
        conn.execute(
            "SELECT id, local_file, local_note, desc_text, scene_tags, url "
            "FROM stickers ORDER BY id"
        )
    )
    need_caption = [r for r in rows if not (str(r[2] or "").strip() or str(r[3] or "").strip())]
    need_tags = [r for r in rows if not str(r[4] or "").strip()]
    print(f"共 {len(rows)} 张；缺描述 {len(need_caption)} 张；缺标签 {len(need_tags)} 张")

    async with httpx.AsyncClient(timeout=90.0, trust_env=False) as client:
        for sid, file_ref, _note, _desc, _tags, remote_url in need_caption:
            path = local_path_of(str(file_ref))
            if path is not None:
                raw, suffix = path.read_bytes(), path.suffix.lower()
            elif str(remote_url or "").startswith("http"):
                try:
                    got = await client.get(str(remote_url))
                    got.raise_for_status()
                    raw, suffix = got.content, ".jpg"
                except Exception as exc:  # noqa: BLE001
                    print(f"  跳过 {sid}：下载失败 {exc}")
                    continue
            else:
                print(f"  跳过 {sid}：既无本地文件也无直链")
                continue
            b64 = base64.b64encode(raw).decode("ascii")
            mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
            try:
                desc, tags = await caption_with_vision(
                    client, endpoint.base_url, endpoint.api_key, endpoint.model, f"data:{mime};base64,{b64}"
                )
            except Exception as exc:  # noqa: BLE001 - 单张失败不应中断整批
                print(f"  失败 {sid}：{exc}")
                continue
            final_tags = tags or derive_tags(desc)
            print(f"  ✔ {sid}: {desc[:50]} [{','.join(final_tags)}]")
            if not dry_run:
                conn.execute(
                    "UPDATE stickers SET local_note = ?, scene_tags = ? WHERE id = ?",
                    (desc, ",".join(final_tags), sid),
                )
                conn.commit()

    for sid, _file_ref, note, desc, _tags, _url in need_tags:
        text = str(note or desc or "")
        if not text.strip():
            continue
        derived = derive_tags(text)
        if not derived:
            derived = ("卖萌",)
        print(f"  🏷 {sid}: [{','.join(derived)}]")
        if not dry_run:
            conn.execute("UPDATE stickers SET scene_tags = ? WHERE id = ?", (",".join(derived), sid))
            conn.commit()

    total_tagged = conn.execute(
        "SELECT COUNT(*) FROM stickers WHERE TRIM(scene_tags) <> ''"
    ).fetchone()[0]
    total_described = conn.execute(
        "SELECT COUNT(*) FROM stickers WHERE TRIM(COALESCE(local_note,'')) <> '' OR TRIM(COALESCE(desc_text,'')) <> ''"
    ).fetchone()[0]
    print(f"完成：有描述 {total_described}/{len(rows)}，有标签 {total_tagged}/{len(rows)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
