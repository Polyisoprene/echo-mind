# 人格自演化：论文依据与形式化模型

> **2026-11-01 状态**：本文是理论模型；当前实现与差距见 [CURRENT_STATE_2026-11-01.md](CURRENT_STATE_2026-11-01.md)。未实现项仍按本文的“不拍阈值”原则处理。

> 目标：把“经历→特质→记忆/行为→新经历”从口号变成可实现、可评测的模型。
> 原则：不引入拍脑袋阈值；能结构化的不用权重；不能用论文直接支持的，标为工程约定。

---

## 0. 结论先行

现有系统只完成了 **慢参数漂移**，缺三件事：

1. **证据账本**：每条 trait 为什么成立、在哪个情境成立；
2. **生命周期**：candidate → active → dormant/retired；
3. **闭环**：trait 影响记忆检索和行为资格，行为再产生新证据。

公开研究支持的建模结论：

| 结论 | 依据 | 对 EchoMind 的含义 |
|---|---|---|
| 人格应建模为**状态分布**，不是单一均值 | Fleeson 2001；Fleeson & Jayawickreme 2015 | trait 存均值 + 方差 + 情境；不要只存一个 7 维点 |
| 人格表达是 **if-situation-then-behavior** | Mischel & Shoda 1995 | 证据必须带 context；trait 可以是情境专属 |
| 快记忆/慢知识分离，靠离线复现巩固 | McClelland et al. 1995；Kumaran et al. 2016 | 快状态/事件缓冲 vs 慢基线；日结算要 replay |
| 睡眠/离线复现促进巩固 | Diekelmann & Born 2010 | 日结算是“离线巩固”，不是简单求和 |
| 记忆提取后会**再巩固**，可被更新 | Nader et al. 2000 | 反证能改写 trait，不是只增不减 |
| 成人特质年均变化很小 | Roberts et al. 2006 | 慢基线必须慢；当前 4 点/年是加速约定 |
| 叙事身份是人格的一部分 | McAdams & McLean 2013 | 周期性自传总结，但必须由证据约束 |
| 情绪/心境影响记忆提取 | Bower 1981 | trait/affect 应影响“想起什么” |
| 社会推断可用贝叶斯模型描述 | Baker et al. 2017；Tenenbaum et al. 2011 | 用后验更新 trait，而不是手调分数 |
| 间隔/多情境比单次重复更可靠 | Cepeda et al. 2006 | 激活要求跨独立情境，不是同一场景刷次数 |
| LLM agent 需要记忆层级/反思/巩固 | Park et al. 2023；Packer et al. 2023；Zhong et al. 2023；Rasmussen et al. 2025 | 复用 memory stream / consolidation，但补 trait 证据 |

---

## 1. 形式化：人格是一个带证据的随机过程

### 1.1 变量

- 情境 `c_t`：群/私聊、对象、话题、时间；
- 行为 `b_t`：说/不说、工具、拒绝/接话；
- 结果 `o_t`：接茬、冷场、冲突、被夸；
- 快状态 `x_t`：情绪/驱动/立场；
- trait `i`：类别、文本、证据、情境集合、状态分布；
- 记忆 `m`：事实/情节；
- 慢基线 `θ`：7 维。

### 1.2 证据更新：Beta-Bernoulli

对每个 trait `i`：

```
s_i = 支持证据数（跨独立情境去重）
c_i = 反证证据数
后验：Beta(1 + s_i, 1 + c_i)
后验均值：E[p_i] = (1 + s_i) / (2 + s_i + c_i)
```

- 先验 `Beta(1,1)` 是均匀先验，不引入偏好；
- `E[p_i] > 0.5` 是对称决策边界，不是调出来的阈值；
- **激活还需要 `distinct_contexts_i ≥ 2`**：一次只能说明“这次这样”，两次独立情境才能说明“倾向”；
- 同一情境重复 100 次，只算 1 个独立情境，避免刷证据。

这不是“2 分就激活”；2 是**可判别性的最低结构条件**，不是拟合权重。

### 1.3 状态分布：不存一个点，存分布

对每个 trait/情境，维护：

```
μ_i = 状态均值
σ_i² = 状态方差
n_i = 观测数
```

- `μ` 是“平时多强”；
- `σ` 是“波动多大/多情境依赖”；
- 高方差 trait 在 prompt 里写成条件句，而不是绝对人格。

这直接对应 Whole Trait Theory：trait 是状态密度分布，不是单一标签。

### 1.4 情境签名：CAPS 的 if-then

trait 不是全局常量，而是：

```
if context_signature(c) matches S_i:
    behavior tendency = f(μ_i, σ_i, x_t)
```

- `context_signature` 先做结构化标签：venue、audience、topic、time bucket；
- 同一 trait 可以有多个情境签名；
- 只在特定情境成立的特质，不应污染全局人格；
- 这也是防止“群里一套、私聊一套”被误判为不一致的关键。

