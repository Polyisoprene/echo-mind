# 人格与记忆模型：现状、缺陷与改进方案

> 日期：2026-10-31 ｜ 范围：EchoMind 线上实现 + 公开论文对照
> 结论先行：**我们不是“embedding 唯一记忆”，也不是“纯向量 RAG”。** 人格与记忆都已有结构化骨架；真正的缺口集中在四件事：**事件时间/ACT-R 激活、关系结构、检索融合、层级组织**。其中前两项最值得先做，第三项决定“语义召回是否真的比关键词更懂情境”，第四项是规模化后的收益。
> 评测标准：见 [EVALUATION_STANDARD.md](EVALUATION_STANDARD.md)。没有冻结集、没有 baseline、没有显著提升的改动，不进入实现。

---

## 1. 现有人格模型

### 1.1 结构

| 层 | 载体 | 作用 | 约束 |
|---|---|---|---|
| 慢基线 | `plastic_params` | 7 维性格底色 | 年预算 4，偏离 ≤12 |
| 日结算 | `persona_pending` | 每日累积 | ≤4/天 |
| 快状态 | `persona_state` | 当下偏移 | ±10，步长 ≤4，45min 半衰 |
| 立场 | `persona_stance` | 对具体的人临时偏移 | ≤8 点 |
| 情绪/驱动 | `working_state(global)` | 秒–分钟 | 全局，跨群延续 |
| 关系 | `social_bonds` / `person_bonds` / `bond_venues` | 信任/好感/深度 | 人级 + 场合脸 |
| 涌现特质 | `persona_traits` | 习惯/雷点 | 证据字段已落库 |
| 披露分寸 | `disclosure_choice` | say/hint/keep | 门后决策 |

7 维当前基线：温柔 65 / 傲娇 62 / 俏皮 58 / 占有 75 / 自信 55 / 狡黠 52 / 叛逆 48。

### 1.2 已有优点

- **一个人，多场合**：温柔/耐心来自人级 trust/depth，俏皮来自场合 affinity；同一人跨群/私聊不换人。
- **快慢分离**：基线年预算、状态 45min 半衰，避免“一句话改变人格”。
- **披露分层**：先过硬门（private/secret），再由 7 维做 say/hint/keep；secret 需授权。
- **可审计**：`disclosures`、`memory_knowledge`、`disclosure_grants`；拒绝有 reason。
- **D14 已做 pilot**：user 轮承载 5/5 必须回复，system 轮 3/5 且 2 次只输出 tool_call → 保留 user 轮。

### 1.3 现有人格缺陷

| 编号 | 缺陷 | 证据 | 影响 |
|---|---|---|---|
| P1 | 7 维是**自研维度**，与 Big Five/HEXACO 无映射矩阵 | `persona_specs` 只标注理论参考 | 不能直接借用心理学常模；解释力依赖自研 rubric |
| P2 | 涌现特质仍是 **5 条固定文案** | `derive_emergent_trait` 条件命中固定字符串 | “成长”有限，容易复读；evidence_count 只是给固定文案计数 |
| P3 | 特质证据未反向影响 prompt | 线上 9 条特质全部 `evidence=1`，`min_evidence` 默认 0 | 证据型特质目前只是存储，未形成筛选/淘汰 |
| P4 | 立场系数仍是 `fit:pending` | `STANCE_COEFFICIENTS` 注释 | 温柔/耐心/俏皮的偏移量未标定 |
| P5 | 缺少长期人格一致性评测 | 只有单轮/极端档审计 | 无法量化“多轮后还是不是她” |
| P6 | 人格→记忆耦合弱 | 记忆影响 trait/state，但 trait 不参与检索 | 她不会因为“更温柔”而优先想起照顾类记忆 |

---

## 2. 现有记忆模型

### 2.1 结构

