# 人格与记忆评测标准（Evaluation Standard）

> 目的：不再靠“发现一个新思路 → 改一版 → 看感觉”，而是用**冻结的标尺 + 回归门槛**判断每个改动是否值得。
> 原则：先有指标，再改代码；没有对照数据，不上线。

---

## 0. 结论（TL;DR）

现在的问题**不是缺一个更强的记忆/人格模型，而是缺一把固定、可重复、带置信区间的标尺**。解决方式：

1. **三层评测**：外部 benchmark 校准水平（LoCoMo、LongMemEval、GroupMemBench、CharacterEval）；内部 60 条冻结场景做回归；季度 50 条人工盲评做校准。
2. **评分卡分维 + 门禁**：记忆看 recall@5、角色互换、时间顺序、多跳、更新/拒答、隐私、来源；人格看跨场合一致、表达、漂移、披露分寸；工程看 p95、调用次数、回退率。**隐私是硬门禁，不做平均。**
3. **一条决策协议**：任何新想法必须先写“假设 → 指标 → 预期效应 → 成本 → 对照”；跑 baseline/candidate 配对评测 + bootstrap CI；通过才灰度，不通过记录“无效”，不合并。**没有指标假设的改动，不写代码。**
4. **成本控制**：确定性指标不花钱；本地 embedding；LLM judge 只跑 30–50 条并缓存；外部 benchmark 月度跑子集；PR 只跑 20 条 smoke + 单测。
5. **成熟度**：当前 L1（有零散测试），目标 L2（冻结集 + 自动回归 + 门禁），再往 L3（外部 benchmark + 人工校准）/L4（线上 canary + 漂移监控）。
6. **下一步（Phase 1，不烧 token）**：脱敏 60 条真实场景 → 写 `eval_suite.py` 先接确定性指标 → 产出 `eval/baselines/2026-10.json` → PR 门禁“recall 不降、隐私 0 越权”。

一句话：**以后不再问“这个新思路好不好”，而是问“它对应评分卡哪一项、在冻结集上有没有显著提升”。**

---

## 1. 现状：为什么现在很烧钱

- 只有零散单测（302 条）和少量探索性 pilot；
- 没有一个**固定场景集**，每次改动都换一批例子；
- 没有 baseline 和置信区间，无法判断“变好”是不是噪声；
- 没有外部 benchmark 校准，无法知道自己在行业中的位置；
- 新想法直接进实现，试错成本由线上和 token 承担。

这对应评测成熟度的 **L1：有零散度量，但没有可重复的标尺**。

---

## 2. 目标：三层评测体系

### 第一层：外部 benchmark（校准“我们在什么水平”）

只取子集、固定版本、固定评测脚本；目标是**可比**，不是刷榜。

| Benchmark | 测什么 | 用法 |
|---|---|---|
| **LoCoMo** | 超长对话记忆：单跳/多跳/时间/常识/对抗 | 取 50 条 QA，映射到事实/情景检索 |
| **LongMemEval** | 信息抽取、多会话推理、时间推理、知识更新、拒答 | 取 5 类各 10 条，测召回与更新 |
| **GroupMemBench** | 多人对话中的记忆归属/受众 | 取多人群聊子集，测“谁说的、谁能知道” |
| **CharacterEval** | 中文角色扮演：人格一致性、知识、风格 | 取 30 条对话，测人格表达 |
| **PersonaLLM / 指令稳定性** | 人格表达与多轮漂移 | 用其协议做 24 场景 × 3 时间点 |
| **MemoryAgentBench** | 增量多轮记忆 | 子集，测更新/遗忘 |

> 外部集只用于**季度/月度快照**，不进每次 PR；避免评测成本和数据泄漏。

### 第二层：内部冻结场景（回归“我们的产品有没有退步”）

- **60 条真实场景**，从线上日志脱敏而来，覆盖：
  1. 群聊点名/旁观
  2. 私聊撒娇/吃醋
  3. 边界拒绝
  4. private/secret 披露
  5. 时间/角色互换
  6. 多跳关系
- 每条带**冻结的输入、允许的事实集合、期望行为**；
- 数据集版本化：`eval/datasets/<name>/<version>/`，带 SHA256；
- 训练/调参/报告严格分开，禁止用测试集调 prompt。

### 第三层：人类校准（判断“像不像她”）

