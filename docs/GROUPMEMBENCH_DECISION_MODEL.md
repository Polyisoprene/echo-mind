# GroupMemBench decision-aware retrieval（2026-11-01）

> 背景：knowledge_update 的 gold 常是团队 decision，而普通 BM25 top10 会混入讨论/噪声消息。
> 数据字段：`is_decision_point`、`decision_type`、`decision_label.decision_category`、`decision_change_metadata`。

## 1. 对照

固定：

- metadata-aware BM25；
- top10；
- 官方 prompt；
- 同一 LLM。

变量：

```text
all messages
decision-only：只在 is_decision_point=true 的消息中检索
```

## 2. 判据

- Finance/Technology knowledge_update 是否提升；
- 是否漏掉非 decision 但含最终值的消息；
- 不改 live；
- 先 KU，不跑全题型。

## 3. 边界

- decision-only 是数据条件，不是通用算法；
- 只适用于有显式 decision 标注的 GroupMemBench；
- 不把 decision 当权重，而是候选集过滤；
- 结果不通过就停。

## 4. 结果（2026-11-01）

| 域 | n | 全消息 | decision-only |
|---|---:|---:|---:|
| Finance | 32 | **0.469** | 0.406 |
| Technology | 36 | 0.472 | 0.472 |

结论：

- decision-only 不改善 Finance，Technology 持平；
- 说明 KU 不是“只缺 decision 候选”；
- 不采用；
- 继续做 candidate set 过滤/排序已经没有证据支持，下一步应检查 gold 与 top10 的语义对应，而不是再换候选集。