| 层 | 载体 | 内容 |
|---|---|---|
| 事实 | `semantic_facts` | subject + fact_text + confidence + scope + owner + sensitivity + source_quote |
| 情景 | `episodic_memories` | summary + key_detail + participants + importance + rehearsals + timestamp |
| 程序 | `procedural_rules` | 触发词 → 行为 |
| 工作 | `working_state` | 情绪/驱动/意图/好奇队列（带版本号） |
| 关系 | `social_bonds` / `person_bonds` / `bond_venues` | 人级关系 + 场合脸 |
| 向量 | `memory_vectors` | 512 维，bge-small-zh，按 model 隔离 |
| 披露 | `disclosures` / `memory_knowledge` / `disclosure_grants` | 说过/保留/谁知道/授权 |

### 2.2 检索流程

```
percept → 硬门（private/secret）
        → 人/场合/global 取事实
        → 关键词选择 或 语义 cosine rerank（覆盖足够时）
        → 情景回忆（retention + importance + relevance + 联想）
        → 人格 7 维 + 关系立场
        → 披露 say/hint/keep
        → prompt
```

### 2.3 线上数据（2026-10-31）

| 项 | 数值 |
|---|---|
| 事实 | 195（global public 26 / person group 27 / venue group 142） |
| 情景 | 184 |
| 程序规则 | 23 |
| 人 | 40，场合脸 41 |
| 涌现特质 | 9（全部 evidence=1） |
| 向量 | 195 × 512，model 隔离 |
| 披露 | 825 条 frame 级 `say` / 1 条 `said` |
| 告知史 | 29 |
| 测试 | 302 passed / 92% |
| 语义 recall@5 | 9/10（关键词/bigram 5/10） |
| 单条 embedding | 10–85ms；显存 +632MB |

### 2.4 已有优点

- **不是纯向量**：结构化事实/情景是主存储，向量可删可重建；
- **硬门在检索前**：private/secret 不因相似度高而放行；
- **来源/受众/敏感度**齐全；
- **人级关系**与场合脸分离；
- **工作状态版本化 + 冲突重试**；
- **语义 + 关键词双通道**，失败自动回退。

### 2.5 现有记忆缺陷

| 编号 | 缺陷 | 证据 | 对应你提到的风险 |
|---|---|---|---|
| M1 | 无类型化关系/角色 | **部分解决**：实体顺序守卫区分 A→B/B→A；`claims`/类型图仍未接 | 结构性失明 |
| M2 | 事实没有事件时间，检索不看时间 | **部分解决**：`event_time_ms` + recency 已进关键词/语义排序；因果链仍未建 | 时间/因果缺失 |
| M3 | 无融合打分 | recency 已加入语义排序；lexical/dense/relation 的 RRF 仍未做 | 向量迷雾 |
| M4 | 无层级/树 | 只有 scope（venue/person/global），没有 parent/child、层级摘要 | 情景断裂 |
| M5 | 无预测回答检索 | 只用原始 query，没有 HyDE/query expansion | 检索脆弱 |
| M6 | 披露多数是 frame 级 | 825 `say` vs 1 `said`；归因是词面重叠启发式 | 审计不精确 |
| M7 | 告知史只覆盖 source/owner | `memory_knowledge` 29，未在披露后传播“谁听到了” | 谁知道不完整 |
| M8 | ANN 未做 | 195 条精确 cosine，当前无损；规模上来才需要 | 当前不是问题 |
| M9 | 评测集小 | 10 条同义查询，无角色互换/时间/多跳 | 不能证明复杂场景 |
| M10 | `claims` 的时间字段未用 | `valid_from_ms/valid_to_ms` 在表里，但读路径关闭 | 事件时间缺失 |

---

## 3. 与行业方法对照

