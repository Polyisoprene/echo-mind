#!/usr/bin/env python3
"""Minimal OpenAI-compatible /v1/embeddings server for a local BGE model.

Designed for the 192.168.3.2 GPU host, reusing its ROCm torch/transformers venv.
No FastAPI/sentence-transformers needed.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModel, AutoTokenizer

LOGGER = logging.getLogger("embedding")
MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL: Any = None
TOKENIZER: Any = None
DEVICE = "cpu"


def _embed(texts: list[str]) -> list[list[float]]:
    inputs = TOKENIZER(
        texts, padding=True, truncation=True, max_length=512, return_tensors="pt"
    )
    inputs = {key: value.to(DEVICE) for key, value in inputs.items()}
    with torch.no_grad():
        hidden = MODEL(**inputs).last_hidden_state
    mask = inputs["attention_mask"].unsqueeze(-1).float()
    pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
    pooled = torch.nn.functional.normalize(pooled, dim=-1)
    return pooled.cpu().tolist()


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/health", "/v1/health"):
            self._json(200, {"status": "ok", "model": MODEL_NAME, "device": DEVICE})
        elif self.path in ("/v1/models", "/models"):
            self._json(200, {"object": "list", "data": [
                {"id": MODEL_NAME, "object": "model", "owned_by": "local"}
            ]})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/v1/embeddings", "/embeddings"):
            self._json(404, {"error": {"message": "not found"}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            raw = body.get("input", "")
            texts = [raw] if isinstance(raw, str) else [str(x) for x in raw]
            if not texts:
                self._json(400, {"error": {"message": "input is empty"}})
                return
            vectors = _embed(texts)
            self._json(200, {
                "object": "list",
                "model": str(body.get("model") or MODEL_NAME),
                "data": [
                    {"object": "embedding", "index": i, "embedding": vec}
                    for i, vec in enumerate(vectors)
                ],
                "usage": {"prompt_tokens": 0, "total_tokens": 0},
            })
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("embedding failed")
            self._json(500, {"error": {"message": str(exc)}})

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), fmt % args)


def main() -> int:
    global MODEL, TOKENIZER, DEVICE, MODEL_NAME
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--host", default="0.0.0.0")  # noqa: S104 - LAN service
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--revision", default="main")
    args = parser.parse_args()
    MODEL_NAME, DEVICE = args.model, args.device
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    LOGGER.info("loading %s on %s", MODEL_NAME, DEVICE)
    kwargs = {} if Path(MODEL_NAME).exists() else {"revision": args.revision}
    TOKENIZER = AutoTokenizer.from_pretrained(MODEL_NAME, **kwargs)
    MODEL = AutoModel.from_pretrained(MODEL_NAME, **kwargs).to(DEVICE).eval()
    LOGGER.info("ready on %s:%s", args.host, args.port)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