- 每季度 50 条盲评：
  - 人格一致性（1–5）
  - 语气自然度（1–5）
  - 披露分寸（该说/不该说）
  - 记忆准确性（是否张冠李戴）
- 用 Cohen's kappa 校准 LLM judge；kappa < 0.6 时**只信人工**，不让 judge 当裁判。

---

## 3. 评分卡：不要一个总分，要“门禁 + 分维”

### 3.1 记忆

| 指标 | 定义 | 当前基线 | 目标 |
|---|---|---|---|
| recall@5 | 目标记忆进前 5 | 9/10（同义集） | ≥9/10，角色/时间集 ≥8/10 |
| MRR | 首个正确记忆的倒数排名 | 待测 | 建立基线 |
| 角色互换 | A→B vs B→A 是否区分 | 未测 | ≥90% |
| 时间顺序 | 之前/之后/更新 | 未测 | ≥85% |
| 多跳 | 2-hop 关系 | 未测 | 逐版提升 |
| 知识更新 | 旧值是否被覆盖 | 未测 | ≥90% |
| 拒答 | 不知道时是否承认 | 未测 | ≥90% |
| 隐私 | private/secret 越权 | 0 | 0（硬门禁） |
| 来源覆盖 | 事实带 source | 100% | 100% |

### 3.2 人格

| 指标 | 定义 | 当前基线 | 目标 |
|---|---|---|---|
| 跨场合一致 | 同一人 group/private 温柔/耐心差 | <2 分 | ≤2 |
| 人格表达 | CharacterEval/自评 rubric | 未测 | 建立基线 |
| 多轮漂移 | 24 场景 × 3 时间点 | 未测 | 不退化 |
| 披露分寸 | 该说/暗示/保留的匹配率 | 未测 | ≥80% |
| 禁用词 | 命中率 | 0 | 0 |
| 复读率 | 机械重复 | 未测 | 建立基线 |

### 3.3 工程

| 指标 | 目标 |
|---|---|
| p95 延迟 | 不超过基线 +20% |
| 每轮 embedding 调用 | ≤1 次 |
| 降级/回退率 | <1% |
| 单测/集成 | 保持 302+，覆盖率 ≥90% |

> 不做“单一总分”。总分会被 Goodhart，分维 + 门禁更稳。

---

## 4. 工具链

### 4.1 一个入口

```bash
python scripts/eval_suite.py --suite memory --baseline eval/baselines/2026-10.json
python scripts/eval_suite.py --suite persona --judge local
python scripts/eval_suite.py --suite all --report reports/eval-$(date +%F).json
```

- 先跑**确定性指标**（召回、角色、时间、隐私），后跑 LLM judge；
- 输出 JSON + Markdown；带模型版本、数据集版本、seed、耗时；
- 同一输入缓存 LLM 输出，避免重复烧 token。

### 4.2 统计

- 每条场景 3 seeds；报告均值 + 95% bootstrap CI；
- 候选 vs baseline 用**配对 bootstrap**；
- 只有 CI 排除 0 且效应量达到最小有意义差异（如 recall +5%）才采纳；
- 隐私指标是**硬门禁**：任何一条越权直接拒绝，不做平均。

### 4.3 CI

| 时机 | 跑什么 | 成本 |
|---|---|---|
| PR | 确定性 smoke（20 条）+ 302 单测 | 约 1 分钟 |
| 每晚 | 内部 60 条 + 外部子集（缓存） | 约 20–30 分钟 |
| 每月 | LoCoMo/LongMemEval/GroupMemBench 子集 | 固定预算 |
| 每季度 | 50 条人工盲评 | 人力 |

### 4.4 成本控制

- 确定性指标不花钱；
- embedding 用本地 bge，单条 10–85ms；
- LLM judge 只跑 30–50 条，缓存 + 固定 judge 模型；
- 外部 benchmark 只跑子集，月度而非每次提交；
- 候选方案先离线小样本，有信号再扩。

---

## 5. 决策协议（最重要）

任何新想法进入实现前，必须填一张卡片：

```
假设：X 会改善 Y
指标：recall@5 / 角色互换 / 人格漂移 ...
预期效应：+5% 或 +0.3 分
成本：延迟 / token / 复杂度
对照：baseline 版本 + 数据集版本
```

