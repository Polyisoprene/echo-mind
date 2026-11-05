# LongMemEval 融合审计（2026-11-01）

## 1. 发现

同一批 500 题、同一 session 文本、同一 hit 计算：

| retriever | recall@5 | MRR |
|---|---:|---:|
| hybrid RRF（当前） | 0.528 | 0.375 |
| BM25-only | **0.947** | **0.868** |

这个差距不是抽样噪声；LongMemEval 论文和 GroupMemBench 都报告 BM25 是强基线，因此先怀疑 **RRF 融合被弱 ranker 稀释**，而不是“没有语义检索”。

## 2. 为什么不能直接改 live

当前 `unified_rank` 等权融合：

```text
bm25
dense
recency
order
relations
confidence
lock
trait
```

在 LongMemEval 上，recency/order/confidence/lock 可能对英文 session 不是有效信号；等权 RRF 会让 BM25 的 top 结果被挤掉。

但直接删 ranker 会影响线上中文群聊，不能拍脑袋。先做消融。

## 3. 消融设计

固定：

- 500 题；
- session 粒度；
- 同一 BM25 实现；
- 同一 top5 hit。

变体：

```text
bm25
bm25 + recency
bm25 + order
bm25 + confidence + lock
bm25 + all non-dense
```

不跑 dense，避免 embedding 成本；先判断非 dense ranker 是否伤害。

## 4. 判据

- 若 BM25-only 明显最好 → 当前 RRF 的等权/弱 ranker 是问题；
- 若某单项不降或提升 → 保留；
- 任何 live 改动必须再做中文群聊回归与 500 题复测；
- 不引入手调权重，优先“移除无效 ranker”或“按验证集选择 ranker 子集”。

## 5. 外部依据

- LongMemEval 论文将 BM25 作为 retrieval baseline；
- GroupMemBench 报告简单 BM25 可匹配或超过多数 agent memory system；
- 这不是“用 BM25 替代一切”，而是先确认融合是否在伤害。

## 6. 消融结果（修前）

同 500 题、BM25 文本、top5：

| 配置 | recall@5 | MRR |
|---|---:|---:|
| BM25 only | 0.940 | 0.868 |
| + recency | 0.626 | 0.426 |
| + order | 0.702 | 0.460 |
| + confidence + lock | 0.448 | 0.315 |
| + all non-dense | 0.336 | 0.237 |

原因：

- confidence 全为常数、lock 全为 false；
- RRF 仍给它们 1..N 的伪排名；
- 这些伪排名把 BM25 的 top 结果挤掉。

## 7. 尝试修复与回滚

尝试：

```text
无信息 ranker（所有分数相同）不进 RRF；
当没有任何 informative ranker 时，回退到原始 ranker 集合。
```

LongMemEval 消融改善：

```text
bm25 + recency = 0.940
bm25 + confidence/lock = 0.940
bm25 + order = 0.702（order 仍伤）
```

但内部 70 条评测：

```text
paraphrase 1/10
overall 61/70
```

原因：paraphrase 依赖旧 tie-break 的顺序；全局跳过常数 ranker 改变了 tie 语义。

处理：

- **生产代码回滚**；
- 只保留诊断、消融、`--disable` 评测开关；
- 不把 61/70 的改动留在线；
- 下一步如果要修，必须做成**可验证的 reranker/feature flag**，并用 70+500 双重验收。

## 8. 结论

- 当前 hybrid 0.528 明显低于 BM25 0.947；
- 但不能直接全局删 ranker；
- 需要设计一个“只在有 informative 信号时启用某 ranker”的策略，且不改变无信息场景的旧顺序；
- 在该策略通过 70/70 与 500 题前，不改 live。

**当前生产 ranker 未改变。**

## 9. 最小修复（已上线，2026-11-01）

只改一处：

```text
confidence / lock 若所有 fact 分数相同 → 不进入 RRF
```

不改 bm25 / dense / recency / order / relations / trait，不改 fallback 顺序。

内部评测：

```text
paraphrase 10/10
overall 70/70
```

LongMemEval 500 消融：

| 配置 | recall@5 | MRR |
|---|---:|---:|
| bm25 only | 0.940 | 0.868 |
| + confidence + lock（过滤后） | **0.940** | **0.868** |
| + recency | 0.626 | 0.426 |
| + order | 0.702 | 0.460 |

结论：

- 常数 confidence/lock 不再稀释 BM25；
- recency/order 仍会降分，但不在本轮改；
- hybrid 500 正在远端验证，结果未出前不宣称整体提升。

**回归测试**：`test_constant_confidence_and_lock_do_not_dilute_bm25`。

**全门禁：392 passed / 93%，fusion 70/70。**

## 10. Conditional ranker（已验证，2026-11-01）

在最小 confidence/lock 修复上，再加一个条件：

```text
recency 只在 query 含时间 cue 时进入 RRF
order   只在 query 含方向 cue 时进入 RRF
```

依据：

- 这两个 ranker 是中文时间/方向专用；
- LongMemEval 英文 query 没有这些 cue，旧实现仍把它们当全局 ranker，造成稀释；
- 不引入新权重，只按已有 `_temporal_mode/_DIRECTION` cue 决定是否启用。

内部评测：

```text
paraphrase 10/10
overall 70/70
mrr 0.988
```

LongMemEval 500 BM25 消融：

| 配置 | recall@5 | MRR |
|---|---:|---:|
| BM25 only | 0.940 | 0.868 |
| + recency（无 cue，跳过） | 0.940 | 0.868 |
| + order（无 cue，跳过） | 0.940 | 0.868 |
| + all non-dense | 0.940 | 0.868 |

结论：

- conditional 后，非 dense 专用 ranker 不再污染英文 benchmark；
- claim_rank 仍显式 `force_recency=True`，保持“近期优先”；
- hybrid 500（dense 仍参与）在远端验证；结果未出前不宣称整体提升。

## 11. 最终 500 结果（2026-11-01）

在 confidence/lock 常数修复 + recency/order 条件启用的最终 ranker 上：

| 类型 | n | recall@5 | MRR |
|---|---:|---:|---:|
| knowledge-update | 78 | 1.000 | 0.965 |
| multi-session | 133 | 0.947 | 0.914 |
| single-session-assistant | 56 | 1.000 | 0.991 |
| single-session-preference | 30 | 0.900 | 0.700 |
| single-session-user | 70 | 0.914 | 0.818 |
| temporal-reasoning | 133 | 0.947 | 0.867 |
| **总体** | **500** | **0.954** | **0.892** |

对照：

```text
旧 hybrid: 0.528 / 0.375
BM25-only: 0.940 / 0.868
最终 hybrid: 0.954 / 0.892
```

结论：

- conditional 修复后，hybrid 不再被中文专用/常数 ranker 稀释；
- hybrid 超过 BM25-only；
- 这是 500 题 session retrieval，不是 QA 端到端；
- 30 题 QA 正在用最终 ranker 重跑，结果未出。