| 方法 | 核心 | 我们的状态 | 可借鉴 |
|---|---|---|---|
| MemGPT | 主上下文 / archival / recall 分层，分页换入换出 | 有工作/情景/事实/规则，但没有显式 context paging | 上下文预算与换页策略 |
| Generative Agents | memory stream + recency/importance/relevance + reflection | 情景有 retention/importance/relevance；事实没有时间 | 事实也纳入时间/重要性；增加 reflection 摘要 |
| RAPTOR | 递归摘要成树，层级检索 | 只有 scope 层，没有树 | 父子链接 + 层级摘要 |
| GraphRAG / Zep | 实体关系图、社区摘要、双时间边 | 只有 social bond 图，没有事件/实体图 | 类型化关系 + 时间边 |
| HyDE | 先预测答案，再用答案检索 | 没有 | 预测回答 → 抽词 → 双路检索 |
| ACT-R | 基础激活 + 扩散激活 + 部分匹配 | 有艾宾浩斯 retention，但不完整 | 形式化激活方程 |
| MemoryBank | 艾宾浩斯遗忘曲线 | 已用 retention | 保持 |
| A-MEM | Zettelkasten 式动态索引/链接 | 无 | 记忆间显式链接 |
| HippoRAG | 图索引 + Personalized PageRank 多跳 | 无 | 多跳关系检索 |
| PersonaLLM / 指令稳定性 | 人格表达与漂移评测 | 无长期漂移评测 | 人格一致性 benchmark |
| RRF | 多路召回融合 | 语义覆盖关键词，不是融合 | RRF/加权融合 |

---

## 4. 改进方案

### P0：事件时间 + ACT-R 激活 + 融合打分（先做，无额外 LLM）

**为什么先做**：不需要新模型调用，直接解决 M2/M3；可以用现有 195 条事实离线标定。

1. **schema**
   ```sql
   ALTER TABLE semantic_facts ADD COLUMN event_time_ms INTEGER NOT NULL DEFAULT 0;
   ALTER TABLE semantic_facts ADD COLUMN valid_from_ms INTEGER NOT NULL DEFAULT 0;
   ALTER TABLE semantic_facts ADD COLUMN valid_to_ms INTEGER;
   ALTER TABLE semantic_facts ADD COLUMN parent_id INTEGER;
   ```
2. **ACT-R 激活**
   ```
   B_i = ln( Σ_j (t_now - t_j)^(-d) )        # 事件时间，不是墙钟
   A_i = B_i + Σ_k W_k S_ki + M_i + ε        # 扩散 + 部分匹配 + 噪声
   retrieve if A_i > τ
   ```
   `d≈0.5` 先用文献默认，再用日志拟合；`τ` 用回放集标定，不拍脑袋。
3. **融合**
   ```
   score = w_d*z(cos) + w_l*z(lexical) + w_t*recency
         + w_i*importance + w_r*relation + w_s*source
   ```
   权重用 pairwise 标注 + 网格/逻辑回归拟合；保留硬门在最前。
4. **验收**
   - 现有 10 条同义查询 recall@5 不低于 9/10；
   - 新增角色互换、时间先后探针；
   - 延迟 p95 不超过当前 +20ms（纯本地计算）。

### P1：预测回答检索（HyDE）+ 双路融合（需要 A/B）

1. 用便宜模型生成“我大概会怎么答”（不直接进最终 prompt）；
2. 抽实体/关键词，得到 predicted query；
3. 原始 query 与 predicted query 双路召回；
4. RRF 融合，最终回答只基于真实记忆；
5. A/B：同场景、同模型、成对比较；指标 recall@5、答案正确率、延迟/费用；
6. 预测文本不落库为事实，避免自我污染。

**风险**：多一次 LLM 调用、预测错误引入噪声；必须保留原始通道做兜底。

### P1：父子链接 + 层级摘要（RAPTOR-lite）

1. `episodic_memories.parent_id` / `thread_id`；
2. `semantic_facts.parent_id`；
3. 按时间/主题聚合，生成层级摘要节点；
4. 检索先命中主题，再下钻；保留平铺检索做兜底；
5. 验收：多跳/长对话 recall，摘要不引入未发生事实。

### P2：类型化关系图 + 时间边（Zep/GraphRAG 思路）

```sql
memory_relations(
  id, subject_id, predicate, object_id,
  valid_from_ms, valid_to_ms, source_memory_id, confidence
)
```

- 把 `claims` 的 predicate/validity 接进读路径；
- 支持 `A --给--> B` 与 `B --给--> A` 的方向区分；
- 多跳用 Personalized PageRank（HippoRAG 思路）；
- 先做“事件角色/所有权/亲属/承诺”四类，不要一开始全领域。

