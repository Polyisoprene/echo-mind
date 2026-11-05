# GroupMemBench dense retrieval 对照（2026-11-01）

> 目的：验证 dense 检索是否改善 term_ambiguity。
> 依据：GroupMemBench 官方 dense baseline（text-embedding-3-large + cosine）与本机 bge-m3 embedding。

## 1. 现状

BM25 Finance/Technology：

```text
Finance 40.7%, term_ambiguity 0.178
Technology 39.9%, term_ambiguity 0.070
```

term_ambiguity 的核心是不同角色用不同 surface form 指同一概念；BM25 只看词面。

## 2. 对照

固定：

- Finance 数据；
- 消息级索引；
- 官方 passage/QA/judge；
- top10；
- 同一 LLM。

变量：

```text
BM25（当前）
dense bge-m3 + cosine
```

## 3. 方法

- 每条消息 content 做 embedding；
- query 用 `asking_user_id + question`；
- cosine top10；
- 不融合 BM25，先做纯 dense 对照；
- 不改 live。

## 4. 验收

- term_ambiguity 是否提升；
- 总 accuracy 是否不降；
- embedding 成本可接受；
- 只有明确提升才考虑 hybrid 融合。

## 5. 边界

- 官方用 text-embedding-3-large；本机 bge-m3，模型不同；
- 30k 消息 embedding 成本高；
- 先跑 Finance term_ambiguity 45 题，不先全量四域；
- 任何 live 改动需另立 A/B。

## 6. 结果（2026-11-01）

### term_ambiguity 单类

| retriever | n | accuracy |
|---|---:|---:|
| BM25 | 45 | 0.178 |
| dense bge-m3 | 45 | **0.356–0.400** |

### Finance 全量

| 类型 | n | BM25 | dense |
|---|---:|---:|---:|
| multi_hop | 48 | 0.479 | 0.458 |
| knowledge_update | 32 | 0.406 | 0.188 |
| temporal | 45 | 0.222 | 0.089 |
| user_implicit | 15 | 0.400 | 0.333 |
| term_ambiguity | 45 | 0.178 | **0.400** |
| abstention | 29 | 0.931 | 0.862 |
| **总体** | **214** | **0.407** | **0.374** |

结论：

- dense 明显改善 term_ambiguity（0.178→0.400）；
- 但 knowledge_update（0.406→0.188）和 temporal（0.222→0.089）严重退化；
- 全局 dense 不如 BM25；
- 下一步只做 **BM25+dense 的 hybrid/RRF**，不能全局切 dense；
- 该结果只作外部评测，不接 live。

## 7. Hybrid/RRF 设计（下一步）

BM25 与 dense 的互补：

```text
BM25:  knowledge/temporal 更好
dense: term_ambiguity 更好
```

采用公开的 Reciprocal Rank Fusion：

```text
score(doc) = Σ 1/(k + rank_i(doc)), k=60
```

- 不引入手调特征权重；
- 两个 ranker 等权；
- top10；
- 同一 Finance 214 题；
- 判据：总 accuracy > BM25 40.7%，且 knowledge/temporal 不崩。

这是“验证是否能同时保留两类优势”，不是默认上线。

## 8. Hybrid/RRF 结果（2026-11-01）

Finance 214 题：

| 类型 | n | BM25 | dense | hybrid RRF |
|---|---:|---:|---:|---:|
| multi_hop | 48 | 0.479 | 0.458 | **0.521** |
| knowledge_update | 32 | 0.406 | 0.188 | 0.406 |
| temporal | 45 | 0.222 | 0.089 | 0.200 |
| user_implicit | 15 | 0.400 | 0.333 | **0.467** |
| term_ambiguity | 45 | 0.178 | **0.400** | 0.244 |
| abstention | 29 | 0.931 | 0.862 | 0.793 |
| **总体** | **214** | **0.407** | 0.374 | **0.411** |

结论：

- hybrid 只比 BM25 高 1 题（0.411 vs 0.407），不具实际意义；
- term 只恢复到 0.244，未吸收 dense 的 0.400；
- temporal/abstention 下降；
- 不接 live；
- 说明 term_ambiguity 需要 **term/entity normalization**，不是 RRF 融合。
