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
