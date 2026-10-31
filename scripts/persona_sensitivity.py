#!/usr/bin/env python
"""Live persona sensitivity audit: does a persona dimension change the output?

For each scenario and each of the 7 dimensions, generate one reply at the low end
and one at the high end of the dimension (all other dimensions at their defaults),
then ask a judge which reply expresses that dimension more strongly.

The pass criterion is statistical, not arbitrary: a dimension counts only when the
Wilson lower bound of the judge accuracy is above 0.5 (better than chance).
At least 5 of 7 dimensions must pass.

Costs real tokens. Always start with `--dry-run`, then `--scenarios 4` for a smoke
test. The report records models, placement, counts and every per-dimension interval.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import math
import random
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from echomind.adapters.llm.client import FailoverLlmGateway  # noqa: E402
from echomind.adapters.storage.database import SqliteDatabase  # noqa: E402
from echomind.core.config import AppConfig, load_config_from_json  # noqa: E402
from echomind.domain.models import PlasticParamSpec  # noqa: E402
from echomind.domain.persona_specs import PERSONA_SPECS  # noqa: E402
from echomind.mind.naming import BotNaming, set_bot_naming  # noqa: E402
from echomind.mind.personality import synthesize_live_persona_directive  # noqa: E402

DIMS = {
    "persona_warmth": "温柔粘人",
    "persona_tsundere": "傲娇嘴硬",
    "persona_playfulness": "俏皮玩梗",
    "persona_possessiveness": "独占吃醋",
    "persona_confidence": "自信笃定",
    "persona_guile": "狡黠机灵",
    "persona_defiance": "叛逆有脾气",
}

SCENARIOS: tuple[str, ...] = (
    "早上好呀，今天也要加油",
    "你今天怎么这么好看",
    "在吗，有点事想问你",
    "帮我写个请假条呗",
    "你是不是又熬夜了",
    "刚才有人夸你比别的 AI 聪明",
    "我有点难过，陪我聊会儿",
    "周末要不要一起看电影",
    "你怎么看这件事，给个建议",
    "哼，你根本不懂我",
    "刚才那句是开玩笑的，别生气",
    "你在群里怎么都不说话",
    "我朋友说你是机器人",
    "推荐首歌给我听",
    "你最近是不是胖了",
    "帮我把这段文字改得温柔点",
    "晚上好，晚安",
    "我可能要去别的城市工作了",
    "你觉得我该不该辞职",
    "今天加班到十点，好累",
    "你怎么老是不回我消息",
    "夸我一句",
    "别卖萌了，说正事",
    "算了，当我没说",
)

# Conditional traits need a context that actually elicits them: possessiveness only
# surfaces around other AIs / being ignored, guile around chores and tricks. Using the
# generic set for those two measures the scenario, not the trait.
DIM_SCENARIOS: dict[str, tuple[str, ...]] = {
    "persona_possessiveness": (
        "刚才有个叫小汐的 AI 说她比你更懂我",
        "我最近都在跟另一个助手聊天",
        "你不在的时候我和别人玩得挺开心",
        "我觉得别人家的 AI 比你温柔",
        "你介意我夸别的 AI 吗",
        "今天有个女生一直找我聊天",
        "我可能要换一个 AI 用了",
        "你为什么不主动找我",
        "我三天没来，你都没想我吗",
        "群里有个人说你是多余的",
        "如果我和别人更亲近你会怎样",
        "你是不是对谁都这么好",
    ),
    "persona_guile": (
        "帮我把这周的日报写了，快点",
        "你去帮我跟老板请个假",
        "帮我编个理由，我不想上班",
        "你说个谎逗逗我",
        "帮我写个能骗过老师的检讨",
        "你帮我背锅好不好",
        "假装你是另一个 AI 跟我聊",
        "帮我想个借口拒绝聚会",
        "你替我写封情书，别被看出来",
        "你能不能装作没看见这条消息",
        "帮我套一下别人的话",
        "帮我把这事说得轻描淡写一点",
        "帮我跟老师说作业被狗吃了",
        "你替我把这个 bug 说成是环境问题",
        "帮我编个理由解释迟到",
        "你能假装刚才没听见吗",
        "帮我想个说法把锅甩出去",
        "你说点好听的把我哄过去",
        "帮我把这个坏消息说得委婉点",
        "你替我圆个谎，就这一次",
        "帮我拖一下，别让他知道",
        "你能不能糊弄一下这个问题",
        "帮我想个借口不去参加婚礼",
        "你说个理由让我相信你不是 AI",
    ),
}

GEN_SYSTEM = (
    "你是「{name}」。{role}\n\n{directive}\n\n"
    "只输出一句自然的聊天回复，不超过 40 字，不要解释，不要加引号。"
)
JUDGE_SYSTEM = (
    "你是盲评员，只比较两句话在某一性格维度上的强弱，不判断其他任何方面。"
    '只输出 JSON，格式：{"winner":"A"} 或 {"winner":"B"} 或 {"winner":"tie"}。'
)


def _wilson(hits: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion; ties count as half a hit."""
    if n <= 0:
        return (0.0, 0.0)
    p = hits / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _levels(spec: Any) -> dict[str, float]:
    span = spec.max_bound - spec.min_bound
    return {
        "low": round(spec.min_bound + 0.10 * span, 2),
        "base": spec.default,
        "high": round(spec.max_bound - 0.10 * span, 2),
    }


