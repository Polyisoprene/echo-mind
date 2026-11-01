# GroupMemBench changed-decision 候选集（2026-11-01）

> 背景：decision-only 太大（Finance 19,920 条），无法解决旧值/新值。
> 数据字段：`decision_type`（original/changed）与 `decision_change_metadata`。
> Finance changed = 66，Technology changed = 74。

## 1. 对照

固定：

- metadata-aware BM25；
- top10；
- 官方 prompt；
- 同一 LLM。

变量：

```text
all messages
change-only：只检索 decision_type=changed / 有 decision_change_metadata 的消息
```

## 2. 判据

- Finance/Technology KU 是否提升；
- changed 候选是否覆盖金标；
- 不通过就停；
- 不接 live。

## 3. 边界

- 只适用于有 changed-decision 标注的 GroupMemBench；
- 候选只有 66/74 条，可能过窄；
- 不把 changed 当权重，而是候选集过滤。

## 4. 结果（2026-11-01）

| 域 | n | 全消息 | change-only |
|---|---:|---:|---:|
| Finance | 32 | 0.469 | **0.688** |
| Technology | 36 | 0.472 | **0.833** |

结论：

- changed-decision 候选集显著提升 KU；
- Finance +21.9pp，Technology +36.1pp；
- 说明 KU 的 gold 主要是“已变更的决策”，普通 BM25 被 old/original 消息淹没；
- 只对 knowledge_update 有效，不能全题型；
- 这是 benchmark/typed routing，不是 live 通用检索；
- 不接 live：live 没有 `decision_type=changed` 字段。
