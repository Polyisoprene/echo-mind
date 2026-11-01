# LongMemEval 检索诊断模型（2026-11-01）

> 依据：LongMemEval ICLR 2025 的 retrieval 设计（session decomposition、fact-augmented key expansion、time-aware query expansion）。
> 状态：诊断阶段，不直接改 live ranker。

## 1. 已知

500 题 session retrieval：

```text
recall@5 = 0.528
MRR = 0.375
```

30 题 end-to-end QA：

```text
10/30
```

oracle gold sessions：

```text
24/25
```

所以 reading 可用，主要损失在 retrieval/context selection。

## 2. 分题型线索

500 题：

| 题型 | recall@5 |
|---|---:|
| knowledge-update | 0.731 |
| multi-session | 0.624 |
| temporal-reasoning | 0.564 |
| single-session-user | 0.343 |
| single-session-assistant | 0.339 |
| single-session-preference | 0.200 |

但 30 题 end-to-end 里：

```text
knowledge-update 0/5
temporal-reasoning 0/4
```

与 500 题的高 recall 不一致，说明小样本或 **top-5 选择**有问题；需要看实际 top-5。

## 3. 诊断输出

给 QA 行增加：

```text
memory_sessions: top-5 的 session id
gold_sessions: answer_session_ids
```

然后逐题判断：

- gold 在 top5 但 reading 没用到；
- gold 不在 top5（检索丢失）；
- gold 在 top5 但被截断/排序靠后；
- gold session 本身不含答案（数据问题）。

## 4. 候选方法（只选有公开依据的）

### 4.1 Time-aware query expansion

LongMemEval 论文的公开优化之一：

- 用问题日期与时间表达扩展 query；
- 目标：temporal-reasoning / knowledge-update 的 session 定位。

### 4.2 Fact-augmented key expansion

论文的另一项：

- 在索引时把 user fact/key 扩展进 session key；
- 目标：单会话 user/assistant 的事实检索。

### 4.3 Session date / recency

现有 ranker 已有 recency，但需要检查：

- 是否把旧 session 排到新 session 前；
- knowledge-update 是否选到最新值。

## 5. 原则

- 先看 30 题 top-5，不先改算法；
- 任何 query expansion 必须 shadow/离线对比 500 retrieval；
- 不引入手调权重；
- 不把 oracle reading 当作 retrieval 结果；
- 不在同一轮同时改 retrieval 和 prompt。

## 6. 验收

- 30 题 top-5 诊断表；
- 明确失败类型占比；
- 选择一种有论文依据的改动；
- 500 retrieval 重新评估；
- 只有 recall/MRR 提升且 QA 不退化才保留。

## 7. 30 题 top-5 诊断（2026-11-01）

`longmemeval-qa-diag-30-2026-11-01.json`：

| 类型 | n | top5 命中 gold | end-to-end 正确 |
|---|---:|---:|---:|
| knowledge-update | 5 | 2 | 0 |
| multi-session | 4 | 3 | 1 |
| single-session-assistant | 4 | 2 | 2 |
| single-session-preference | 4 | 1 | 2 |
| single-session-user | 9 | 3 | 6 |
| temporal-reasoning | 4 | 2 | 0 |
| **总** | **30** | **13** | **11** |

结论：

- 检索确实丢证据（17/30 没命中）；
- 但 gold 在 top5 的 knowledge-update/temporal 仍答错，说明上下文顺序/日期也重要；
- 官方 generation 会把 retrieved sessions 按 session date 排序；我们之前保留 ranker 顺序，已改为按日期排序；
- 下一步先验证日期排序，再决定是否做 time-aware query expansion / fact-augmented key。

## 8. 日期排序对照（2026-11-01）

改动：

- 只把 top-5 context 按 session date 升序排列（官方 generation 的做法）；
- 不改检索、不改 prompt。

结果：

```text
before (ranker order): 10/30
after  (date order):   10/30
```

分题型：

| 类型 | n | accuracy |
|---|---:|---:|
| knowledge-update | 5 | 0.0 |
| multi-session | 4 | 0.25 |
| single-session-assistant | 4 | 0.5 |
| single-session-preference | 4 | 0.25 |
| single-session-user | 9 | 0.667 |
| temporal-reasoning | 4 | 0.0 |
| abstention | 5 | 1.0 |
| **总** | **30** | **10/30** |

结论：

- 日期排序不是瓶颈；
- knowledge-update 仍 0/5，且 3/5 的 gold 不在 top5；
- temporal 0/4，2/4 gold 在 top5；
- 下一步应做 **time-aware query expansion / 更新事实检索**，并先离线对比 500 retrieval，不直接改 ranker。
