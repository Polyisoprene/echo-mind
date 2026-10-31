"""D15: end-to-end mock pipeline — embed, store, rerank paraphrase queries."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from echomind.adapters.llm.embedding_client import OpenAiEmbeddingGateway
from echomind.adapters.storage.memory_vector_repo import SqliteMemoryVectorStore
from echomind.core.bootstrap import EchoMindContainer
from echomind.core.config import EmbeddingConfig
from echomind.domain.models import SemanticFact
from echomind.mind.semantic_retrieval import rerank_facts

TOPICS: tuple[tuple[str, ...], ...] = (
    ("猫", "猫粮", "胃口"),
    ("工作", "岗位", "顺利"),
    ("熬夜", "睡", "凌晨"),
    ("爬山", "假期", "出门"),
    ("美式", "咖啡"),
    ("截止", "材料", "交"),
    ("休养", "身体"),
    ("电影", "催泪", "哭"),
    ("打雷", "害怕", "天气"),
    ("预算", "钱", "花"),
)

PAIRS = (
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

DISTRACTORS = ("群规周五发图", "B 站热门", "排位连胜", "今天降温", "中午吃面")


def _topic(text: str) -> int:
    for index, words in enumerate(TOPICS):
        if any(word in text for word in words):
            return index
    return len(TOPICS)


def _handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    data = []
    for index, text in enumerate(body["input"]):
        vector = [0.0] * (len(TOPICS) + 1)
        vector[_topic(text)] = 1.0
        data.append({"index": index, "embedding": vector})
    return httpx.Response(200, json={"data": data})


@pytest.mark.asyncio
async def test_mock_semantic_pipeline_recall(tmp_path: Path) -> None:
    container = await EchoMindContainer.create(db_path=tmp_path / "sem.db")
    facts = tuple(
        SemanticFact(fact_id=index, chat_key="g", subject=f"s{index}", fact_text=text)
        for index, text in enumerate(
            [text for _q, text in PAIRS] + list(DISTRACTORS), start=1
        )
    )
    cfg = EmbeddingConfig(model="mock", base_url="http://mock/v1")
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    gateway = OpenAiEmbeddingGateway(cfg, client=client)
    embeddings = await gateway.embed(tuple(f.fact_text for f in facts))

    store = SqliteMemoryVectorStore(container.db)
    for fact, vector in zip(facts, embeddings, strict=True):
        await store.upsert(memory_kind="semantic", memory_id=fact.fact_id,
                           model="mock", vector=vector)

    vectors = await store.get("semantic", tuple(f.fact_id for f in facts), "mock")
    hits = 0
    for query, target in PAIRS:
        ranked = await rerank_facts(facts, query, gateway, vectors, limit=1)
        hits += int(ranked[0].fact_text == target)
    await client.aclose()
    assert hits == len(PAIRS)
