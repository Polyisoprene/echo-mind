# LongMemEval CoT 生成模型（2026-11-01）

> 目的：验证官方 `cot=true` 生成协议是否能改善 multi-session / temporal-reasoning。
> 依据：LongMemEval 官方 `src/generation/run_generation.py` 的 `cot` 分支（公开实现）。

## 1. 当前基线

```text
500 retrieval: recall@5 0.954, MRR 0.892
500 QA: 417/500 = 83.4%
multi-session: 0.729
temporal-reasoning: 0.789
knowledge-update: 0.833
```

错误形态：

- multi-session 36 错，33 是“数错/漏项”，3 是拒答；
- temporal 28 错，全部是时间/顺序答错；
- knowledge 13 错，主要是旧值/更新值选择。

## 2. 官方 CoT 协议

非 CoT 当前 prompt：

```text
Please answer the question based on the relevant chat history.
... Answer:
```

官方 CoT：

```text
Please answer the question based on the relevant chat history.
Answer the question step by step: first extract all the relevant information,
and then reason over the information to get the answer.
... Answer (step by step):
```

本实现只复刻这段官方 prompt，不改 judge、不改检索、不加新规则。

## 3. 评测设计

- 同一 30 题样本：非 CoT 23/30 vs CoT；
- 若 30 题不退化，再跑 500；
- 分题型看 multi-session / temporal；
- 任何提升必须同时保持 knowledge/abstention 不显著退化；
- judge 使用官方 prompt，不变。

## 4. 边界

- CoT 增加输出 token 与延迟；
- 不是所有题都需要 CoT；
- 不能因为 30 题提升就直接上线；
- 不引入“先验答案”或人工规则。

## 5. 验收

- CoT 30 题 ≥ 非 CoT；
- 500 题分题型报告；
- 只有 multi/temporal 提升且总准确率不降才保留；
- 否则回退，仅保留实验开关。

## 6. 结果（2026-11-01）

### 30 题

```text
non-CoT: 23/30
CoT:     25/30
```

### 500 题全量

| 类型 | n | non-CoT | CoT |
|---|---:|---:|---:|
| knowledge-update | 78 | 0.833 | **0.910** |
| multi-session | 133 | 0.729 | **0.759** |
| single-session-assistant | 56 | 1.000 | 1.000 |
| single-session-preference | 30 | 0.900 | 0.900 |
| single-session-user | 70 | 0.957 | 0.957 |
| temporal-reasoning | 133 | 0.789 | **0.820** |
| abstention | 30 | 0.900 | 0.867 |
| **总体** | **500** | **417 (0.834)** | **431 (0.862)** |

结论：

- CoT 总提升 +14 题（+2.8pp）；
- knowledge-update +6、multi-session +4、temporal +4；
- abstention -1（单题级，30 条样本，不作强结论）；
- 500/500 有效，无错误；
- 只作为评测协议/开关 `--cot`，不直接改 live prompt；
- 若上线，应先做 live A/B，并考虑按题型路由，而不是全局 CoT。