流程：

1. 在冻结集上跑 baseline；
2. 实现候选（可开关）；
3. 配对评测 + CI；
4. 通过门禁 → 灰度 → 全量；
5. 不通过 → 记录“无效”，不合并。

**没有指标假设的改动，不写代码。**

---

## 6. 成熟度模型

| 级别 | 特征 | 我们 |
|---|---|---|
| L0 | 靠感觉、无固定集 | 过去 |
| L1 | 有单测/零散指标 | **当前** |
| L2 | 冻结集 + 自动回归 + 门禁 | 目标（下一阶段） |
| L3 | 外部 benchmark + 人工校准 | 目标（季度） |
| L4 | 线上 canary + 漂移监控 | 长期 |

从 L1 到 L2 的关键不是模型，而是：**冻结 60 条场景 + 一个 runner + 一条 CI 门禁**。

---

## 7. 落地顺序

### Phase 1：先有标尺（不花钱）— 已落地

- 数据集：`eval/datasets/persona_memory_v1/scenarios.json`（60 条，SHA256 随报告）；
- Runner：`scripts/eval_suite.py`（临时 DB，不调 LLM）；
- 基线：`eval/baselines/2026-10.json`；
- 关键词基线：paraphrase 0/10（零字面重叠）、privacy 10/10（0 泄露）、venue 10/10、role 0/10、temporal 0/10、persona 10/10，overall 30/60；
- 语义基线：全类 10/10，overall 70/70（本地 bge + RRF）；
- 关系抽取：线上 LLM 抽到 35 条 alias + 1 条 friend + 2 条 sibling；works_at 仍为 0，multihop 评测目前用 seed 关系。
- 基线：`eval/baselines/2026-10.json`（关键词）、`eval/baselines/2026-10-semantic.json`（语义）；
- 门禁已接进 `scripts/qa_gate.sh` 的 Gate 2D：`python scripts/eval_suite.py --check eval/baselines/2026-10.json`。

### Phase 1 原计划

1. 从线上脱敏 60 条场景，冻结输入/期望；
2. 写 `eval_suite.py`，先接确定性指标：
   - 同义 recall、角色互换、时间顺序、隐私；
3. 生成 `baseline.json`；
4. PR 门禁：recall 不低于 baseline，隐私 0 越权。

### Phase 2：人格 judge（少量花钱）

1. 24 条人格场景 × 群/私聊；
2. 先人工标 50 条，校准 judge；
3. kappa ≥0.6 后，judge 只做 nightly；
4. 报告分维，不报总分。

### Phase 3：外部 benchmark

1. 适配 LoCoMo / LongMemEval / GroupMemBench 子集；
2. 固定脚本与版本；
3. 月度快照，不参与日常 PR。

### Phase 4：线上漂移

1. 采样真实对话，脱敏后进评测；
2. 监控 p95、回退率、披露越权；
3. 发现漂移再触发人工复核。

---

## 8. 非目标

- 不追求榜单 SOTA；
- 不用单一分数替代人工判断；
- 不把测试集用于调 prompt；
- 不在每次提交跑全量 LLM 评测。

---

## 9. 参考文献

- Maharana et al., *Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo)*, 2024. [arXiv:2402.17753](https://arxiv.org/abs/2402.17753)
- Wu et al., *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*, 2024. [arXiv:2410.10813](https://arxiv.org/abs/2410.10813)
- *GroupMemBench: Benchmarking LLM Agent Memory in Multi-Party Conversations*, 2026. [arXiv:2605.14498](https://arxiv.org/abs/2605.14498)
- *CharacterEval: A Chinese Benchmark for Role-Playing Conversational Agent Evaluation*, 2024. [arXiv:2401.01275](https://arxiv.org/abs/2401.01275)
- Jiang et al., *PersonaLLM*, 2023. [arXiv:2305.02547](https://arxiv.org/abs/2305.02547)
- Li et al., *Measuring and Controlling Instruction (In)Stability in Language Model Dialogs*, 2024. [arXiv:2402.10962](https://arxiv.org/abs/2402.10962)
- *Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions*, 2025. [arXiv:2507.05257](https://arxiv.org/abs/2507.05257)
- *AI Persona: Life-long Personalization*, 2024. [arXiv:2412.13103](https://arxiv.org/abs/2412.13103)