### 1.5 快慢双层：CLS + sleep replay

```
快（事件/情节/快状态）
  → 每日离线 replay（选重要/矛盾/高预测误差事件）
  → 慢（trait 证据、7 维基线、叙事）
```

- 单轮不能改慢基线（现有约束保留）；
- 日结算不是“把 delta 求和”，而是**有选择地 replay**；
- replay 必须包含反例/中性例，不能只挑正向，否则会自我强化；
- 记忆提取后的再巩固：若新结果与旧 trait 冲突，写反证，不直接覆盖。

### 1.6 闭环：trait → 记忆/行为

```
active trait
  ├─ trait_memory_links → trait ranker（RRF 中的一路）
  ├─ 行为资格门（允许/不允许某类动作）
  └─ prompt 条件句
        ↓
新行为 → 新结果 → 新证据
```

- 记忆侧：只对 active trait 生效；有 link 的记忆排名上升；
- 行为侧：不做权重，做**资格门**（例如 boundary trait 才允许拒绝动作）；
- 反证侧：同一记忆/同一轮不能重复计证据，防止自证循环。

---

## 2. 与当前代码的映射

| 模型部件 | 当前状态 | 需要改 |
|---|---|---|
| 7 维慢基线 | 已有 `plastic_params`，年预算 4、偏离≤12 | 保留；不要放大 |
| 快状态 | 已有 `persona_state`，45min 半衰 | 保留 |
| 日结算 | 已有 `settle_baseline` | 加 replay 选择与反例 |
| trait 证据 | 只有计数 | 新增 `trait_evidence` 账本 |
| trait 文本 | 5 条固定 if | 证据模式 + LLM 总结 + 原文校验 |
| trait 生命周期 | 无 | candidate/active/dormant/retired |
| trait 情境 | 无 | `context_signature` |
| trait 状态分布 | 无 | μ/σ/n |
| trait→记忆 | 无 | `trait_memory_links` + trait ranker |
| trait→行为 | 只进 prompt | 资格门 |
| 长期评测 | 无 | counterfactual replay |

---

## 3. 分阶段实现

### P0：证据账本（不改行为）

```sql
trait_evidence(
  id, trait_id, session_id, turn_id,
  quote, polarity, context_hash, created_ms
)
```

- 从现有 9 条 trait 回填能追溯的证据；
- `evidence_count` 改为派生；
- 先只记录，不 gate。

**验收**：每条 active trait 都能列出证据原话；同一情境刷次数不增加独立证据。

### P1：生命周期（只改 prompt 可见性）

- candidate：1 个情境，不进 prompt；
- active：≥2 独立情境且后验均值>0.5；
- dormant：长期无强化；
- retired：反证后验<0.5。

- `_visible_traits` 改读生命周期，不再用 `min_evidence=0`；
- 先离线回放，确认不会把现有 9 条全清空。

**验收**：现有 9 条中哪些会 active/dormant，必须能解释；不能“全留”或“全删”。

### P2：trait 文本生成

- 从证据模式生成 candidate；
- LLM 只做总结，输出必须带 `evidence_quotes`；
- quote 必须能在原文找到，否则丢弃；
- 结构校验：category 枚举、长度上限、不得含隐私。

**验收**：同一证据集重复生成，trait 语义稳定；无引用则拒绝。

### P3：trait → 记忆

- `trait_memory_links`；
- `unified_rank` 加 `trait` ranker；
- 只在 active trait 上生效；
- 隐私/边界硬门不变。

**验收**：开/关 trait ranker，召回的记忆类型有可解释变化；隐私泄漏不增加。

### P4：trait → 行为 + 长期评测

- 资格门；
- 30 天 counterfactual replay；
- 三条经历流：温柔/冒犯/混合；
- 指标：trait 激活、漂移范围、行为变化、振荡、边界退化。

---

## 4. 评测：没有真人标签也能测

### 4.1 合成经历流

给定已知“真实 trait”的模拟用户/事件流，测：

- 2 个独立情境后是否激活；
- 反证后是否降级；
- 同一情境刷证据是否不激活；
- 噪声/矛盾下是否振荡；
- trait 是否改变检索；
- 隐私/边界是否不变。

### 4.2 对照

| 变体 | 目的 |
|---|---|
| 固定 5 条模板 | 当前基线 |
| 证据账本，不 gate | 只记录是否有用 |
| 证据账本 + 生命周期 | 筛选是否有效 |
| 全闭环（+trait memory/action） | 复利是否出现 |

### 4.3 指标

- **Trait activation precision/recall**（合成 ground truth）；
- **False activation rate**（反证后仍 active）；
- **Retrieval shift**（开/关 trait ranker 的记忆类型差异）；
- **Boundary invariance**（隐私/拒绝不退化）；
- **Drift bound**（7 维不越界、不振荡）；
- **Narrative consistency**（自传总结不引入无证据内容）。

