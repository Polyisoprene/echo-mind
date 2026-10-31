"""D15: the embedding client speaks the OpenAI /embeddings shape."""

from __future__ import annotations

import json

import httpx
import pytest

from echomind.adapters.llm.embedding_client import OpenAiEmbeddingGateway
from echomind.core.config import EmbeddingConfig


def _handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["model"] == "embed-small"
    assert body["input"] == ["a", "b"]
    return httpx.Response(200, json={"data": [
        {"index": 1, "embedding": [3.0, 4.0]},
        {"index": 0, "embedding": [1.0, 2.0]},
    ]})


@pytest.mark.asyncio
async def test_embed_batches_and_orders_by_index() -> None:
    cfg = EmbeddingConfig(model="embed-small", base_url="http://embed/v1", api_key="k")
    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        gateway = OpenAiEmbeddingGateway(cfg, client=client)
        vectors = await gateway.embed(("a", "b"))
    assert vectors == ((1.0, 2.0), (3.0, 4.0))


def test_disabled_config_is_rejected() -> None:
    with pytest.raises(ValueError):
        OpenAiEmbeddingGateway(EmbeddingConfig())