### P2：人格-记忆耦合 + 漂移评测

- `trait_evidence(trait_id, memory_id, relation)`：特质来自哪条记忆；
- `min_evidence` 按证据累积灰度；
- 人格漂移 benchmark：
  - 24 场景 × 群/私聊 × 3 时间点；
  - 指标：温柔/耐心跨场合差 ≤2、trait 漂移、拒绝一致性、禁用词；
  - 配对 bootstrap，不只看均值。

---

## 5. 评测与验收

| 维度 | 指标 | 目标 |
|---|---|---|
| 语义召回 | recall@5 / MRR | 同义 ≥9/10；角色/时间探针 ≥8/10 |
| 结构 | 角色互换准确率 | ≥90% |
| 时间 | 先后顺序准确率 | ≥85% |
| 多跳 | 2-hop recall | 先基线，再逐版提升 |
| 人格 | 跨场合温柔/耐心差 | ≤2 分 |
| 人格 | 多轮 trait 漂移 | 有基线，逐版不退化 |
| 隐私 | private/secret 越权 | 0 |
| 成本 | p95 延迟 / 每轮 embedding 调用 | 不超过 +20ms / ≤1 次 |
| 回归 | QA gate | 保持 302+ |

**不要**用单一 recall 证明“记忆变好”；必须同时看角色、时间、多跳、隐私、人格一致性。

---

## 6. 风险与非目标

- **事件时间**需要事件抽取；先用消息时间戳/provenance，不追求完美语义时间；
- **ACT-R 参数**必须拟合，不能直接抄 0.5 当真理；
- **HyDE** 有幻觉风险，预测文本不落库、不直接进最终回答；
- **图/树**增加维护成本，当前 195 条事实先做融合与父子链接，不急着上图数据库；
- **隐私硬门**永远在激活/融合之前，任何新打分都不能绕过。

---

## 7. 参考文献

- Packer et al., *MemGPT: Towards LLMs as Operating Systems*, 2023. [arXiv:2310.08560](https://arxiv.org/abs/2310.08560)
- Park et al., *Generative Agents: Interactive Simulacra of Human Behavior*, 2023. [arXiv:2304.03442](https://arxiv.org/abs/2304.03442)
- Sarthi et al., *RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval*, 2024. [arXiv:2401.18059](https://arxiv.org/abs/2401.18059)
- Edge et al., *From Local to Global: A Graph RAG Approach to Query-Focused Summarization*, 2024. [arXiv:2404.16130](https://arxiv.org/abs/2404.16130)
- Gao et al., *Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE)*, 2022. [arXiv:2212.10496](https://arxiv.org/abs/2212.10496)
- Rasmussen et al., *Zep: A Temporal Knowledge Graph Architecture for Agent Memory*, 2025. [arXiv:2501.13956](https://arxiv.org/abs/2501.13956)
- Zhong et al., *MemoryBank: Enhancing Large Language Models with Long-Term Memory*, 2023. [arXiv:2305.10250](https://arxiv.org/abs/2305.10250)
- Xu et al., *A-MEM: Agentic Memory for LLM Agents*, 2025. [arXiv:2502.12110](https://arxiv.org/abs/2502.12110)
- Gutiérrez et al., *HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models*, 2024. [arXiv:2405.14831](https://arxiv.org/abs/2405.14831)
- Anderson et al., *An Integrated Theory of the Mind*, Psychological Review, 2004. [doi:10.1037/0033-295X.111.4.1036](https://doi.org/10.1037/0033-295X.111.4.1036)
- Jiang et al., *PersonaLLM: Investigating the Ability of Large Language Models to Express Personality Traits*, 2023. [arXiv:2305.02547](https://arxiv.org/abs/2305.02547)
- Li et al., *Measuring and Controlling Instruction (In)Stability in Language Model Dialogs*, 2024. [arXiv:2402.10962](https://arxiv.org/abs/2402.10962)
- Cormack et al., *Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods*, SIGIR 2009. [doi:10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114)
