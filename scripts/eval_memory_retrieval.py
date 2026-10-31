#!/usr/bin/env python
"""D15: measure lexical retrieval recall on paraphrase queries (no model calls)."""

from __future__ import annotations

import json
from pathlib import Path

from echomind.domain.models import SemanticFact
from echomind.mind.ebbinghaus import select_relevant_facts

ROOT = Path(__file__).resolve().parents[1]

# (query, target fact text) — paraphrases deliberately avoid the target's wording.
PAIRS: tuple[tuple[str, str], ...] = (
    ("家里那只小东西最近胃口不好", "橘猫的猫粮吃得很少"),
    ("那份工作还顺利吗", "新岗位还在适应"),
    ("你昨晚几点睡的", "熬夜到凌晨两点"),
    ("假期想出门走走吗", "周末计划去爬山"),
    ("她平时喝什么咖啡", "只喝美式"),
    ("材料什么时候要交", "下周三截止"),
    ("L 最近身体怎么样", "在休养"),
    ("那部片子看完哭了吗", "电影很催泪"),
    ("天气不好会害怕吗", "怕打雷"),
    ("这个月钱够花吗", "预算超了"),
)

DISTRACTORS: tuple[tuple[str, str], ...] = (
    ("群规", "周五晚上发图"),
    ("梗", "B 站热门视频"),
    ("游戏", "昨晚排位连胜"),
    ("天气", "今天降温"),
    ("外卖", "中午吃了面"),
    ("宠物", "楼下狗很吵"),
    ("工作", "周报还没写"),
    ("学习", "单词背到第三单元"),
    ("出行", "地铁二号线停运"),
    ("电影", "新片下周上映"),
    ("音乐", "循环一首老歌"),
    ("睡眠", "午睡二十分钟"),
    ("饮食", "少糖少冰"),
    ("运动", "跑步三公里"),
    ("购物", "买了双鞋"),
    ("家务", "周末大扫除"),
    ("朋友", "老同学来出差"),
    ("计划", "下月去海边"),
    ("健康", "体检报告正常"),
    ("心情", "今天有点低落"),
)


def _facts() -> tuple[SemanticFact, ...]:
    rows = [("目标", text) for _q, text in PAIRS]
    rows += list(DISTRACTORS)
    return tuple(
        SemanticFact(chat_key="eval", subject=subject, fact_text=text, confidence=0.9)
        for subject, text in rows
    )


def _bigram_hits(facts: tuple[SemanticFact, ...]) -> tuple[int, list[dict[str, object]]]:
    import math
    from collections import Counter

    texts = [f.fact_text for f in facts]
    grams = [{t[i:i + 2] for i in range(len(t) - 1)} for t in texts]
    df: Counter[str] = Counter()
    for bag in grams:
        df.update(bag)
    idf = {g: math.log((len(texts) + 1) / (c + 1)) + 1 for g, c in df.items()}

    def score(query: str, index: int) -> float:
        q = {query[i:i + 2] for i in range(len(query) - 1)}
        return sum(idf.get(g, 0.0) for g in q & grams[index])

    hits = 0
    details: list[dict[str, object]] = []
    for query, target in PAIRS:
        ranked = sorted(range(len(texts)), key=lambda i: score(query, i), reverse=True)[:5]
        found = target in [texts[i] for i in ranked]
        hits += int(found)
        details.append({"query": query, "target": target, "found": found})
    return hits, details


def main() -> int:
    facts = _facts()
    hits = 0
    details: list[dict[str, object]] = []
    for query, target in PAIRS:
        picked = select_relevant_facts(facts, query, limit=5)
        texts = [f.fact_text for f in picked]
        found = target in texts
        hits += int(found)
        details.append({"query": query, "target": target, "found": found,
                        "rank": texts.index(target) + 1 if found else None})
    bigram_hits, bigram_details = _bigram_hits(facts)
    payload = {
        "n": len(PAIRS),
        "recall_at_5": round(hits / len(PAIRS), 3),
        "recall_at_5_bigram_idf": round(bigram_hits / len(PAIRS), 3),
        "details": details,
        "bigram_details": bigram_details,
    }
    out = ROOT / "reports" / "memory_retrieval_baseline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"recall@5 = {hits}/{len(PAIRS)} = {payload['recall_at_5']}")
    print(f"bigram-idf recall@5 = {bigram_hits}/{len(PAIRS)} = "
          f"{payload['recall_at_5_bigram_idf']}")
    for row in details:
        print(f"  {'OK ' if row['found'] else 'MISS'} {row['query']}")
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
