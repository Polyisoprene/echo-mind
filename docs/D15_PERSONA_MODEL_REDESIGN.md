# D15 人格模型重设计（设计，未改线上）

## 现状

- 7 维向量：warmth/tsundere/playfulness/possessiveness/confidence/guile/defiance；
- 已修正“HEXACO”命名，不再宣称六轴映射；
- `persona_traits` 由回合巩固写入，带 source/chat_key，但 prompt 仍以固定 rubric 示例为主；
- 记忆检索是关键词/时间/关系加权，**没有语义向量检索**。

## 问题

1. 固定 rubric 示例容易让她“照着例句演”，而不是从经历长出习惯；
2. 无语义检索时，同义/改写过的记忆召回率低；
3. 特质缺少“证据强度/反证”的显式建模，长期可能漂移。

## 设计

### A. 可学习特质

- 每条 `PersonaTrait` 增加 `evidence_count`、`last_evidence_ms`、`contradiction_count`；
- 巩固时写证据，衰减按 12h 未强化（现有）保留；
- prompt 只放 **top-k 有证据的特质**，固定 rubric 示例降级为“语气参考”，不进入身份陈述；
- 离线评测：同一场景在“固定示例 vs 证据特质”下的复读率与一致性。

### B. 语义检索

- 事实/往事写入时生成 embedding，存 `memory_vectors`；
- 检索改成 hybrid：BM25/关键词 + 向量 cosine + 关系/来源加权；
- 硬门在检索后、渲染前仍然生效（private/secret 不因相似度放行）；
- 评测：Recall@5、MRR、越权率、跨场合一致性。

### C. 分阶段

1. 先离线建索引与评测集，不改线上；
2. 灰度 10% 会话，比较召回与人格一致性；
3. 达标再全量。

## 进展（2026-10-31）

- **Step 1 已落地（存储层）**：`persona_traits` 增加 `evidence_count`、`contradiction_count`、`last_evidence_ms`；
- 每次巩固强化 `evidence_count +1`、刷新 `last_evidence_ms`；
- prompt 仍按原逻辑读取，未改变线上人格；
- 测试：同一特质强化两次 → `evidence_count=2`。

## 进展（2026-10-31）

- **Step 1（存储）**：`persona_traits` 增加 `evidence_count`、`contradiction_count`、`last_evidence_ms`；每次强化 +1；测试通过。
- **Step 2（prompt 筛选）**：`synthesize_live_persona_directive(..., min_evidence=0, max_traits=6)`，默认 0 保持现状；离线测试证明 `min_evidence=2` 只保留高证据特质。
- **现网分布**：9 条特质全部 `evidence=1`，现在开 `min_evidence=2` 会把 9 条全过滤掉，所以**默认仍为 0**，等证据累积。

## API embedding 管线（已实现，默认关闭）

- 配置（`data/config.json` 的 `api` 段）：
  ```json
  "embeddingModel": "your-embedding-model",
  "embeddingBaseUrl": "https://your-endpoint/v1",
  "embeddingApiKey": "sk-...",
  "embeddingDimensions": 0
  ```
- 客户端：`adapters/llm/embedding_client.py`，OpenAI `/embeddings` 形状；
- 存储：`memory_vectors` 表 + `SqliteMemoryVectorStore`；
- 检索：`mind/semantic_retrieval.py` 余弦 rerank；
- 回填：`scripts/backfill_memory_vectors.py --apply`；
- 测试：mock `/embeddings`、向量 roundtrip、余弦排序；
- **默认关闭**：当前三个 provider 的 `/embeddings` 都返回 404/不支持，没有可用 endpoint，所以线上行为不变。

## 接入状态

- 已接入 frame：`build_cognitive_frame` 在 `_semantic` 存在时调用 `SemanticMemoryRetriever`，否则走原关键词选择；
- 覆盖不足或 API 失败时自动回退关键词；
- `main.py` 仅在 `cfg.embedding.enabled` 时构造 retriever；
- 默认关闭，当前线上行为不变。

## 下一步（需 endpoint）

1. 在 `api.embedding*` 填入可用 endpoint/model/key；
2. 跑 `backfill_memory_vectors.py --apply` 建索引；
3. 用 `eval_memory_retrieval.py` 的同义集对比 recall@5；
4. 达标后把 `rerank_facts` 接入 frame 检索（硬门仍在渲染前）。

## 本轮不做

- 不改线上人格；
- 不引入 embedding 依赖；
- 等实验方案与评测集确认后再实施。