不用 LLM judge 当门禁；人工标签冻结，不再新增。

---

## 5. 风险与约束

1. **自证循环**：trait 拉高相关记忆 → 记忆又强化 trait。  
   约束：证据去重、反例 replay、检索本身不计证据。
2. **过度拟合近期**：  
   约束：跨情境激活、日结算、慢回归。
3. **LLM 编造 trait**：  
   约束：原文 quote 校验、结构 schema、无引用拒绝。
4. **隐私/边界被人格绕过**：  
   约束：硬门在 trait 之前，trait 只能影响“怎么说/想起什么”，不能放行 private/secret。
5. **开放自修改**：  
   不做代码/prompt 结构自改；只做有界人格/记忆演化。

---

## 6. 参考文献

### 人格与情境

- Fleeson, W. (2001). Toward a structure- and process-integrated view of personality: Traits as density distributions of states. *Journal of Personality and Social Psychology*, 80(6), 1011–1027. https://doi.org/10.1037/0022-3514.80.6.1011
- Fleeson, W., & Jayawickreme, E. (2015). Whole Trait Theory. *Journal of Research in Personality*, 56, 82–92. https://doi.org/10.1016/j.jrp.2014.10.009
- Mischel, W., & Shoda, Y. (1995). A cognitive-affective system theory of personality. *Psychological Review*, 102(2), 246–268. https://doi.org/10.1037/0033-295X.102.2.246
- Roberts, B. W., Walton, K. E., & Viechtbauer, W. (2006). Patterns of mean-level change in personality traits across the life course. *Psychological Bulletin*, 132(1), 1–25. https://doi.org/10.1037/0033-2909.132.1.1
- McAdams, D. P., & McLean, K. C. (2013). Narrative identity. *Current Directions in Psychological Science*, 22(3), 233–238. https://doi.org/10.1177/0963721413475622

### 记忆、巩固与再巩固

- McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). Why there are complementary learning systems in the hippocampus and neocortex. *Psychological Review*, 102(3), 419–457. https://doi.org/10.1037/0033-295X.102.3.419
- Kumaran, D., Hassabis, D., & McClelland, J. L. (2016). What learning systems do intelligent agents need? Complementary learning systems theory updated. *Trends in Cognitive Sciences*, 20(7), 512–534. https://doi.org/10.1016/j.tics.2016.05.004
- Diekelmann, S., & Born, J. (2010). The memory function of sleep. *Nature Reviews Neuroscience*, 11, 114–126. https://doi.org/10.1038/nrn2762
- Nader, K., Schafe, G. E., & LeDoux, J. E. (2000). Fear memories require protein synthesis in the amygdala for reconsolidation after retrieval. *Nature*, 406, 722–726. https://doi.org/10.1038/35021052
- Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks. *Psychological Bulletin*, 132(3), 354–380. https://doi.org/10.1037/0033-2909.132.3.354

### 情绪、社会推断与贝叶斯

- Bower, G. H. (1981). Mood and memory. *American Psychologist*, 36(2), 129–148. https://doi.org/10.1037/0003-066X.36.2.129
- Baker, C. L., Jara-Ettinger, J., Saxe, R., & Tenenbaum, J. B. (2017). Rational quantitative attribution of beliefs, desires and percepts in human mentalizing. *Nature Human Behaviour*, 1, 0064. https://doi.org/10.1038/s41562-017-0064
- Tenenbaum, J. B., Kemp, C., Griffiths, T. L., & Goodman, N. D. (2011). How to grow a mind: Statistics, structure, and abstraction. *Science*, 331(6022), 1279–1285. https://doi.org/10.1126/science.1192788

### LLM Agent 记忆系统

- Park, J. S., et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior. arXiv:2304.03442. https://arxiv.org/abs/2304.03442
- Packer, C., et al. (2023). MemGPT: Towards LLMs as Operating Systems. arXiv:2310.08560. https://arxiv.org/abs/2310.08560
- Zhong, W., et al. (2023). MemoryBank: Enhancing Large Language Models with Long-Term Memory. arXiv:2305.10250. https://arxiv.org/abs/2305.10250
- Gutiérrez, B. J., et al. (2024). HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models. arXiv:2405.14831. https://arxiv.org/abs/2405.14831
- Rasmussen, P., et al. (2025). Zep: A Temporal Knowledge Graph Architecture for Agent Memory. arXiv:2501.13956. https://arxiv.org/abs/2501.13956
- Wu, D., et al. (2024). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. arXiv:2410.10813. https://arxiv.org/abs/2410.10813
- Zhang, Z., et al. (2024). A Survey on the Memory Mechanism of Large Language Model based Agents. arXiv:2404.13501. https://arxiv.org/abs/2404.13501
- Xu, W., et al. (2025). A-MEM: Agentic Memory for LLM Agents. arXiv:2502.12110. https://arxiv.org/abs/2502.12110
