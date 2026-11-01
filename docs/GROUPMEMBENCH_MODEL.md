# GroupMemBench 适配模型（2026-11-01）

> 依据：GroupMemBench 官方仓库（UCSB-NLP-Chang/GroupMemBench）与论文。
> 目的：在多人群聊外部集上验证“消息级 BM25 + 官方 QA/judge”基线。
> 状态：Finance 单域适配；不改 live。

## 1. 数据

`data/external/GroupMemBench`（浅克隆）：

- Finance 214 题：
  - multi_hop 48
  - knowledge_update 32
  - temporal 45
  - user_implicit 15
  - term_ambiguity 45
  - abstention 29
- 每条消息含 `author/role/_channel/timestamp/reply_to/phase_name/topic`；
- 官方 BM25 只索引 `content`，metadata 在拼 passage 时加入。

## 2. 适配

```text
conversation JSON
  → 每个 channel 的消息按时间展开
  → message fact（content-only BM25）
  → query = asking_user_id + question
  → top-10 message
  → 官方 passage 格式
  → 官方 agent prompt（Final: <answer>）
  → 官方 judge prompt（Final: Correct/Incorrect）
```

不使用 embedding，先复现官方 BM25 基线；这是 CPU/确定性索引 + LLM QA。

## 3. 验收

- Finance 214 题全跑；
- 分题型 accuracy；
- 与官方 README 的 BM25 结果对照时说明模型/judge 不同；
- 不改 live 检索/人格；
- 输出 raw JSONL + summary JSON。

## 4. 边界

- 官方 QA/judge 使用 gpt-5；本机使用可用 LLM，不能直接排名；
- Finance 是 solvability-filtered，Healthcare/Manufacturing 未过滤；
- 只跑 Finance 先验证适配，不一次跑四域；
- 任何 live 改动必须另立 shadow/A-B。

## 5. Finance 首轮结果（2026-11-01）

消息级 BM25 + 官方 QA/judge prompt：

| 类型 | n | accuracy |
|---|---:|---:|
| multi_hop | 48 | 0.479 |
| knowledge_update | 32 | 0.406 |
| temporal | 45 | 0.222 |
| user_implicit | 15 | 0.400 |
| term_ambiguity | 45 | 0.178 |
| abstention | 29 | 0.931 |
| **总体** | **214** | **87/214 = 0.407** |

解读：

- abstention 0.931 是强项；
- term_ambiguity 0.178、temporal 0.222、user_implicit 0.400 是明显短板；
- 官方最强系统平均 46.0%（gpt-5 judge），BM25 是强基线；本机 LLM/judge 不同，不能直接排名；
- 该结果只作 Finance 适配基线，尚未接 live；
- 下一步优先 term_ambiguity/temporal，而不是继续加 top-k。

## 6. Technology 复测（2026-11-01）

同一消息级 BM25 + 官方 prompt：

| 类型 | n | accuracy |
|---|---:|---:|
| multi_hop | 41 | 0.341 |
| knowledge_update | 36 | 0.417 |
| temporal | 37 | 0.378 |
| user_implicit | 28 | 0.393 |
| term_ambiguity | 43 | 0.070 |
| abstention | 28 | 1.000 |
| **总体** | **213** | **85/213 = 0.399** |

对照 Finance：

```text
Finance 0.407
Technology 0.399
```

结论：

- 两个 solvability-filtered 域都约 40%，适配器不是 Finance 偶然；
- term_ambiguity 在 Technology 只有 0.070，是最稳定的系统性短板；
- abstention 1.000，说明拒答不是问题；
- 下一步应做 term/entity normalization 或 dense retrieval，而不是继续加 top-k。

## 7. metadata-aware BM25（2026-11-01）

把消息的 `author/role/_channel/phase_name/topic` 加入检索文本，passage 仍保留原格式：

| 域 | n | content-only BM25 | metadata-aware |
|---|---:|---:|---:|
| Finance | 214 | 0.407 | **0.486** |
| Technology | 213 | 0.399 | **0.526** |

Finance 分题型：

| 类型 | n | content BM25 | metadata |
|---|---:|---:|---:|
| multi_hop | 48 | 0.479 | **0.583** |
| knowledge_update | 32 | 0.406 | **0.469** |
| temporal | 45 | 0.222 | **0.333** |
| user_implicit | 15 | 0.400 | **0.667** |
| term_ambiguity | 45 | 0.178 | **0.267** |
| abstention | 29 | 0.931 | 0.828 |

Technology 分题型：

```text
multi_hop 0.659, knowledge 0.472, temporal 0.324,
user_implicit 0.571, term 0.326, abstention 0.929
```

结论：

- metadata 索引在 Finance +7.9pp、Technology +12.7pp；
- term_ambiguity 从 0.07–0.18 提升到 0.27–0.33，但仍低于 dense 0.40；
- Finance abstention 有下降，不能忽略；
- 这是**外部适配条件**：GroupMemBench 提供 role/channel/phase/topic metadata，官方 content-only BM25 不使用这些；因此不能与官方排名直接比较；
- 不接 live；live 记忆没有这些字段，不能假装等价。

## 8. 四域 metadata-aware 矩阵（2026-11-01）

同一 metadata-aware BM25 + 官方 prompt：

| 域 | n | accuracy | 数据性质 |
|---|---:|---:|---|
| Finance | 214 | 0.486 | solvability-filtered |
| Technology | 213 | 0.526 | solvability-filtered |
| Healthcare | 145 | 0.483 | 未过滤 |
| Manufacturing | 173 | 0.578 | 未过滤 |

分题型：

| 类型 | Finance | Technology | Healthcare | Manufacturing |
|---|---:|---:|---:|---:|
| multi_hop | 0.583 | 0.659 | 0.438 | 0.489 |
| knowledge_update | 0.469 | 0.472 | 0.235 | 0.273 |
| temporal | 0.333 | 0.324 | 0.216 | 0.442 |
| user_implicit | 0.667 | 0.571 | 1.000* | 0.500* |
| term_ambiguity | 0.267 | 0.326 | 0.286* | 0.455* |
| abstention | 0.828 | 0.929 | 0.971 | 0.958 |

`*` 样本很小（2–11 条），不能单独下结论。

结论：

- 四域都在 48–58% 区间；
- knowledge_update 是跨域稳定短板（0.235–0.472）；
- Healthcare/Manufacturing 是未过滤集，不能和 Finance/Technology 直接排名；
- metadata-aware 仍不是官方 content-only BM25 条件；
- 不接 live。
