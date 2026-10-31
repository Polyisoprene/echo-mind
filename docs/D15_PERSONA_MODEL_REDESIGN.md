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

## 本轮不做

- 不改线上人格；
- 不引入 embedding 依赖；
- 等实验方案与评测集确认后再实施。
