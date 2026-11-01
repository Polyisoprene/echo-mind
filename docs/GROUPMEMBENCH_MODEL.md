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
