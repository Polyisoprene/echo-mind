# 外部 Benchmark：LongMemEval-S 检索基线

> 数据集：LongMemEval-S cleaned（500 题，约 53 个 session/题）
> 本报告：100 题分层抽样，session 粒度检索，不含答案生成
> 日期：2026-11-01

## 结论

- **session recall@5 = 44.0%**
- **MRR = 0.276**
- 这是**检索基线**，不是 LongMemEval QA 分数，不能和论文里的端到端准确率直接比较。

## 分层结果

| 题型 | n | session recall@5 | MRR |
|---|---:|---:|---:|
| knowledge-update | 17 | **0.765** | 0.539 |
| multi-session | 17 | 0.647 | 0.522 |
| temporal-reasoning | 16 | 0.500 | 0.189 |
| single-session-preference | 17 | 0.294 | 0.124 |
| single-session-assistant | 17 | 0.235 | 0.144 |
| single-session-user | 16 | 0.188 | 0.123 |
| **总体** | **100** | **0.440** | **0.276** |

## 适配方法

- 每个 session 聚合成一个 `SemanticFact`（role + content，截断 6000 字符）；
- `event_time` 取 session 日期；
- 用 `unified_rank`：BM25(bigram) + dense(bge-small-zh) + recency/order/confidence/lock，RRF(k=60)；
- 关掉中文时间/方向约束（LongMemEval 是英文题面）；
- 证据 session 来自 `answer_session_ids`；top5 命中即 session recall。

## 结果意味着什么

- **知识更新、多会话推理**相对好：0.765 / 0.647；
- **单会话用户/助手/偏好**很差：0.188–0.294；
- 一个明显原因是 **bge-small-zh 是中文模型，LongMemEval 是英文**；跨语言 dense 信号弱，BM25 英文词面又只能覆盖一部分；
- session 级聚合会稀释具体证据，但也比 turn 级（turn recall@5 10%）更接近官方粒度。

## 限制

- 100/500 题，不是全量；
- 只测检索，不测 answer generation / abstention；
- 没有对 LongMemEval 做中文翻译，存在语言域偏移；
- 没有和论文系统的同环境复现，不能直接排名；
- session 文本截断 6000 字符，长 session 可能丢证据。

## 下一步

1. 换多语言 embedding（如 bge-m3）复测，隔离语言因素；
2. 扩到 500 题；
3. 加 answer generation / abstention 指标，才可与论文端到端结果比较；
4. 若继续中文产品，优先补 **GroupMemBench/中文多人群聊** 外部集。