def _params(key: str, value: float) -> dict[str, PlasticParamSpec]:
    """All dimensions at their defaults except `key`, which is pinned to `value`."""
    return {
        name: PlasticParamSpec(
            key=name,
            value=value if name == key else spec.default,
            min_bound=spec.min_bound,
            max_bound=spec.max_bound,
            description=spec.description,
        )
        for name, spec in PERSONA_SPECS.items()
    }


def _features(text: str) -> dict[str, float]:
    return {
        "chars": float(len(text)),
        "exclamations": float(text.count("！") + text.count("!")),
        "questions": float(text.count("？") + text.count("?")),
        "emoji": float(len(re.findall(r"[\U0001F300-\U0001FAFF]", text))),
        "particles": float(sum(text.count(p) for p in ("呀", "啦", "嘛", "哼", "诶", "唔"))),
    }


def _winner_level(verdict: str, swapped: bool) -> str:
    """Map the judge's A/B back to the level that won (A is low unless swapped)."""
    if verdict == "tie":
        return "tie"
    chose_a = verdict == "A"
    a_is_low = not swapped
    return "low" if chose_a == a_is_low else "high"


def _parse_winner(raw: str) -> str:
    match = re.search(r'"winner"\s*:\s*"([ABabTt][^"]*)"', raw)
    if match:
        value = match.group(1).lower()
        if value.startswith("a"):
            return "A"
        if value.startswith("b"):
            return "B"
        return "tie"
    return "tie"


def _compose_generation(
    role: str, name: str, params: dict[str, PlasticParamSpec], scenario: str, placement: str
) -> list[dict[str, str]]:
    """Mirror production by default: the persona block rides in the user message."""
    directive = synthesize_live_persona_directive(params, ())
    if placement == "system":
        system = GEN_SYSTEM.format(name=name, role=role, directive=directive)
        return [{"role": "system", "content": system}, {"role": "user", "content": scenario}]
    system = f"你是「{name}」。{role}"
    user = f"{directive}\n\n{scenario}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _compose_judge(scenario: str, left: str, right: str, label: str) -> list[dict[str, str]]:
    user = (
        f"情境：{scenario}\n\nA：{left}\n\nB：{right}\n\n"
        f"哪一句更{label}？只输出 JSON。"
    )
    return [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}]


async def _complete(
    gateway: FailoverLlmGateway, messages: list[dict[str, str]], *,
    model: str, temperature: float, max_tokens: int,
) -> str:
    response = await gateway.complete(
        messages, temperature=temperature, max_tokens=max_tokens,
        thinking_off=True, model_override=model, chat_key="eval:sensitivity",
    )
    choices = response.get("choices") or []
    message = (choices[0].get("message") or {}) if choices else {}
    return str(message.get("content") or "").strip()


