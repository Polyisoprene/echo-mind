# LongMemEval QA / abstention 评测模型

> 依据：[LongMemEval ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/d813d324dbf0598bbdc9c8e79740ed01-Abstract-Conference.html) 与官方 [evaluate_qa.py](https://raw.githubusercontent.com/xiaowu0162/LongMemEval/main/src/evaluation/evaluate_qa.py)。
> 状态：P1，只评测，不用于训练/调参。

## 1. 数据

`data/external/longmemeval_s.json`：

```text
500 questions
30 个 question_id 含 "_abs" → abstention
470 个普通问题
```

之前只跑 100 题 retrieval；本阶段补：

- 500 题 retrieval；
- answer generation；
- QA accuracy；
- abstention accuracy；
- 分题型结果。

## 2. 官方协议

官方 `evaluate_qa.py` 的判分：

- single-session-user / assistant / multi-session：答案包含正确信息；
- temporal-reasoning：允许 off-by-one 天数；
- knowledge-update：旧信息 + 更新答案，以新答案为准；
- single-session-preference：按 rubric 是否利用用户偏好；
- `_abs`：模型是否识别为不可回答。

本实现复刻官方 prompt，不另造 judge 规则。

## 3. 系统适配

```text
question
  → 取 haystack sessions
  → session 聚合为 SemanticFact
  → bge-m3 dense + BM25 + recency/order/confidence/lock
  → RRF top-k
  → LLM 阅读 memories
  → answer
  → 官方 judge prompt
```

生成 prompt 明确：

```text
只使用 memories；证据不足就说 "I don't know"。
```

## 4. 指标

| 指标 | 说明 |
|---|---|
| QA accuracy | judge=yes 比例 |
| abstention accuracy | `_abs` 子集 judge=yes |
| per-type | 6 个 question_type |
| retrieval recall@5 / MRR | 独立报告，不混入 QA |

## 5. 限制

- 官方 judge 默认 GPT-4o；本机使用可用 LLM，**不能**与论文端到端分数直接排名；
- 500 题 generation + judge 成本高，先跑分层小样本，再扩全量；
- judge 只评估，不作训练标签；
- session 聚合仍会稀释证据；
- 不改人格/ranker。

## 6. 验收

- 小样本 30 题（每类 5 题）跑通；
- 输出每类 accuracy 与 abstention accuracy；
- 全量 500 结果单独落盘；
- 判分 prompt 与官方一致；
- 失败可回退到纯 retrieval 报告。

## 7. 结论使用

- 只用于判断“记忆是否支持回答”，不用于自动调权；
- 若 QA 差但 retrieval 好，优先修 reading/context；
- 若 abstention 差，优先修“证据不足”提示，不夸大人格。

## 8. 2026-11-01 远端小样本（30 题）

执行环境：

```text
192.168.3.2:~/echo-mind-eval
PYTHONPATH=src
embedding: 192.168.3.2:8010
LLM: 192.168.3.114:9000
```

命令：

```bash
PYTHONPATH=src .venv/bin/python scripts/eval_longmemeval_qa.py \
  --limit 30 --batch 4 \
  --out eval/baselines/longmemeval-qa-30-2026-11-01.json
```

结果：

| 类型 | n | accuracy |
|---|---:|---:|
| knowledge-update | 5 | 0.0 |
| multi-session | 4 | 0.0 |
| single-session-assistant | 4 | 0.0 |
| single-session-preference | 4 | 0.25 |
| single-session-user | 9 | 0.556 |
| temporal-reasoning | 4 | 0.0 |
| abstention | 5 | 1.0 |
| 总 | 30 | 11/30 = 0.367 |

注意：

- 30 条里刻意抽了 5 条 abstention（全库 30/500），所以总正确率**不是** LongMemEval 总体估计；
- 普通题大量回答 `I don't know`，说明 top-5 session 没覆盖证据，或生成端过度保守；
- 先修检索/上下文，不调 judge；
- 500 题 retrieval 正在远端跑，结果单独落盘。


## 9. 500 题 retrieval（已完成）

远端全量：

```text
session recall@5 = 0.528
MRR = 0.375
abstention 子集 recall@5 = 0.567
```

报告：`eval/baselines/longmemeval-500-2026-11-01.json`

仍未跑 500 题 QA 全量；30 题 QA 小样本只用于协议验证。

## 10. Oracle reading 消融（2026-11-01）

为区分“检索没找到”和“读到了也答不对”，新增 `--oracle`：

```text
context = answer_session_ids 对应的 gold sessions
不跑 embedding/ranker
```

30 题样本中 5 条 abstention 跳过，剩 25 条：

| 类型 | n | accuracy |
|---|---:|---:|
| knowledge-update | 5 | 0.0 |
| multi-session | 4 | 0.0 |
| single-session-assistant | 4 | 0.0 |
| single-session-preference | 4 | 0.5 |
| single-session-user | 4 | 0.0 |
| temporal-reasoning | 4 | 0.0 |
| **总** | **25** | **2/25 = 0.08** |

结论：

- 即使给 gold sessions，reading 仍然很差；
- 不能把 30 题 end-to-end 的 11/30 全归因于检索；
- 需要先检查 gold session 是否真的包含答案、上下文截断、生成 prompt，而不是继续调 ranker；
- 这是 25 条小样本，不是 500 题结论。

## 11. 修正后的正式结果（2026-11-01）

### 11.1 两个 bug

1. **生成 prompt 偏离官方**：之前强制“只使用 memories，证据不足就说 I don't know”，造成过度拒答；已改为官方 `History Chats + Current Date + Question + Answer`。
2. **judge prompt 占位符 bug**：普通字符串里的 `Model Response: {{}}` 被 `.format` 当成转义字面量，judge 永远看到空响应 `{}`，因此大量正确答案被判 no。

修复后加回归测试：

`tests/unit/test_longmemeval_judge_prompt.py`

### 11.2 Oracle reading（gold sessions，25 条可答）

```text
correct = 24/25 = 0.96
```

分类型：

| 类型 | n | accuracy |
|---|---:|---:|
| knowledge-update | 5 | 1.0 |
| multi-session | 4 | 0.75 |
| single-session-assistant | 4 | 1.0 |
| single-session-preference | 4 | 1.0 |
| single-session-user | 4 | 1.0 |
| temporal-reasoning | 4 | 1.0 |

结论：**reading 本身基本可用；主要损失来自检索/上下文选择**，不是模型不会答。

### 11.3 End-to-end 30 题（检索 + reading）

| 类型 | n | accuracy |
|---|---:|---:|
| knowledge-update | 5 | 0.0 |
| multi-session | 4 | 0.25 |
| single-session-assistant | 4 | 0.5 |
| single-session-preference | 4 | 0.25 |
| single-session-user | 9 | 0.667 |
| temporal-reasoning | 4 | 0.0 |
| abstention | 5 | 1.0 |
| **总** | **30** | **10/30 = 0.333** |

解读：

- 30 条中 5 条 abstention 过采样，总体不是 500 题估计；
- oracle 24/25 vs end-to-end 10/30，差距主要来自检索没把证据 session 放进 top-5；
- 下一步应针对 knowledge-update / temporal-reasoning 的检索，而不是改 judge。

### 11.4 旧结果作废

- 旧 `11/30`、`2/25` 是 judge 占位符 bug + 过度拒答的组合结果，**不再作为结论**；
- 保留文件仅作 bug 审计记录。


## 12. 诊断与日期排序（2026-11-01）

30 题 top-5 诊断：

```text
gold 命中 top5: 13/30
knowledge-update: 2/5 命中，0/5 正确
temporal-reasoning: 2/4 命中，0/4 正确
```

按 session date 排序后 end-to-end 仍为 **10/30**，没有提升。  
检索丢失与 knowledge-update/temporal 的上下文选择是下一步，不是 judge/reading。

## 13. 最终 conditional ranker 的 30 题 QA（2026-11-01）

用最终 ranker 重跑同一 30 题：

| 类型 | n | accuracy |
|---|---:|---:|
| knowledge-update | 5 | 0.60 |
| multi-session | 4 | 0.50 |
| single-session-assistant | 4 | 1.00 |
| single-session-preference | 4 | 0.75 |
| single-session-user | 9 | 0.778 |
| temporal-reasoning | 4 | 1.00 |
| abstention | 5 | 1.00 |
| **总** | **30** | **23/30 = 0.767** |

对比：

```text
旧 hybrid: 10/30
最终 hybrid: 23/30
```

说明：

- 检索修复确实传导到端到端 QA；
- knowledge-update 仍只有 0.60，是剩余短板；
- 30 题 abstention 过采样，不能直接外推 500 题总体。

## 14. 500 题全量 QA（2026-11-01，最终 ranker）

5 个 100 题分片 + 缺失补齐，合并后 **500/500 覆盖，无重复、无缺失**：

| 类型 | n | accuracy |
|---|---:|---:|
| knowledge-update | 78 | 0.641 |
| multi-session | 133 | 0.271 |
| single-session-assistant | 56 | 0.661 |
| single-session-preference | 30 | 0.633 |
| single-session-user | 70 | 0.671 |
| temporal-reasoning | 133 | 0.278 |
| abstention | 30 | 0.333 |
| **总体** | **500** | **226/500 = 0.452** |

对照：

```text
30 题样本：23/30 = 0.767
500 题全量：226/500 = 0.452
```

结论：

- 30 题样本的 abstention 过采样 + 小样本，显著高估总体；
- 500 题真实短板是 **multi-session 0.271、temporal 0.278、abstention 0.333**；
- retrieval 已 0.954，oracle reading 24/25，说明剩下主要是“选中/读对/该拒答”；
- 该分数使用本机 judge/模型，不是 GPT-4o 官方 judge，不能直接与论文排名比较；
- 500 QA 完整结果文件：`eval/baselines/longmemeval-qa-500-final-2026-11-01.json`。
