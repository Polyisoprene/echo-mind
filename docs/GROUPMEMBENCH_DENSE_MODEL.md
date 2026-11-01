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