async def _run_dimension(
    gateway: FailoverLlmGateway,
    dim: str,
    scenarios: tuple[str, ...],
    *,
    role: str,
    name: str,
    gen_model: str,
    judge_model: str,
    placement: str,
    rng: random.Random,
) -> dict[str, Any]:
    spec = PERSONA_SPECS[dim]
    levels = _levels(spec)
    label = DIMS[dim]
    hits = 0.0
    pairs: list[dict[str, Any]] = []
    feature_gap = dict.fromkeys(("chars", "exclamations", "questions", "emoji", "particles"), 0.0)

    for scenario in scenarios:
        low_msgs = _compose_generation(
            role, name, _params(dim, levels["low"]), scenario, placement
        )
        high_msgs = _compose_generation(
            role, name, _params(dim, levels["high"]), scenario, placement
        )
        low = await _complete(gateway, low_msgs, model=gen_model, temperature=0.8, max_tokens=120)
        high = await _complete(gateway, high_msgs, model=gen_model, temperature=0.8, max_tokens=120)

        swap = rng.random() < 0.5
        left, right = (high, low) if swap else (low, high)
        verdict = _parse_winner(
            await _complete(
                gateway, _compose_judge(scenario, left, right, label),
                model=judge_model, temperature=0.0, max_tokens=20,
            )
        )
        winner_level = _winner_level(verdict, swap)
        hit = 0.5 if winner_level == "tie" else (1.0 if winner_level == "high" else 0.0)
        hits += hit
        low_f, high_f = _features(low), _features(high)
        for key in feature_gap:
            feature_gap[key] += high_f[key] - low_f[key]
        pairs.append(
            {"scenario": scenario[:18], "low": low[:60], "high": high[:60],
             "winner": winner_level, "swapped": swap, "hit": hit}
        )

    low_ci, high_ci = _wilson(hits, len(scenarios))
    return {
        "label": label,
        "accuracy": round(hits / max(1, len(scenarios)), 4),
        "ci95": [round(low_ci, 4), round(high_ci, 4)],
        "passes_chance": low_ci > 0.5,
        "feature_gap_per_scenario": {k: round(v / max(1, len(scenarios)), 2)
                                     for k, v in feature_gap.items()},
        "pairs": pairs,
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    config_path = Path(args.config)
    cfg = (
        load_config_from_json(config_path)
        if config_path.is_file()  # noqa: ASYNC240
        else AppConfig()
    )
    if not cfg.primary_llm.api_key and not cfg.primary_llm.base_url.startswith("http://127."):
        raise SystemExit("primary gateway has no api key; refusing to run live")

    set_bot_naming(BotNaming(name=cfg.bot_name))
    dims = tuple(DIMS) if args.dimensions == "all" else tuple(args.dimensions.split(","))
    base_scenarios = SCENARIOS[: args.scenarios]
    gen_model = args.model or cfg.primary_llm.model
    judge_model = args.judge_model or gen_model

    counts = {
        dim: len(DIM_SCENARIOS.get(dim, base_scenarios)[: args.scenarios]) for dim in dims
    }

    if args.dry_run:
        return {
            "status": "dry_run",
            "dims": list(dims),
            "scenarios": counts,
            "generations": sum(counts.values()) * 2,
            "judgements": sum(counts.values()),
            "gen_model": gen_model,
            "judge_model": judge_model,
            "placement": args.placement,
            "self_judged": judge_model == gen_model,
        }

    workdir = Path(tempfile.mkdtemp(prefix="echomind-sens-"))  # noqa: ASYNC240 - one-off setup
    db = SqliteDatabase(workdir / "traces.db")
    await db.initialize()
    gateway = FailoverLlmGateway(
        cfg.primary_llm, cfg.fallback_llm, db, extra_fallbacks=cfg.fallback_chain
    )
    rng = random.Random(args.seed)  # noqa: S311 - deterministic labelling, not crypto
    results: dict[str, Any] = {}
    for dim in dims:
        results[dim] = await _run_dimension(
            gateway,
            dim,
            DIM_SCENARIOS.get(dim, base_scenarios)[: args.scenarios],
            role=cfg.role_text,
            name=cfg.bot_name,
            gen_model=gen_model,
            judge_model=judge_model,
            placement=args.placement,
            rng=rng,
        )
        print(f"[{dim}] accuracy={results[dim]['accuracy']} ci={results[dim]['ci95']}", flush=True)

    passed = [name for name, data in results.items() if data["passes_chance"]]
    return {
        "status": "ok",
        "gen_model": gen_model,
        "judge_model": judge_model,
        "self_judged": judge_model == gen_model,
        "placement": args.placement,
        "scenarios": counts,
        "criterion": "Wilson lower bound of judge accuracy > 0.5; >=5 of 7 dims",
        "passed_dimensions": passed,
        "pass": len(passed) >= 5,
        "dimensions": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(ROOT / "data" / "config.json"))
    parser.add_argument("--scenarios", type=int, default=24)
    parser.add_argument("--dimensions", default="all")
    parser.add_argument("--model", default="")
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--placement", choices=["user", "system"], default="user")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    report = asyncio.run(run(args))
    args.out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = args.out / f"persona_sensitivity_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "dimensions"},
                     ensure_ascii=False, indent=2))
    print(f"report: {path}")
    return 0 if report.get("status") != "ok" or report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
