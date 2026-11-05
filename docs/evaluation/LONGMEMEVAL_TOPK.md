# LongMemEval top-k 上下文对照（2026-11-01）

> 目的：验证 top-5 是否限制 multi-session / temporal 的多证据合并。
> 依据：LongMemEval 官方 generation 的 `--topk_context` 参数；这是官方支持的上下文预算变量，不是新算法。

## 1. 背景

```text
500 retrieval: recall@5 0.954
500 QA (top5): 417/500 = 83.4%
multi-session: 0.729
temporal: 0.789
```

multi-session 的错误多是“漏项/数错”，可能因为 top5 没包含所有证据 session。

## 2. 对照设计

固定：

- 同一 30 题样本；
- 同一 retriever / ranker；
- 同一非 CoT 生成 prompt；
- 同一 judge。

变量：

```text
topk = 5  （现有）
topk = 10 （多给 5 个 session）
```

## 3. 判据

- multi-session / temporal 是否提升；
- 总准确率不降；
- 上下文长度/延迟成本可接受；
- 只有明确收益才考虑扩大 live 检索上下文。

## 4. 边界

- 30 题样本小，不能直接定论；
- top10 可能引入更多干扰；
- 不改 retrieval 排序，只改进入生成器的上下文数量；
- 不在 live 直接改 TOPK。

## 5. 结果（2026-11-01）

30 题分层样本：

```text
top5:  23/30
top10: 26/30
```

500 题全量（top10）：

| 类型 | n | accuracy |
|---|---:|---:|
| knowledge-update | 78 | 0.923 |
| multi-session | 133 | 0.744 |
| single-session-assistant | 56 | 1.000 |
| single-session-preference | 30 | 0.733 |
| single-session-user | 70 | 0.971 |
| temporal-reasoning | 133 | 0.850 |
| abstention | 30 | 0.867 |
| **总体** | **500** | **430/500 = 0.860** |

对照：

```text
top5 non-CoT: 417/500 = 0.834
top5 CoT:     431/500 = 0.862
top10 non-CoT:430/500 = 0.860
```

注意：

- top10 提升 knowledge-update/temporal，但 preference 从 0.900 降到 0.733；
- 总提升来自多类抵消，不是全面变好；
- 不改 live top-k；只保留评测开关；
- 500 分片曾因选择逻辑只覆盖 388 题，缺 112 已补齐；新增 `--full-order` 供后续稳定分片。
