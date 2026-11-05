# GroupMemBench knowledge_update 对照（2026-11-01）

> 目标：定位跨域 knowledge_update 短板（0.235–0.472）。
> 变量：只改变 top-10 context 的时间顺序，不改检索、权重、prompt。

## 1. 现状

| 域 | knowledge_update |
|---|---:|
| Finance | 0.469 |
| Technology | 0.472 |
| Healthcare | 0.235 |
| Manufacturing | 0.273 |

问题通常是“旧值 vs 新值”：检索到了旧消息，生成器选了旧值。

## 2. 对照

固定：

- metadata-aware BM25；
- top10；
- 官方 prompt；
- 同一 LLM/judge。

变量：

```text
rank order：按 BM25 排名呈现
date order：按消息 timestamp 升序呈现
```

依据：GroupMemBench passage 本来携带 timestamp；把上下文按时间排列是呈现层变量，不改变候选集。

## 3. 判据

- knowledge_update 是否提升；
- 总 accuracy 是否不降；
- 只影响呈现顺序，若无效就回退；
- 不引入日期权重。

## 4. 边界

- 只测 knowledge_update；
- 先 Finance+Technology，再考虑四域；
- 不改 live。

## 5. 结果（2026-11-01）

| 域 | BM25 排名顺序 | 按 timestamp 排序 |
|---|---:|---:|
| Finance | **0.469** | 0.375 |
| Technology | **0.472** | 0.444 |

结论：

- 只改 context 时间顺序会让 knowledge_update 变差；
- 不能把“按日期排序”当修复；
- 不接 live；
- 下一步需要看具体检索证据（旧值/新值是否都进了 top10、哪个被模型选中），而不是继续调顺序。
