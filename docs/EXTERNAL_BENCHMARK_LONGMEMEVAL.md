# 外部 Benchmark：LongMemEval-S 检索基线

> 数据集：LongMemEval-S cleaned（500 题，约 53 个 session/题）
> 本报告：100 题分层抽样 + 500 题全量，session 粒度检索
> 500 题运行：2026-11-01，远端 192.168.3.2
> 日期：2026-11-01
> Embedding：bge-small-zh → bge-m3 对照

## 结论

- 100 题 bge-small：session recall@5 **44.0%**，MRR **0.276**
- 100 题 bge-m3：session recall@5 **51.0%**，MRR **0.315**
- **500 题 bge-m3：session recall@5 52.8%，MRR 0.375**
- 这是**检索基线**，不是 LongMemEval QA 分数，不能和论文里的端到端准确率直接比较。

## 分层结果

| 题型 | n | bge-small recall@5 | bge-m3 recall@5 | bge-m3 MRR |
|---|---:|---:|---:|---:|
| knowledge-update | 17 | 0.765 | **0.824** | 0.606 |
| multi-session | 17 | 0.647 | **0.824** | 0.576 |
| temporal-reasoning | 16 | 0.500 | 0.500 | 0.231 |
| single-session-preference | 17 | 0.294 | 0.294 | 0.168 |
| single-session-assistant | 17 | 0.235 | 0.294 | 0.138 |
| single-session-user | 16 | 0.188 | 0.312 | 0.159 |
| **总体（100）** | **100** | **0.440** | **0.510** | **0.315** |

### 500 题全量（bge-m3，session）

| 题型 | n | recall@5 | MRR |
|---|---:|---:|---:|
| knowledge-update | 78 | 0.731 | 0.558 |
| multi-session | 133 | 0.624 | 0.441 |
| temporal-reasoning | 133 | 0.564 | 0.395 |
| single-session-user | 70 | 0.343 | 0.218 |
| single-session-assistant | 56 | 0.339 | 0.227 |
| single-session-preference | 30 | 0.200 | 0.158 |
| **总体** | **500** | **0.528** | **0.375** |

abstention 子集（30 条）：recall@5 **0.567**，MRR **0.409**。

## 适配方法

- 每个 session 聚合成一个 `SemanticFact`（role + content，截断 6000 字符）；
- `event_time` 取 session 日期；
- 用 `unified_rank`：BM25(bigram) + dense(bge-small-zh) + recency/order/confidence/lock，RRF(k=60)；
- 关掉中文时间/方向约束（LongMemEval 是英文题面）；
- 证据 session 来自 `answer_session_ids`；top5 命中即 session recall。

## 结果意味着什么

- bge-m3 把 knowledge-update / multi-session 推到 0.824 / 0.824；
- **单会话用户/助手/偏好**仍差：0.294–0.312；
- bge-m3 证明语言因素占一部分，但不是全部：单会话检索仍是主要短板；
- session 级聚合会稀释具体证据，但也比 turn 级（turn recall@5 10%）更接近官方粒度。

## 限制

- 500 题只用远端跑 retrieval；QA/abstention 仅 30 题小样本；
- 500 题结果与 100 题不是严格同一抽样，不能做显著性结论；
- 只测检索，不测 answer generation / abstention 全量；
- 没有对 LongMemEval 做中文翻译，存在语言域偏移；
- 没有和论文系统的同环境复现，不能直接排名；
- bge-m3 批量 32 会 OOM，评测使用 batch=4；
- session 文本截断 6000 字符，长 session 可能丢证据。

## 下一步

1. ✅ 已扩到 500 题（52.8% / 0.375），确认 100 题不是偶然；
2. 500 题 QA 全量仍未跑；30 题 QA 小样本 11/30，abstention 5/5；
2. 补单会话事实检索（当前 0.294–0.312）；
3. 加 answer generation / abstention 指标，才可与论文端到端结果比较；
4. 若继续中文产品，优先补 **GroupMemBench/中文多人群聊** 外部集。
