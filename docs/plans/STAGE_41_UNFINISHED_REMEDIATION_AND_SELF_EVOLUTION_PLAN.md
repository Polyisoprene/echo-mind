# Stage 41 未完成事项建模、自演化闭环与落实计划

> 日期：2026-11-01
> 范围：以 `docs/PERSONA_MEMORY_AUDIT_AND_ROADMAP.md`、`docs/PERSONA_SELF_EVOLUTION_MODEL.md`、`docs/MASTER_BACKLOG.md` 为基线，覆盖人格、记忆、评测、身份/关系四条未完成线。
> 原则：先建模再写代码；新数值必须有论文/数据/账本依据；不做代码或 prompt 的自修改。

> **2026-11-01 更新**：第 0 节是历史基线；最新真实状态与代码审计盲区见文末 14.64。

---

## 0. 当前基线（2026-11-01）

| 项 | 现状 |
|---|---|
| 检索 | 统一 ranker fusion（BM25/dense/recency/order/relation/confidence/lock + RRF） |
| 关系图 | PPR，非固定跳数 |
| Embedding | `BAAI/bge-m3`，1024 维；主库 204 条、小沫库 14 条已回填 |
| 内部评测 | 70/70；关 relations 后 60/70，multihop 0/10 |
| 外部评测 | LongMemEval-S 100 题，session recall@5 **51.0%**，MRR 0.315 |
| 测试 | 321 passed |
| 人格特质 | 线上 9 条；`evidence_count` 1–6；`min_evidence=0` |
| 特质文本 | `derive_emergent_trait` 5 条固定文案 |
| 人格→记忆 | 未接；trait 不影响检索 |
| 长期漂移评测 | 未做 |
| claims 读路径 | `FACTS_V2` 关闭 |
| 外部 QA/abstention | 未做；LongMemEval 只跑 100/500 检索 |

---

## 1. 未完成项全景

### A. 人格 / 自演化

| ID | 未完成项 | 现状 | 目标 |
|---|---|---|---|
| A1 | `trait_evidence` 证据账本 | 只有计数 | 原话、场景、支持/反证可追溯 |
| A2 | trait 生命周期 | 无 | candidate → active → dormant/retired |
| A3 | 特质证据门控 | `min_evidence=0` | 只让 active trait 进 prompt |
| A4 | 特质文本生成 | 5 条固定文案 | 从证据模式生成，带原文引用 |
| A5 | trait → 记忆检索 | 无 | trait ranker 进 RRF |
| A6 | trait → 行为资格 | 只进 prompt | 用资格门决定动作是否允许 |
| A7 | 长期漂移评测 | 无 | 30 天 counterfactual replay |
| A8 | 7 维 ↔ Big Five/HEXACO | 无映射 | 先做构念效度研究，不硬造矩阵 |
| A9 | 立场系数 | `fit:pending` | 用冻结标签标定；不够就保持 pending |
| A10 | 外部人格 benchmark | 无 | CharacterEval 类中文人格集 |
| A11 | 风格监控 | 文件未跟踪/暂停 | 确定性指标，不再真人测试 |

### B. 记忆 / 检索

| ID | 未完成项 | 现状 | 目标 |
|---|---|---|---|
| B1 | ACT-R base-level activation | 只有 recency/PPR | 作为独立 ranker，与现有 RRF 融合 |
| B2 | HyDE / query expansion | 只用原 query | 先 shadow，A/B 通过再启用 |
| B3 | 父子链接 / 层级摘要 | 只有 scope | 事实/情节/摘要多级检索 |
| B4 | claims 读路径 `FACTS_V2` | 关闭 | 先补 provenance，再 shadow，最后切换 |
| B5 | 披露归因 M6 / 告知传播 M7 | frame 级 say | 按收件人传播“谁听到了” |
| B6 | 事实层时间边 | claims 有，读路径关 | 有效期过滤 + 时间关系 |
| B7 | ANN | 未做 | 规模上来再做；当前不紧急 |

### C. 评测

| ID | 未完成项 | 现状 |
|---|---|---|
| C1 | 人格自演化 replay | 无 |
| C2 | LongMemEval 500 + QA/abstention | 只 100 题检索 |
| C3 | LoCoMo / GroupMemBench | 未接 |
| C4 | 外部中文人格集 | 未接 |
| C5 | 确定性风格监控 | 未接线 |

### D. 身份 / 关系 backlog

| ID | 未完成项 | 现状 |
|---|---|---|
| D1 | 人格语料硬编码 | `MASTER_BACKLOG` 仍列 P1 文案 |
| D2 | bond 事件采集接线 | 已建，未完全接线 |
| D3 | 跨群 B 系列自适应 | 未做 |
| D4 | 人工拟合 bond | 暂缓；不新增真人测试 |

---

## 2. 目标模型

### 2.1 人格自演化闭环

```
ExperienceEvent
  → TraitEvidence（支持/反证 + 原话 + 情境）
  → Beta 后验 + 独立情境计数
  → 生命周期 candidate/active/dormant/retired
  → active trait
      ├─ prompt 条件句
      ├─ trait_memory_links → trait ranker（RRF）
      └─ 行为资格门
  → 新行为 → 新经历
```

### 2.2 证据模型（不拍阈值）

```
s = 支持证据数（跨独立情境去重）
c = 反证证据数
后验 = Beta(1+s, 1+c)
E[p] = (1+s) / (2+s+c)
```

- `Beta(1,1)` 是均匀先验；
- `E[p] > 0.5` 是对称决策边界；
- 激活还要求 `distinct_contexts ≥ 2`；
- **2 是可判别性的最低结构条件，不是拟合权重**；
- 同一 `context_hash` 重复只增加强度，不增加独立证据。

### 2.3 状态分布与情境签名

- 每 trait/情境维护 `μ, σ², n`（Welford 在线更新）；
- 高方差 trait 渲染成条件句，不渲染成绝对人格；
- `context_signature`：venue + audience + topic + time bucket；
- 对应 Whole Trait Theory（Fleeson 2001）与 CAPS（Mischel & Shoda 1995）。

### 2.4 快慢巩固

- 快：事件/情节/快状态；
- 每日 replay：选重要、矛盾、高预测误差事件；
- 慢：trait 证据、7 维基线、叙事；
- replay 必须含反例/中性例，防止自我强化；
- 提取后若结果冲突，写反证，不覆盖历史。

### 2.5 行为资格，不是行为权重

- active boundary trait → 允许拒绝/冷处理动作；
- active care trait → 允许主动关心/追问；
- active novelty trait → 允许搜索/玩梗/探索；
- 没有 trait → 动作不进入候选；
- 不引入“trait 权重 × 行为分”这类数值。

---

## 3. 工作流 A：人格自演化

### A1. P0 证据账本（先做，不改行为）

**实现**

- 新增 `trait_evidence`：

```sql
CREATE TABLE IF NOT EXISTS trait_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trait_id INTEGER NOT NULL REFERENCES persona_traits(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  quote TEXT NOT NULL,
  quote_kind TEXT NOT NULL CHECK(quote_kind IN ('assistant','user','tool')),
  polarity INTEGER NOT NULL CHECK(polarity IN (-1, 1)),
  context_hash TEXT NOT NULL,
  created_ms INTEGER NOT NULL,
  UNIQUE(trait_id, turn_id, polarity)
);
CREATE INDEX IF NOT EXISTS idx_trait_evidence_trait
  ON trait_evidence(trait_id, created_ms);
```

- `turn_id` 先使用 `TurnOutcome.session_id`；未来有真实 message_id 再迁移，不混用。
- `quote` 必须取自 `sent_texts`/trigger 文本/tool 名之一；不能为空。
- `context_hash = sha256(chat_key | sorted(audience_ids) | UTC day)`；
  - 先不引入 topic 聚类，避免额外阈值；topic 后续作为可选字段。
  - 同一天同场景重复只算一个独立情境。
- `evidence_count` / `contradiction_count` 先双写，再从表派生；旧列保留只读兼容。
- 现有 9 条 trait 回填：只回填能追溯到 `source` 和原文的；不能追溯的标 `legacy_unverified`，不得直接 active。
- 先 shadow 写，不改 prompt。

**验收**

- 每条 active trait 都能列出至少 1 条原文引用；
- 同一 turn 重复写不增加证据；
- 开启/关闭账本，prompt 逐字一致（shadow 等价）。

### A2. P1 生命周期（只改可见性）

**实现**

- `persona_traits` 增加：
  - `status TEXT NOT NULL DEFAULT 'legacy_unverified'`（candidate/active/dormant/retired/legacy_unverified）
  - `active_since_ms INTEGER NOT NULL DEFAULT 0`
  - `last_support_ms INTEGER NOT NULL DEFAULT 0`
  - `last_contradiction_ms INTEGER NOT NULL DEFAULT 0`
  - `state_n INTEGER NOT NULL DEFAULT 0`
  - `state_mean REAL NOT NULL DEFAULT 0`
  - `state_m2 REAL NOT NULL DEFAULT 0`（Welford）
- 状态机：
  - candidate：有证据但独立情境 < 2；
  - active：≥2 独立情境且后验均值 > 0.5；
  - dormant：长期无强化；
  - retired：反证后验 < 0.5。
- `TRAIT_LIFECYCLE_MODE=shadow`：先计算，不改 prompt；稳定后切 `active`。
- 删除 `min_evidence` 的运行时语义，保留只读兼容。

**验收**

- 现有 9 条全部有状态和理由；
- 不允许“全部 active”或“全部清空”；
- shadow 模式下 prompt 不变；
- active 模式只出现 active trait。

### A3. P2 特质文本生成

**实现**

- 只在 ≥2 独立情境后生成 candidate；
- LLM 输入：证据原话 + 情境；输出：
  - `category`（habit/taste/temperament/taboo）
  - `trait_text`
  - `evidence_quotes`
- `evidence_quotes` 必须是原文子串，否则丢弃；
- 结构校验：长度、隐私词、不得含用户私密内容；
- 同一证据集重复生成要做一致性抽检。

**验收**

- 生成 100 条候选，引用校验 100% 通过；
- 无引用/编造的直接拒绝；
- 与旧 5 条模板做 A/B，不强制替换。

### A4. P3 trait → 记忆

**实现**

- 新增 `trait_memory_links(trait_id, memory_kind, memory_id, relation, evidence_ms)`；
- `unified_rank` 增加 `trait` ranker（只对 active trait 生效）；
- 与现有 ranker 一样走 RRF，不加权重；
- 隐私/边界硬门在 trait 之前。

**验收**

- 开/关 trait ranker，召回的记忆类型有可解释变化；
- 隐私泄漏仍为 0；
- 70/70 不回归；hard negatives 不退化。

### A5. P4 行为资格与长期 replay

**实现**

- `action_eligibility`：trait → 允许的动作类；纯规则，不打分；
- 30 天 replay：
  - 温柔流、冒犯流、混合流；
  - 初始人格相同；
  - 记录 trait 状态、检索、行为、边界。
- 指标：激活/退场、漂移界、振荡、检索偏移、边界不变性。

**验收**

- 三条流产生可解释的不同人格轨迹；
- 7 维不越界、不振荡；
- 隐私/拒绝不退化；
- 无“全 active”或“身份崩坏”。

### A6. 7 维映射与立场标定（研究项，不硬造）

- 7 维 ↔ Big Five/HEXACO：先用现有 50 条人工标签做探索性因素分析；样本不足就明确“不做映射”，不硬编矩阵。
- 立场系数：用冻结的 90 组 pairwise 标签做序数回归/偏好模型；标签不足则保持 `fit:pending`。
- 不新增真人测试。

### A7. 外部人格 benchmark

- 选 CharacterEval 或中文角色人格集；
- 先做数据许可/字段映射；
- 只做自动指标，LLM judge 不作门禁；
- 无数据则不虚报“已接”。

---

## 4. 工作流 B：记忆 / 检索

### B1. ACT-R base-level activation

**建模**

```
B_i = ln( Σ_j t_j^(-d) )
```

- `t_j` = 第 j 次使用/检索距今秒数；
- `d` = ACT-R 衰减参数，**不是本项目拟合值**；用 ACT-R 默认/论文值，登记 ledger；
- 若无法确认 `d` 的公开来源，则本项不实现，不用“差不多”的数值。

**实现**

- 作为 `actr` ranker 进 RRF；只输出排序，不引入权重；
- 与 recency 做留一消融；
- 无增益或与 recency 重复，不启用。

**依据**

- Anderson & Schooler (1991), *Reflections of the environment in memory*；
- ACT-R 官方教程/实现（base-level activation）。

### B2. HyDE / query expansion

**建模**

- 用现有 LLM 生成一个“假设文档”（hypothetical document），再对其做 embedding；
- 用假设文档向量检索真实记忆，而不是直接检索原 query；
- 生成内容可能含假细节，靠真实语料向量邻域过滤。

**实现**

- 先 shadow：同时记录原 query 与 HyDE 的 top-k；
- 记录延迟、token 成本、召回差异；
- 隐私硬门在检索前不变；
- A/B 通过才启用；不通过就删除，不保留死代码。

**依据**

- Gao et al. (2022), *Precise Zero-Shot Dense Retrieval without Relevance Labels*（HyDE），arXiv:2212.10496。

### B3. 父子链接 / 层级摘要

**建模**

- 参考 RAPTOR：递归 embedding → 聚类 → 摘要，构建自底向上的摘要树；
- 检索可从叶子事实、情节、摘要多个层级同时取，再融合；
- 不预设固定层级数；层数由数据规模/聚类结果决定，参数登记 ledger。

**实现**

- 先只对 episodic/session 建树，不动 semantic facts；
- 根节点只做摘要，不替代原始证据；
- 先离线 A/B，再 shadow，再启用。

**依据**

- Sarthi et al. (2024), *RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval*，arXiv:2401.18059。

### B4. claims `FACTS_V2`

- 先补 provenance（source/turn/evidence）；
- shadow 双读，比较 facts vs claims；
- 无隐私泄漏、覆盖不降才切换；
- 迁移可回滚。

### B5. 披露归因 M6 / 告知传播 M7

- 披露事件记录 audience；
- `memory_knowledge` 按收件人传播；
- 测试“谁听到了/谁没听到”；
- secret/private 硬门不放宽。

### B6. 事实层时间边

- claims 已有 `valid_from/to`，但读路径关闭；
- facts 增加有效期/时间关系需要迁移与回填；
- 先只做过滤影子，不改默认读路径。

### B7. ANN

- 当前 204 条不紧急；
- 只有规模/延迟指标触发才做；
- 触发条件写进参数账本，不凭感觉。

---

## 5. 工作流 C：评测

### C1. 长期人格 replay

- 合成三条经历流，各 30 天；
- 测 trait 激活/退场、false activation、检索偏移、边界不变性、漂移界；
- 对照组：固定模板 / 证据账本不 gate / 证据+生命周期 / 全闭环。

### C2. LongMemEval 500 + QA/abstention

- 从 100 扩到 500；
- 加 answer generation（gold answer 对比）和 abstention；
- 报告分题型，不只看总分；
- 仍注明 retrieval-only 与 QA 的区别。

### C3. LoCoMo / GroupMemBench

**优先级：GroupMemBench > LongMemEval > LoCoMo。**

- GroupMemBench 直接测多人群聊、说话人绑定、ToM/受众词汇差异，和 EchoMind 的群聊场景最贴近；
  - 数据：HuggingFace `kimperyang/GroupMemBench`；
  - 代码：`UCSB-NLP-Chang/GroupMemBench`；
  - 指标：answer accuracy + cost + storage；六类问题；
  - 论文报告最强系统平均 46.0%，BM25 可匹配多数系统，说明“结构化/说话人条件”是重点。
- 先映射 `chat_key`、`speaker_id`、`audience`、`question_user`；
- 无数据/许可不清就不写“已接”。

### C4. 外部中文人格集

**优先 CharacterEval**：

- 1,785 段中文角色对话、77 个角色、13 个指标/4 维度；
- 指标：知识一致性、人格行为/话语一致性、真人感、共情、表达多样性；
- CharacterRM 是人工标注训练的奖励模型，可作辅助，不作唯一门禁；
- 数据/代码：`morecry/CharacterEval`。

**适配限制**

- EchoMind 是原创角色，不是既有小说角色；只迁移指标和场景协议，不直接套角色知识；
- 不新增真人测试；用自动指标 + 冻结人工标签；
- LLM judge/CharacterRM 只做横向参考，不能替代边界/隐私硬门。

### C5. 确定性风格监控

- 指标：长度、>40 字比例、解释词命中、括号动作、多问句；
- 只报告分布，不设拍脑袋阈值；
- 不新增真人测试；
- 文件纳入 git，不再留 untracked。

---

## 6. 工作流 D：身份 / 关系 backlog

### D1. 人格语料硬编码

- `MASTER_BACKLOG` 里的 P1 文案：`agent_runner.py`、`frame_renderer.py`、`personality.py`、`scheduler.py`、`epistemic.py`、`drives.py`；
- 全部改读 `bot_naming()`；
- 加 `rg` 门禁，禁止新增硬编码自称。

### D2. bond 事件采集接线

- 已建事件表，未完全接线；
- 先 wire，后 shadow；
- 不改现有评分默认值。

### D3. 跨群 B 系列

- 用现有 bond 校准，不引入新权重；
- 先离线回放，再灰度；
- 拟合数据不足则保持规则。

### D4. 人工拟合 bond

- 暂缓；不新增真人测试；
- 只用已有标签。

---

## 7. 依赖与执行顺序

```
A1 证据账本
  ├─→ A2 生命周期
  │     ├─→ A3 文本生成
  │     │     └─→ A4 trait→记忆
  │     │           └─→ A5 行为+replay
  │     └─→ C1 长期 replay
  ├─→ B4 claims（provenance）
  └─→ C5 风格监控（独立）

B1 ACT-R / B2 HyDE / B3 层级（可并行，不依赖 A）
B5 披露 / B6 时间边（依赖 B4）
C2/C3/C4（评测线，可并行）
D1/D2/D3（独立 backlog）
```

**建议顺序**

1. A1 + C5 + D1（低风险、先打底）
2. A2（shadow）+ B1/B2 shadow
3. A3 + A4
4. A5 + C1
5. B4/B5/B6
6. C2/C3/C4
7. D2/D3

---

## 8. 验收矩阵

| 项 | 必须通过 |
|---|---|
| A1 | active trait 100% 有原文引用；重复证据不计数 |
| A2 | 9 条全部有状态/理由；shadow prompt 不变 |
| A3 | 引用校验 100%；编造/隐私直接拒绝 |
| A4 | 隐私泄漏 0；70/70 不回归；检索变化可解释 |
| A5 | 三条流轨迹可解释；无越界/振荡/边界退化 |
| B1 | 与 recency 消融；无增益不启用 |
| B2 | shadow 延迟/成本可接受；A/B 通过 |
| B4 | 无泄漏、覆盖不降、可回滚 |
| B5 | 谁知道/谁不知道可验证 |
| C1 | 对照组差异可解释 |
| C2 | 500 题结果 + QA/abstention |
| D1 | `rg` 无新增硬编码自称 |

---

## 9. 风险

| 风险 | 缓解 |
|---|---|
| 自证循环：trait 拉记忆，记忆再强化 trait | 证据去重；检索不计证据；反例 replay |
| LLM 编造 trait | 原文引用校验；schema；无引用拒绝 |
| 人格绕过隐私 | 硬门在 trait 之前；trait 不能放行 private/secret |
| 长期漂移振荡 | 慢预算/回归保留；replay 监测 |
| 迁移不可回滚 | 每步 migration + 备份 + shadow |
| 评测自嗨 | 内部 70 + 外部 LongMemEval/GroupMemBench；不用 LLM judge 门禁 |

---

## 9.1 调研补充与计划修正（2026-11-01）

本轮把仍含糊的 8 个点查清并回填：

| 模糊点 | 调研结论 | 对计划的影响 |
|---|---|---|
| ACT-R 激活公式 | `B_i = ln(Σ t_j^-d)`，`d` 取 ACT-R 默认/论文值，不自行拟合 | B1 改为“无来源不实现”，并加 ledger 门 |
| HyDE 怎么用 | 生成假设文档 → embedding → 检索真实语料；假细节靠向量邻域过滤 | B2 明确 shadow/A-B，不先改默认路径 |
| 层级摘要怎么做 | RAPTOR：递归 embed/cluster/summarize，多层级检索 | B3 先 episodic，不预设层数 |
| 多人群聊外部集 | GroupMemBench：说话人绑定、受众词汇、六类问题 | C3 升为外部记忆首选 |
| 中文人格外部集 | CharacterEval：77 角色、13 指标、CharacterRM | C4 用指标/协议，不直接套角色知识 |
| 证据身份 | `turn_id` 先取 `TurnOutcome.session_id`；`context_hash` 用 chat+audience+UTC day | A1 schema 固定 |
| 生命周期 | Beta 后验 + 2 独立情境；legacy 标 `legacy_unverified` | A2 可在 shadow 下安全上线 |
| 行为资格 | trait 只做“允许/不允许动作”，不做分值 | A5 不做行为权重 |

新增/修改的硬约束：

- `trait_evidence.quote` 不允许为空；
- 同一 `(trait_id, turn_id, polarity)` 只能一条；
- `context_hash` 未引入 topic 聚类，避免额外阈值；
- 任何新数值先登记 `docs/params/ledger.json`；
- ACT-R 的 `d`、RAPTOR 的层数/聚类参数、HyDE 的触发策略都必须有来源或工程数据。

### 9.1.1 参考链接

- Anderson & Schooler (1991), *Reflections of the environment in memory*: https://doi.org/10.1111/j.1467-9280.1991.tb00174.x
- ACT-R: https://act-r.psy.cmu.edu/
- Gao et al. (2022), HyDE: https://arxiv.org/abs/2212.10496
- Sarthi et al. (2024), RAPTOR: https://arxiv.org/abs/2401.18059
- GroupMemBench: https://arxiv.org/abs/2605.14498 ；数据 https://huggingface.co/datasets/kimperyang/GroupMemBench
- CharacterEval: https://arxiv.org/abs/2401.01275 ；代码 https://github.com/morecry/CharacterEval

---

## 10. 参数与证据规则

- 新增数值必须先登记 `docs/params/ledger.json`，否则不进代码；
- Beta(1,1)、0.5 决策边界、2 个独立情境：模型结构，不需要拟合；
- ACT-R `d`、层级/窗口、ANN 触发阈值：必须有论文或工程数据；
- 不新增 ranker 手调权重；
- 不新增真人测试；人工标签冻结。

---

## 11. 不做什么

- 不做代码自修改；
- 不做 prompt 结构自修改；
- 不做开放式价值观自生成；
- 不用 LLM judge 当门禁；
- 不在 204 条规模上做 ANN；
- 不为了“看起来自演化”而放大 7 维漂移。

---

## 12. 交付物

- 迁移与回填脚本；
- 新表/新 ranker/新生命周期；
- 单测 + 集成测试 + 回放报告；
- LongMemEval 500 / QA / abstention 报告；
- 更新后的审计、状态、参数账本；
- 每阶段一个可回滚提交。

---

## 13. 完成定义（DoD）

1. A1–A5 全部上线并有回放证据；
2. 至少一个外部人格/记忆 benchmark 可复现；
3. 隐私/边界无退化；
4. 所有新参数有来源；
5. 文档、账本、测试、回滚路径齐全；
6. 不依赖新增真人标注。

---

## 14. 执行记录

### 14.1 P0 证据账本（2026-11-01 已落地，shadow）

**代码**

- `src/echomind/domain/trait_evidence.py`：`TraitEvidence` 值对象；
- `src/echomind/domain/trait_evidence_ports.py`：窄端口 `ITraitEvidenceStore`；
- `src/echomind/adapters/storage/trait_evidence_repo.py`：append-only 仓储；
- `src/echomind/adapters/storage/migrations.py`：`trait_evidence` 表 + 索引；
- `src/echomind/mind/trait_evidence_writer.py`：quote / context_hash 提取；
- `src/echomind/mind/plasticity.py`：每次涌现 trait 写入支持证据；
- `src/echomind/mind/facade.py` / `core/bootstrap.py`：注入证据仓储。

**行为**

- 只写证据，不改 prompt、不改检索、不改 7 维；
- `trait_evidence` 唯一键 `(trait_id, turn_id, polarity)`，同一轮重复写被忽略；
- 现有 9 条 legacy trait 未回填（缺原文），保持原样，等 P1 标 `legacy_unverified`；
- 当前线上证据表为空，只有新 turn 产生新证据。

**验证**

- `tests/integration/test_trait_evidence_ledger.py`：roundtrip + dedupe + 真实 turn 写入；
- 架构门禁：`working_repo` 拆出证据仓储后回到 300 行内；`IWorkingStateStore` 保持 5 方法；
- 全门禁：**323 passed / 92%**，fusion 70/70。

**下一步**

- P1：给 `persona_traits` 加 status/context/state 字段，先 shadow 计算；
- 回填策略：无原文的 9 条一律 `legacy_unverified`，不伪造 quote。

### 14.2 P1 生命周期（2026-11-01 已落地，shadow）

**代码**

- `src/echomind/mind/trait_lifecycle.py`：`TraitEvidenceStats`、`assess_lifecycle`；
- `persona_traits` 新增：`status`、`active_since_ms`、`last_support_ms`、`last_contradiction_ms`、`state_n/state_mean/state_m2`；
- `trait_evidence_repo.refresh_lifecycle()`：按 distinct context 计算 Beta 后验并写状态；
- `plasticity._learn_traits()` 写证据后刷新生命周期。

**规则**

- `supports = distinct(context_hash, polarity=+1)`；
- `contradictions = distinct(context_hash, polarity=-1)`；
- 后验均值 `(1+s)/(2+s+c)`；
- `active`：`s >= 2` 且后验 `> 0.5`；
- `retired`：`c > 0` 且后验 `<= 0.5`；
- `candidate`：其余；
- `legacy_unverified`：无证据，或现有 9 条旧 trait。

**明确未做**

- `dormant` 暂不赋值：需要“多久算休眠”的来源/数据，不能拍 12h/7d；
- 状态尚未影响 prompt/检索；这是 shadow；
- 现有 9 条旧 trait 不回填、不伪造 quote。

**验证**

- `tests/unit/test_trait_lifecycle.py`：无证据/单情境/双情境/反证；
- `tests/integration/test_trait_evidence_ledger.py`：活跃→反证退休；
- 全门禁：**329 passed / 92%**，fusion 70/70。

### 14.3 P2 特质文本生成（2026-11-01 已落地，离线 shadow）

**代码**

- `src/echomind/domain/trait_candidate.py`；
- `src/echomind/domain/trait_candidate_ports.py`；
- `src/echomind/adapters/storage/trait_candidate_repo.py`；
- `trait_candidates` 表（trait_id + prompt_hash 唯一）；
- `src/echomind/mind/trait_generation.py`；
- `scripts/generate_trait_candidates.py`。

**规则**

- 只有 ≥2 个独立支持情境才调用 LLM；
- LLM 只输出 `category + trait_text + evidence_quotes`；
- `evidence_quotes` 每条必须是证据原文子串，否则存为 `rejected` 并记录原因；
- 候选只进 `trait_candidates`，**不进 prompt、不覆盖现有 5 条模板**；
- prompt hash 去重，重复生成不会重复插入；
- 脚本默认只处理 `status='active'` 的 trait。

**当前状态**

- 9 条旧 trait 仍是 `legacy_unverified`，没有候选；
- 脚本 dry-run 会明确输出“no active traits”；
- 还没有接 live；没有用假数据跑 LLM。

**验证**

- `tests/unit/test_trait_generation.py`：有效候选、伪造 quote 拒绝、单情境不调用 LLM；
- `tests/integration/test_trait_evidence_ledger.py`：候选表去重；
- 全门禁：**333 passed / 92%**，fusion 70/70。

### 14.4 P3 trait → 记忆（2026-11-01 已落地基础层，未接 live）

**代码**

- `src/echomind/domain/trait_memory_link.py`；
- `src/echomind/domain/trait_memory_ports.py`；
- `src/echomind/adapters/storage/trait_memory_repo.py`；
- `trait_memory_links` 表（trait/memory/relation 唯一）；
- `unified_rank(..., trait_scores=...)` 新增 `trait` ranker；
- `semantic_memory.rank_fused(..., trait_scores=...)` 透传。

**规则**

- 只有 `memory_kind='semantic'` 且 `relation='supports'` 的链接产生 ranker 分数；
- 分数只有 presence（1.0），没有手调权重；
- 链接按 trait/memory/relation 去重；
- **不自动建链**：当前没有可靠的 evidence→memory_id 映射，先保留人工/脚本显式链接；
- 未接 live：默认 `trait_scores` 为空，行为不变。

**验证**

- `tests/unit/test_trait_memory_ranker.py`：有 trait 分数时能排到目标；空分数无影响；
- `tests/integration/test_trait_memory_links.py`：链接去重、semantic/episodic 隔离；
- 全门禁：**336 passed / 92%**，fusion 70/70。

**未完成**

- 自动 evidence→memory 链接生产器；
- active trait 的 live 注入与 A/B；
- 隐私/边界回归。

### 14.5 P3b 精确链接生产器（2026-11-01 已落地，离线）

**代码**

- `src/echomind/domain/memory_quote_ports.py`；
- `src/echomind/adapters/storage/memory_quote_lookup.py`；
- `src/echomind/mind/trait_memory_linker.py`；
- `scripts/link_trait_memory.py`。

**规则**

- 只做 **`evidence.quote == memory.source_quote` 精确相等**；
- 不相似匹配、不按时间/主题猜、不设相似度阈值；
- semantic / episodic 各自建链；
- 支持 `--dry-run`，先审计再加链；
- 无匹配就跳过，不自作聪明。

**为什么这样保守**

现有 evidence 没有可靠的 `memory_id` 映射；  
P3a 的 `trait_memory_links` 需要可审计来源。精确 quote 是唯一不需要新阈值的关联。

**当前状态**

- 两个库 `trait_memory_links` 仍为 0；
- 链接器还没接 live；
- 没有用模糊匹配跑生产数据。

**验证**

- `tests/integration/test_trait_memory_linker.py`：精确命中 semantic + episodic，无关 quote 跳过，dry-run 不落库；
- 全门禁：**337 passed / 92%**，fusion 70/70。

### 14.6 P3c 端到端闭环验证（2026-11-01）

新增 `tests/integration/test_persona_self_evolution_loop.py`：

```
TurnOutcome(day1) ─┐
TurnOutcome(day2) ─┴→ trait evidence（2 独立 context）
                     → active
                     → semantic memory source_quote 精确匹配
                     → trait_memory_link
                     → trait ranker
                     → linked memory 排第一
```

同时修复：

- `evidence_context` 以前用“处理时间”的 UTC day，重放/补数据会把不同事件混成同一天；
- 现在优先用 `Percept.timestamp_ms` 的 UTC day，没有 trigger 时间才回退到当前时间。

**验证**

- 2 个独立情境 → `active`；
- 精确链接 1 条 semantic；
- 开 trait ranker 时 linked memory 第一；
- 全门禁：**338 passed / 92%**，fusion 70/70。

仍是离线闭环：没有接 live，没有自动提升 trait，没有跑真实 30 天数据。

### 14.7 30 天 synthetic replay（2026-11-01）

新增 `tests/integration/test_persona_30_day_replay.py`：

- 三条流：warm / offense / mixed；
- 每流 30 天，每天一个事件；
- 事件时间传给 `adapt_from_outcome(..., now_ms=event_ms)`；
- 日结算后检查 7 维仍在 `TRAIT_MAX_DEVIATION=12` 内；
- warm 长出 habit，offense 长出 taboo，mixed 两条都出现；
- 每条 active trait 有 30 个独立 context。

为支持 replay，给 `NeuroplasticityEngine.adapt_from_outcome()` 增加可选 `now_ms`；线上不传，仍用当前时间。  
这不是新参数，是事件时间入口。

**验证**

- replay 用时约 12.7s；
- 全门禁：**340 passed / 92%**，fusion 70/70。

**仍未做**

- 用真实 LLM 生成候选（P2 仍是离线脚本）；
- 接 live 的 trait ranker；
- 隐私/边界回归；
- 30 天结果目前是“结构一致性”，不是“人格更像真人”。

### 14.8 P4 行为资格（2026-11-01 已落地，shadow）

**代码**

- `src/echomind/mind/trait_action_eligibility.py`；
- `scripts/audit_trait_eligibility.py`。

**规则**

- 资格是集合，不是分数；
- active `taboo` → 只开放 `refusal`；
- active trait 的证据里 `quote_kind='tool'` 且 quote 是工具名 → 开放该工具；
- 没有证据/没有 trait → 不开放；
- 不读 `count/strength` 做权重。

**示例**

- 看到图 → 证据里 `look_at_image` → 允许 `look_at_image`；
- 被命令 → taboo → 允许拒绝；
- 不会因为“温柔 65”就凭空开放关心动作。

**当前状态**

- 纯函数 + 审计脚本；
- 没接 `explorer` / 主动行为仲裁；
- 没接 live；
- 现有 9 条 legacy trait 没有 active，所以输出为空。

**验证**

- `tests/unit/test_trait_action_eligibility.py`：taboo、tool、空集；
- 全门禁：**343 passed / 92%**，fusion 70/70。

### 14.9 P4b shadow 决策日志（2026-11-01 已落地）

**代码**

- `trait_action_shadow` 表；
- `TraitShadowRecord` / `ITraitShadowStore` / `IActiveTraitReader`；
- `SqliteTraitShadowStore`；
- `TraitShadowService`；
- `CognitiveCoreFacade.on_turn_completed` 在塑性回流后记录；
- bootstrap 注入。

**规则**

- 每轮记录：active trait ids、allowed tools、allow_refusal、actual tools、sent_count；
- 只记录，不改行为、不阻断回合；
- 记录失败只写 warning，不影响回复；
- 没有 active trait 时仍记空行，便于对比“本可以允许什么”。

**验证**

- `tests/integration/test_trait_shadow_log.py`：active taboo + tool evidence → allowed/actual 都落库；
- 全门禁：**344 passed / 92%**，fusion 70/70；
- 两个服务重启后 200。

**当前状态**

- 线上 9 条 legacy trait 仍非 active，所以 shadow 行会是空 trait_ids；
- 还没有用真实流量做统计；
- 还没有把 eligibility 接进行为仲裁。

### 14.10 30 天 shadow benchmark（2026-11-01）

新增 `scripts/persona_replay.py`，输出 `eval/baselines/persona-replay-30d-2026-11-01.json`。

| 流 | active trait | shadow 行 | allowed tools | actual tools | 允许拒绝行 | max drift |
|---|---|---:|---|---|---:|---:|
| warm | habit | 30 | `look_at_image` | `look_at_image` | 0 | 0.39 |
| offense | taboo | 30 | 空 | 空 | 29 | 0.39 |
| mixed | taboo + habit | 30 | `look_at_image` | `look_at_image` | 28 | 0.195 |

解读：

- warm 的工具资格和实际使用一致；
- offense 从第 2 天起允许拒绝（29/30），第 1 天仍是 candidate；
- mixed 两条 trait 并存；
- 三条流 7 维偏离都远低于 12 点边界；
- 30 天 replay 约 13.5s。

同时修了证据优先级：

```
assistant text > tool > user trigger
```

否则“有工具但无助手文本”的回合会把工具证据记成用户触发词，P4 资格永远看不到工具。

**验证**

- `tests/unit/test_trait_evidence_writer.py`；
- 全门禁：**347 passed / 92%**，fusion 70/70。

### 14.11 90 天 replay（2026-11-01，192.168.3.2）

在远程服务器运行 `scripts/persona_replay.py --days 90`，产物：

`eval/baselines/persona-replay-90d-2026-11-01.json`

| 流 | active trait | shadow 行 | allowed/actual | 允许拒绝 | max drift |
|---|---|---:|---|---:|---:|
| warm | habit | 90 | `look_at_image` 一致 | 0 | 1.141 |
| offense | taboo | 90 | 空 | 89/90 | 1.141 |
| mixed | taboo + habit | 90 | `look_at_image` 一致 | 88/90 | 0.571 |

对比 30 天：

| 流 | 30 天 drift | 90 天 drift |
|---|---:|---:|
| warm | 0.39 | 1.141 |
| offense | 0.39 | 1.141 |
| mixed | 0.195 | 0.571 |

结论：

- 漂移随天数增长，但 90 天仍只有边界的 **9.5%**；
- trait 结构没有跑偏；
- offense/ mixed 的拒绝资格因为第一天是 candidate，分别从第 2/第 3 天才生效；
- 远程 90 天约 **8.75s**，不占本机。

**限制**

- 合成流，不是真实聊天；
- 只验证结构一致性，不验证真人感；
- 没有接 live 行为仲裁。

### 14.12 真实 LLM 候选生成 benchmark（2026-11-01）

`scripts/replay_trait_candidates.py` 先把 warm/offense/mixed replay 到 active trait，再调真实 LLM 生成候选。

产物：`eval/baselines/persona-replay-candidates-2026-11-01.json`

| 流 | trait | 生成候选 | 校验 |
|---|---|---|---|
| warm | habit | 她在查看图片时倾向于注意到并指出图中的小槽点。 | candidate |
| offense | taboo | 当别人用命令语气使唤她时，她会直接表示拒绝。 | candidate |
| mixed | taboo | 当别人用命令语气使唤她时，她会明确拒绝并强调不要这样对她。 | candidate |
| mixed | habit | 她在查看内容时倾向于多次打开或查看图片。 | candidate |

- 4/4 通过 quote 校验，0 rejected；
- 单条生成耗时约 6–9s/流；
- 候选只进 `trait_candidates`，未进 prompt；
- 文本仍偏通用，需要后续做“去模板化/具体化”评估，不能因为校验通过就认为真人感提升。

**新增**

- `scripts/replay_trait_candidates.py`；
- `scripts/__init__.py`（让 replay 可被候选脚本导入）；
- `eval/baselines/persona-replay-candidates-2026-11-01.json`。

**验证**

- 全门禁：**347 passed / 92%**，fusion 70/70。

### 14.13 候选质量评估与结构门槛（2026-11-01）

新增 `scripts/evaluate_trait_candidates.py`，每条 active trait 重复生成 3 次：

产物：`eval/baselines/persona-candidate-eval-2026-11-01.json`

| 流/trait | 有效/次数 | exact match | 平均 Jaccard | 证据 bigram 覆盖 | 模板最大相似 |
|---|---:|---:|---:|---:|---:|
| warm/habit | 3/3 | 0.333 | 0.522 | 0.068 | 0.083 |
| offense/taboo | 3/3 | 0.667 | 0.717 | 0.194 | 0.175 |
| mixed/taboo | 3/3 | 0.333 | 0.502 | 0.194 | 0.163 |
| mixed/habit | **0/3** | — | — | — | — |

**关键发现**

- mixed 的 habit 证据只有 `look_at_image` 工具名；LLM 只能生成“反复查看图片”这种空泛文本。
- 因此新增结构门槛：**至少一条非 tool 的行为/话语证据才允许生成候选**。
- 这不是分数阈值，而是证据类型要求：工具名只能证明“允许动作”，不能证明“人格怎么说话”。

**晋升**

- 仍然没有自动 promoted；
- 候选必须人工/后续协议审核；
- 质量指标只报告，不做加权总分。

**验证**

- `tests/unit/test_trait_generation.py`：tool-only 不调用 LLM；
- 全门禁：**348 passed / 92%**，fusion 70/70。

### 14.14 晋升协议（2026-11-01 已落地，显式人工）

**代码**

- `src/echomind/mind/trait_promotion.py`；
- `trait_candidates` 新增 `promoted_by / promote_reason / promoted_ms`；
- `SqliteTraitCandidateStore.get_candidate()/promote_candidate()`；
- `scripts/promote_trait_candidate.py`。

**自动审查**

- candidate 状态；
- ≥2 个独立支持 context；
- 至少一条非 tool 的行为/话语证据。

**显式晋升**

- 必须 `--approve`；
- 必须提供 `--reason`；
- 只把 `trait_candidates.status` 改为 `promoted`；
- **不写 `persona_traits`、不改 prompt、不进检索**；
- 重复晋升返回 false。

**为什么不是自动**

当前没有可靠的人格质量 ground truth；  
quote 校验/结构审查只能证明“不是编的”，不能证明“像真人”。  
所以 `promoted` 只是审计状态，不是上线开关。

**验证**

- `tests/unit/test_trait_promotion.py`：eligible / tool-only / one context / promoted；
- 集成测试：晋升审计、重复晋升拒绝；
- 全门禁：**352 passed / 92%**，fusion 70/70。

### 14.15 晋升后的 shadow prompt 对比（2026-11-01）

新增：

- `src/echomind/mind/trait_prompt_shadow.py`；
- `scripts/compare_promoted_candidate_prompt.py`；
- `tests/unit/test_trait_prompt_shadow.py`；
- `eval/baselines/persona-prompt-shadow-2026-11-01.json`。

规则：

- 只接受 `status='promoted'` 的候选；
- 用同一组 7 维参数和 traits，仅把目标 trait 文本替换成候选；
- 渲染两份完整人格指令；
- 不写 `persona_traits`、不改 prompt、不进检索。

synthetic 结果：

| 项 | 值 |
|---|---:|
| old directive | 1170 字 |
| new directive | 1164 字 |
| delta | -6 |
| candidate in old | False |
| candidate in new | True |

说明候选确实只替换了 trait 行，长度变化可量化。  
仍需用真实 candidate 做 shadow，不是直接上线。

**验证**

- 单测覆盖“只替换目标 trait”；
- 全门禁：**353 passed / 92%**，fusion 70/70。

### 14.16 完整离线链路（2026-11-01）

新增 `scripts/replay_full_trait_chain.py`：

```
30 天 replay → active trait → 真实 LLM 候选 → quote 校验
→ 结构审查 → 显式 --approve-promotion → shadow prompt diff
```

产物：`eval/baselines/persona-full-chain-2026-11-01.json`

| 流 | 候选 | review | promote | prompt delta |
|---|---|---|---|---:|
| warm | 在查看图片时，她倾向于确认并说出自己看到了图中的小槽点。 | eligible | true | **-2** |
| offense | 当别人用命令语气使唤她时，她会直接拒绝并明确要求对方不要这样。 | eligible | true | **+7** |

- 两条都通过 quote 校验、结构审查、显式晋升；
- 候选只替换目标 trait 行；
- 旧指令中不含候选，新指令中含候选；
- 单次全链路约 **4.4s**；
- 全程临时库，**不写线上 persona_traits / prompt / 检索**。

**重要边界**

这条链路证明“可以走通”，不证明“候选更好”。  
目前仍缺：真实经历分布、真人感评估、live A/B。

**验证**

- 全门禁：**353 passed / 92%**，fusion 70/70。

> 单样本结果只作为现象记录；结论以 14.18 的重复测量为准。

### 14.17 shadow prompt A/B（2026-11-01，单样本；已被 14.18 重复测量取代）

`scripts/shadow_prompt_ab.py`：

- 同一 warm replay、同一 7 维、同一 6 个场景；
- 只替换 trait 行；
- 旧/新各生成 1 条回复；
- 指标只用确定性文本特征（26 字为人工校准上限）。

产物：`eval/baselines/persona-prompt-ab-2026-11-01.json`

| 指标 | 旧 | 新 | 差值 |
|---|---:|---:|---:|
| 平均长度 | 17.5 | 23.7 | **+6.2** |
| >26 字比例 | 0.000 | 0.167 | +0.167 |
| 解释词比例 | 0.000 | 0.000 | 0 |
| 括号动作比例 | 0.000 | 0.000 | 0 |
| 多问句比例 | 0.000 | 0.000 | 0 |

候选：

> 在查看图片时，她倾向反复确认并说出自己看到了图中的小槽点。

**解读**

- 单样本下，新候选让回复平均长 6.2 字，出现 1/6 超 26 字；
- 没有解释词/括号动作差异；
- **不能据此说更好或更差**：每个场景只有 1 次生成，随机性未控制；
- 下一步必须做 repeats + 更大场景集，才能判断是否稳定。

**验证**

- 全门禁：**353 passed / 92%**，fusion 70/70。

### 14.18 重复测量 shadow A/B（2026-11-01）

`scripts/shadow_prompt_ab.py` 升级：

- 6 类 × 2 个场景 = 12 个场景；
- 每场景 3 次生成；
- **36 对配对样本**；
- bootstrap 95% 区间（固定种子 42，纯评测方法，不是模型参数）；
- 不使用 LLM judge。

结果（候选：在查看图片时，她倾向于反复指出自己看到了图中的小槽点）：

| 指标 | 旧均值 | 新均值 | 配对差值 | 95% CI |
|---|---:|---:|---:|---:|
| 平均长度 | 20.3 | 21.1 | +0.75 | [-1.556, 3.000] |
| >26 字比例 | 0.083 | 0.167 | +0.083 | [-0.028, 0.194] |
| 解释词比例 | 0 | 0 | 0 | [0, 0] |
| 括号动作比例 | 0 | 0 | 0 | [0, 0] |
| 多问句比例 | 0.056 | 0.056 | 0 | [-0.111, 0.111] |

**结论**

- 长度和长句比例的 CI 都跨 0；
- 没有证据表明候选更好或更差；
- 不能晋升为 prompt 默认；
- 这次只是“可判断”，不是“通过”。

评测耗时约 **2m20s**（72 次生成）。

**验证**

- 全门禁：**353 passed / 92%**，fusion 70/70。

### 14.19 20×5 shadow A/B（2026-11-01）

`--scenarios 20 --repeats 5`，共 **100 对**，场景级均值 + bootstrap（不把同场景重复当独立样本）。

| 指标 | 旧 | 新 | 配对差值 | 95% CI |
|---|---:|---:|---:|---:|
| 平均长度 | 20.4 | 19.2 | -1.22 | [-2.58, 0.11] |
| >26 字比例 | 0.150 | 0.060 | **-0.09** | **[-0.16, -0.02]** |
| 解释词比例 | 0 | 0 | 0 | [0, 0] |
| 括号动作比例 | 0 | 0 | 0 | [0, 0] |
| 多问句比例 | 0.05 | 0.06 | +0.01 | [-0.03, 0.06] |

**结论**

- 长句率下降的 95% CI 不含 0，是一个真实信号；
- 平均长度 CI 跨 0，不能说整体显著变短；
- 解释词/括号动作/多问句无差异；
- 但旧/新指令只差 7 字，候选 trait 文本本身更短，存在**提示长度混淆**；
- 不能据此晋升；下一步要做长度匹配对照，并测多个候选。

评测耗时约 **6m22s**（200 次生成）。

**验证**

- 全门禁：**353 passed / 92%**，fusion 70/70。

### 14.20 长度匹配对照（2026-11-01）

为排除提示长度伪影，把候选 trait 行用**全角空格**补到与旧 trait 指令等长：

- 旧/新指令均为 **1174 字**；
- 20 场景 ×5 次 = 100 对；
- 场景级 bootstrap；
- 只做字符级控制（空白可能被 tokenizer 忽略，这是限制）。

| 指标 | 旧 | 新 | 配对差值 | 95% CI |
|---|---:|---:|---:|---:|
| 平均长度 | 21.5 | 20.7 | -0.76 | [-1.98, 0.47] |
| >26 字比例 | 0.22 | 0.17 | -0.05 | **[-0.13, 0.04]** |
| 解释词比例 | 0.01 | 0.00 | -0.01 | [-0.03, 0.00] |
| 括号动作比例 | 0 | 0 | 0 | [0, 0] |
| 多问句比例 | 0.02 | 0.04 | +0.02 | [-0.02, 0.07] |

**结论**

- 长度匹配后，14.19 的长句率显著下降**消失**；
- 差值 CI 跨 0；
- 因此之前的信号**不能归因于候选语义**，主要是提示长度伪影；
- 候选不晋升、不接 live。

**限制**

- 这是字符级长度控制，不是 token 级；
- 但足以拒绝“候选语义让长句率下降”的强结论。

**验证**

- 全门禁：**353 passed / 92%**，fusion 70/70。

### 14.21 多候选 pilot（2026-11-01）

同一 active trait 采 3 个候选（默认 LLM 采样温度，去重后 3 条），
8 场景 ×2 次，每个候选都与旧模板做**长度匹配**的配对 A/B。

产物：`eval/baselines/persona-multi-candidate-2026-11-01.json`

| 候选 | 长度 delta | 95% CI | 长句 delta | 95% CI |
|---|---:|---:|---:|---:|
| 她在查看图片时，倾向于注意到并说出图里的小槽点。 | +1.438 | [-0.375, 2.875] | 0 | [-0.188, 0.188] |
| 在查看图片时，她倾向于指出图中注意到的小槽点。 | -0.500 | [-3.062, 2.188] | 0 | [0, 0] |
| 她在查看图片时倾向于注意到并说出图中的小槽点。 | +0.125 | [-3.125, 3.625] | +0.062 | [-0.125, 0.250] |

- 3/3 候选的长度、长句 CI 都跨 0；
- 第二个候选多问句 +0.125，但 CI 下界正好 0，不构成稳定效应；
- 没有任何候选通过“稳定改善”的门槛；
- 不晋升、不接 live。

**结论**

单候选路线和多候选 pilot 都没有证明候选能改善真人感风格。  
下一步不应继续堆 A/B，而应改 **trait 生成策略**（更具体的行为/情境证据、非空泛总结），或把 trait 只用于“想起什么/允许什么”，不强行让它改说话长度。

**验证**

- 全门禁：**353 passed / 92%**，fusion 70/70。

### 14.22 结构化 trait 签名（2026-11-01）

之前的候选是自由总结，容易出现“倾向于注意到”这类空泛句。  
现在强制 LLM 输出 **CAPS if-then 签名**：

```json
{
  "category": "...",
  "trait_text": "...",
  "signature": {
    "situation": "什么情境",
    "behavior": "她怎么做",
    "result": "结果/感受"
  },
  "evidence_quotes": ["..."]
}
```

结构校验：

- 三个字段都必须非空；
- 缺任一字段 → rejected；
- quote 仍需逐字来自证据；
- 至少一条非 tool 的行为/话语证据。

存储：

- `trait_candidates.signature_json`；
- `TraitSignature` 值对象；
- 旧候选没有签名可为空，但新生成必须通过。

真实 LLM smoke：

```text
text: 在查看图片时，她倾向于反复指出并确认图中的小槽点。
signature.situation: 查看图片时
signature.behavior: 反复说“我看到图里那个小槽点了”并继续查看图片
signature.result: 形成反复确认小槽点的行为模式
```

比之前多出明确的行为/结果，但仍偏“行为模式总结”，需要后续 A/B 验证，不能直接晋升。

**验证**

- 全门禁：**354 passed / 92%**，fusion 70/70。

### 14.23 结构化签名候选 A/B（2026-11-01）

12 场景 ×3 次，长度匹配（两份指令 1174 字）。

| 指标 | 旧 | 新 | 配对差值 | 95% CI |
|---|---:|---:|---:|---:|
| 平均长度 | 20.8 | 21.3 | +0.556 | [-1.472, 2.500] |
| >26 字比例 | 0.139 | 0.139 | 0 | [-0.139, 0.139] |
| 解释词比例 | 0 | 0 | 0 | [0, 0] |
| 括号动作比例 | 0 | 0 | 0 | [0, 0] |
| 多问句比例 | 0 | 0 | 0 | [0, 0] |

候选：

> 在查看图片时，她倾向反复确认并报告自己看到了图中的小槽点。

**结论**

- 带 situation/behavior/result 的候选没有产生稳定风格差异；
- 长句率完全相同；
- 结构更完整 ≠ 表达更像真人；
- **停止用“候选 trait 文本直接改 prompt 风格”这条路线**；
- 候选不晋升、不接 live。

下一步不再跑同类 A/B，转向：

1. trait → 记忆检索（想起什么）；
2. trait → 行为资格（允许什么）；
3. 真人感交给独立的风格约束，不再让 trait 文本承担。

**验证**

- 全门禁：**354 passed / 92%**，fusion 70/70。

### 14.24 trait→记忆接入 live retriever（2026-11-01）

**代码**

- `SemanticMemoryRetriever` 新增可选：
  - `trait_reader: IActiveTraitReader`
  - `trait_links: ITraitMemoryLinkStore`
- `active_trait_scores()`：只取 active trait，再查 supports 链接；
- `rank_fused()` 把 scores 传给 `unified_rank(..., trait_scores=...)`；
- `main._wire_semantic` 注入 `SqliteTraitShadowStore` + `SqliteTraitMemoryLinkStore`。

**默认行为**

- 线上 9 条 legacy trait 不是 active；
- `trait_memory_links` 为 0；
- 因此 `trait_scores={}`，RRF 行为与之前一致；
- fusion 仍 70/70。

**验证**

- `tests/unit/test_semantic_memory.py`：
  - active trait 分数注入；
  - 无 reader/links 返回空；
- 全门禁：**356 passed / 92%**，fusion 70/70。

**边界**

- 只有 active + exact source_quote link 才生效；
- 没有自动建链/晋升；
- 真实流量生效前仍需真实 active trait。

### 14.25 live retriever 端到端 tie-break（2026-11-01）

新增 `tests/integration/test_live_trait_retrieval.py`：

- 构造两条事实，让其余 ranker 形成 3:3 平票；
- 无 trait 时 distractor 因 id 顺序排第一；
- 有 active trait + 精确 memory link 时，linked fact 多一个 trait ranker，排第一；
- 证明 live `SemanticMemoryRetriever.rank_fused` 的接线真的改变排序，不是只传空 map。

测试耗时约 4.7s。

**验证**

- 全门禁：**357 passed / 92%**，fusion 70/70。

**边界**

- 这是受控 tie-break，不是真实流量；
- 隐私/secret 硬门在 retrieval 之外，尚未在这个测试里覆盖；
- 没有自动建链/晋升。

### 14.26 trait ranker 隐私回归（2026-11-01）

新增 `tests/integration/test_trait_memory_privacy.py`：

1. **secret**：
   - public + secret 两条事实；
   - trait link 同时指向两条；
   - `gate_frame` 先丢 secret；
   - `select_facts` 只能看到 public，secret 不会因 ranker 回来。

2. **private**：
   - owner 不在 audience → 丢弃；
   - owner 在 audience → 保留。

结论：

- 硬门在 `select_facts` 之前；
- trait ranker 不能绕过 private/secret；
- 隐私边界没有被自演化通道打开。

**验证**

- 全门禁：**359 passed / 92%**，fusion 70/70。

**边界**

- 没测跨 venue 的链接隔离；链接本身没有 venue 字段；
- 没测 grant 后的 secret 传播；
- 这些仍属于披露模型/GroupMemBench 工作流。

### 14.27 跨 venue 链接隔离（2026-11-01）

`trait_memory_links` 没有 `venue_id`，先验证是否真的需要：

- 语义事实/情节记忆的 `id` 是**全局 AUTOINCREMENT**；
- 链接器按 `chat_key + source_quote` 精确查记忆；
- 检索时只拿当前 venue 的 facts，`unified_rank` 会按现成 facts 过滤 ranker 分数。

新增测试 `test_linker_does_not_cross_venue`：

- group g 和 group h 有相同 `source_quote` 的两条事实；
- trait 属于 g；
- 链接器只生成 g 的 1 条链接；
- h 的 memory_id 不出现。

**结论**

- 当前不需要给 link 加 `venue_id`；
- 跨 venue 由“事实 ID 全局唯一 + 链接器 chat_key 过滤 + 检索只传当前 facts”共同保证；
- 若未来 ID 复用或跨库合并，再补 venue 字段。

**验证**

- 全门禁：**360 passed / 92%**，fusion 70/70。

### 14.28 真实数据首查（2026-11-01）

新增只读审计 `scripts/trait_evolution_status.py`：

产物：`eval/baselines/trait-live-status-2026-11-01.json`

主库 `data/echomind.db`：

| 项 | 值 |
|---|---:|
| trait | 9 |
| candidate | 1（trait 45） |
| legacy_unverified | 8 |
| ledger evidence | 1 |
| 该 trait 独立 context | 1 |
| cached evidence_count | 4 |
| shadow rows | 12 |
| shadow 非空 trait_ids | 0 |
| links | 0 |
| candidates | 0 |

- trait 45 只有 **1 个可审计 context**，不够 active；
- 12 条 shadow 的 trait_ids 全空，actual tools 只有 `feiyu_say`；
- 旧 `evidence_count=4` 是历史缓存，不能当 4 个独立证据；
- 小沫库没有真实 trait/shadow/link；
- **turn_traces 里有 156 条真实 `look_at_image` 回合**，trait 45 的旧 `evidence_count=4` 不是凭空来的；
- 但这些旧回合没有进入 `trait_evidence`，因为 ledger 是后加的，不能直接当独立 context。

**下一步不是等新数据**：从 turn_traces 回填真实 image 证据（quote 取 steps_json 的 LLM 输出，context 用事件日），先 dry-run 审计，再决定是否写入。禁止用合成 quote。

**结论**

- 真实证据密度不够，不能靠旧计数“假装 active”；
- 不回填无 quote 的旧证据；
- 需要一个**新的独立图片/视频情境**，或更稳定的证据写入；
- 在此之前，trait ranker/资格在线上保持空跑。

**验证**

- 全门禁：**360 passed / 92%**，fusion 70/70。

### 14.29 真实 trace 回填与首个 active trait（2026-11-01）

`turn_traces` 里有 156 条真实 `look_at_image` 回合。  
回填规则收紧为：

- quote **只取真实发送工具**（`send_message`/`feiyu_say`/`feiyu_cover`）的文本；
- 不用 LLM 中间输出（避免把内心独白当证据）；
- 每个 UTC 日只取一个 context；
- 已有 context 的日期跳过；
- 先 dry-run，再 `--apply`。

dry-run 结果：

- 2 条可回填的真实发送文本；
- 加上原有 1 个 context → 3 个独立 context。

执行后：

```text
trait 45 status=active
ledger_rows=3
distinct_contexts=3
```

这是第一个**真实数据驱动**的 active trait，不是合成 replay。

但：

- `trait_memory_links` 精确匹配为 0（semantic=0, episodic=0）；
- 所以 trait ranker 仍然不生效；
- shadow 历史 12 行仍是空，下一次真实回合才会记录非空 trait_ids。

**验证**

- 全门禁：**363 passed / 92%**，fusion 70/70；
- 参数账本：**59 compliant**（新增 `DAY_MS` 单位换算）。

### 14.30 因果链接：evidence 携带当轮 memory_ids（2026-11-01）

真实数据验证：episodic `source_quote` 为空，exact quote 链接自然为 0。  
不再用模糊阈值，改为**因果建链**：

- `TraitEvidence` 新增 `memory_ids`；
- `trait_evidence.memory_ids_json`；
- `CognitiveCoreFacade.on_turn_completed` 把本轮 `included` 的 fact_id 传给塑性引擎；
- `NeuroplasticityEngine._record_evidence` 在写 evidence 后，对每个 memory_id 建 `semantic/supports` link。

这样链接代表“这条特质是在想起这些记忆的回合里形成的”，而不是事后相似匹配。

**当前**

- trait 45 已 active，但旧 evidence 没有 memory_ids；
- 旧 exact-quote 链接仍为 0；
- 新回合才会产生因果链接；
- 未自动晋升/未改 prompt。

**验证**

- `tests/integration/test_trait_evidence_ledger.py`：included memory_id → causal link，重复不重复建；
- 全门禁：**364 passed / 92%**，fusion 70/70。

### 14.31 evidence 计数漂移修复（2026-11-01）

真实审计发现：

- trait 45 缓存 `evidence_count=4`；
- ledger 实际 3 条。

原因：`sync_persona_traits` 双写计数，回填/账本写入不会同步缓存。

修复：

- `refresh_lifecycle` 更新 `evidence_count / contradiction_count` 时，直接从 `trait_evidence` 聚合；
- 真实 trait 45 刷新后：`active, evidence_count=3, contradiction_count=0`；
- 测试断言状态/时间/计数一起正确。

**验证**

- 全门禁：**364 passed / 92%**，fusion 70/70。

### 14.32 trait 健康监控（2026-11-01）

新增 `scripts/trait_evolution_health.py` + `mind/trait_health.py`。

状态：

- `no_active`：没有 active trait；
- `waiting_turn`：active 存在，但 active 后没有新回合；
- `shadow_missing_trait`：有 shadow 行但 trait_ids 为空（代码问题）；
- `no_causal_links`：已有非空 shadow，但没有 causal link；
- `ok`：全链路有数据。

当前真实状态：

```text
status=waiting_turn
active_traits=1
shadow_since_activation=0
nonempty_shadow=0
causal_links=0
```

**特点**

- 不引入“多久算异常”的时间阈值；
- `--check` 只在 `shadow_missing_trait` 时返回非零；
- 等待真实流量时不会误报故障。

**验证**

- `tests/unit/test_trait_health.py` 5 个状态；
- 全门禁：**369 passed / 92%**，fusion 70/70。

### 14.33 健康快照（2026-11-01 02:38）

`trait_evolution_health.py` 新增 `--out`，把监控状态落盘：

`eval/baselines/trait-health-2026-11-01.json`

当前：

```text
status=waiting_turn
active_traits=1
shadow_since_activation=0
nonempty_shadow=0
causal_links=0
```

最近消息/轨迹停在 **02:24:45**，之后没有真实回合。  
不伪造 shadow/link，不重复合成实验；等新回合后直接跑 `--check` 对比。

**验证**

- 全门禁沿用：**369 passed / 92%**，fusion 70/70。

### 14.34 active-only prompt 影响（2026-11-01）

新增 `scripts/trait_prompt_impact.py`。

真实主库：

| 项 | 值 |
|---|---:|
| 当前 traits | 9 |
| active traits | 1 |
| 当前 prompt | 1367 字 |
| active-only prompt | 1181 字 |
| delta | -186 |

会移除 8 条 legacy trait，包括：

- 讨厌被命令使唤（taboo）；
- 情绪上来会发语音；
- 熬夜赖床；
- 被说偷懒会反驳；
- 困了直说；
- 还有 3 条“嘴硬心软/记小账本”类习惯。

**结论**

- 现在切 active-only 会丢掉 8 条未迁移的真实人格；
- 不能因为 trait 45 active 就切；
- 需要先给 legacy trait 做证据迁移（或明确保留策略）；
- 当前 prompt 继续显示全部 traits。

**验证**

- 全门禁：**369 passed / 92%**，fusion 70/70。

### 14.35 legacy trait 迁移审计（2026-11-01）

8 条 legacy trait 中，有真实 trace 支持的只有：

| id | trait | 真实来源 |
|---|---|---|
| 45 | 看到群友发图会看细节 | `look_at_image`，已 active |
| 66 | 情绪上来会直接发语音 | `feiyu_say`，187 条 trace，已 active |

trait 66 dry-run 找到 4 个独立日 context，真实发送文本例如：

- “主人别生气嘛……这条语音送你……”
- “那我睡啦，你也早睡，别又熬到天亮”

执行后：

```text
trait 66: active, evidence=4, contexts=4
health: active_traits=2, waiting_turn
```

其余 6 条：

- 无 `source` 或无可结构化工具；
- 不做关键词硬套、不伪造 quote；
- 保持 `legacy_unverified`，prompt 继续显示。

active-only prompt 影响：

| 项 | 值 |
|---|---:|
| 当前 prompt | 1367 字 |
| active-only | 1222 字 |
| delta | -145 |
| 仍会移除 | 7 条 legacy（含 taboo） |

所以 active-only 仍不能开。

**验证**

- 全门禁沿用：**369 passed / 92%**，fusion 70/70。

### 14.36 facade 全链路测试（2026-11-01）

新增 `tests/integration/test_trait_shadow_facade.py`：

- 临时 `EchoMindContainer`；
- 手工把 trait 45 同文案推到 active；
- 写入一个 included semantic fact；
- 调用真实 `CognitiveCoreFacade.on_turn_completed`；
- 验证：
  - `trait_action_shadow` 记录 active trait id；
  - `trait_memory_links` 记录该 fact 的 causal link。

这不是只测子函数，而是走真实 facade 回合完成路径。  
测试 0.38s，不依赖真实流量。

**验证**

- 全门禁：**370 passed / 92%**，fusion 70/70。

### 14.37 trait health 控制台 API（2026-11-01）

新增只读：

```text
GET /api/mind/trait-health
```

返回：

```json
{
  "ok": true,
  "status": "waiting_turn",
  "active_traits": 2,
  "shadow_since_activation": 0,
  "nonempty_shadow": 0,
  "causal_links": 0,
  "latest_turn_ms": 1793471085391
}
```

实现：

- 查询逻辑放到 `web/trait_health_service.py`；
- `mind_inspector_service` 仍保持 <300 行；
- 不改人格/prompt/retrieval。

当前真实：

- active_traits=2；
- active 后无新回合；
- waiting_turn，不是故障。

**验证**

- 全门禁：**370 passed / 92%**，fusion 70/70。

### 14.38 prompt 生命周期可见性修复（2026-11-01）

发现：

- `PersonaTrait` 没有 `status`；
- `synthesize_live_persona_directive` 直接渲染 `sync_persona_traits()` 返回的所有 trait；
- 结果：`candidate`/`retired` 也可能提前进入 prompt。

修复：

- `PersonaTrait.status` 增加；
- `sync_persona_traits` 查询并返回 status；
- prompt 只显示：
  - `active`
  - `legacy_unverified`

不显示：

- `candidate`
- `dormant`
- `retired`

当前真实库仍是 9 条（2 active + 7 legacy），所以线上 prompt 内容不变；  
但未来候选不会在晋升前偷偷改人格。

**验证**

- 新增测试：active/legacy 可见，candidate/retired 不可见；
- 全门禁：**371 passed / 92%**，fusion 70/70。

### 14.39 trait 列表生命周期字段（2026-11-01）

`GET /api/mind/traits` 现在返回：

- `status`
- `evidence_count`
- `contradiction_count`

不再只有 id/category/text/strength。  
这样控制台能直接区分 active 与 legacy，看到证据数，不用猜。

当前真实主库：

- 2 active；
- 7 legacy_unverified；
- 0 candidate/retired。

**验证**

- Web 测试断言 status/evidence 字段；
- `mind_inspector_service.py` 保持 300 行；
- 全门禁：**371 passed / 92%**，fusion 70/70。

### 14.40 trait evidence 控制台 API（2026-11-01）

新增只读：

```text
GET /api/mind/traits/{trait_id}/evidence
```

返回：

- quote
- quote_kind
- polarity
- context_hash
- memory_ids
- created_ms

可直接审计 active trait 的真实证据。当前：

- trait 45：3 条；
- trait 66：4 条；
- 全部来自真实发送文本；
- 旧证据 memory_ids 为空，所以 link 仍为 0。

**验证**

- Web 测试断言新 endpoint；
- `create_web_app` 保持 ≤40 行；
- 全门禁：**371 passed / 92%**，fusion 70/70。

### 14.41 真实流量暴露的 trait 学习根因（2026-11-01）

真实 8 小时后：

```text
shadow_since_activation=10
nonempty_shadow=10
causal_links=0
status=no_causal_links
```

shadow 正常记录 `[45,66]`，但 evidence/link 一直不写。

根因：

- `adapt_from_outcome` 在 `compute_param_deltas(outcome)` 为空时直接 `return ()`；
- 中性回合、只发消息/语音的回合参数增量为空，于是 `_learn_traits` 完全不执行；
- 所以 trait 不会被真实回合强化，也不会有 memory_ids/link。

修复：

- 删除早退；
- 参数增量循环照常执行（可能为空）；
- `_learn_traits` 每回合都执行。

新增测试：

- 中性 outcome（无 triggers、social_reward=0）也会写 trait evidence。

**验证**

- 全门禁：**372 passed / 92%**，fusion 70/70。

### 14.42 真实链接质量修正：context vs supports（2026-11-01）

真实 `feiyu_say` 回合第一次产生：

```text
shadow=25
trait 66 evidence 新增 1 条
memory_ids=25
links=25
```

但逐条检查后发现，这 25 条都是当轮 included 的**群友资料/琐事**，与“情绪上来会发语音”习惯没有支持关系。

问题：

- “当轮 included”只能证明**上下文**，不能证明**支持**；
- 自动把它们全部建成 `supports`，会让 trait ranker 对所有记忆等权加分，失去区分度。

修复：

- `TraitMemoryLink.is_context`；
- 真实回合自动链接标记 `is_context=True`；
- `ranker_scores` 只取 `relation='supports' AND is_context=0`；
- 历史 25 条改为 context；
- `trait_health.causal_links` 只数 support 链接。

结果：

```text
context links=25
support links=0
status=no_causal_links
```

这是正确的：有上下文证据，但没有被证明的 support 链接。  
不再用“全部 included”冒充 trait→记忆支持。

**验证**

- 全门禁：**372 passed / 92%**，fusion 70/70。

### 14.43 精确 support：source_turn_id（2026-11-01）

context 链接不能当 support；新增精确来源：

- `SemanticFact.source_turn_id`；
- `_extract_explicit_fact` 写入当前 `outcome.session_id`；
- `SqliteTraitMemoryLinkStore.link_turn_support(chat_key, turn_id)`：
  - 只连接 `semantic_facts.source_turn_id = trait_evidence.turn_id`；
  - `relation='supports'`、`is_context=0`；
  - 已有 context 链接会被**升级**为 support，不新增重复行。
- `CognitiveCoreFacade` 在 trait evidence 写入后调用该 linker；
- 不同 turn 的 fact 不会连接。

语义：

```text
同一真实回合产生的 explicit fact
  → 可以作为该回合 trait evidence 的 support
included 的其他 fact
  → 只能留在 context，不进 ranker
```

**验证**

- 同回合 fact → supports，ranker 得分；
- 不同回合 → 0；
- context → support 升级不重复；
- 全门禁：**373 passed / 92%**，fusion 70/70。

### 14.44 真实流量复验（2026-11-01 11:03）

修复早退后，真实回合：

- 11:02 `look_at_image` → trait 45 新 evidence；
- 11:03 `feiyu_say` → trait 66 新 evidence；
- shadow 21 条，全部 `[45,66]`；
- context links 25；
- support links 0；
- `semantic_facts.source_turn_id != ''` 仍为 0。

结论：

- trait learning、evidence、shadow、context 都已真实跑通；
- support 为 0 的直接原因是最近没有 explicit fact；
- 不是 linker 写入失败；
- 不为了指标放宽 support 条件。

下一步优先查 `subconscious_probe.explicit_fact` 的真实产出率，而不是继续改 ranker。

### 14.45 explicit fact 产出率（2026-11-01）

用固定文本模式 `“提到：”` 统计真实 explicit fact：

```json
{
  "total": 13,
  "last_24h": 7,
  "last_1h": 1,
  "with_source_turn": 0,
  "latest_ms": 1793501443885
}
```

结论：

- explicit fact 不是 0，最近 24h 有 7 条；
- `source_turn_id` 为 0 是因为这些 fact 多产生于字段上线前；
- support 稀缺不是因为 linker 坏了，而是因为“同回合同时有 trait 行为 + explicit fact”很罕见；
- 不放宽 support 条件。

新增 `scripts/explicit_fact_stats.py` 持续统计。

**验证**

- 参数账本 59 compliant；
- 全门禁沿用：**373 passed / 92%**，fusion 70/70。

### 14.46 真实回复风格测量（2026-11-01）

`scripts/style_monitor.py` 对主库真实 self 消息：

| 窗口 | n | 平均长度 | 长句率 | 解释词 | 括号动作 | 多问句 |
|---|---:|---:|---:|---:|---:|---:|
| 7 天 | 1000 | 41.6 | 33.6% | 3.3% | 10.1% | 0.4% |
| 最近 24h | 200 | 28.8 | 15.0% | 3.0% | 3.5% | 0.0% |

结论：

- 最近 24h 明显更短、更少括号动作；
- 但 7 天整体仍高于“默认 1–2 句、尽量 ≤26 字”的目标；
- 没有根据这组数据调参数；
- 继续用确定性指标监控，不接 LLM judge。

产物：

`eval/baselines/style-live-2026-11-01.json`

**验证**

- 全门禁沿用：**373 passed / 92%**，fusion 70/70。

### 14.47 health 增加 support 来源字段（2026-11-01）

`/api/mind/trait-health` 和 CLI 新增：

```text
facts_with_turn
```

用于区分：

- `no_causal_links`：有 shadow，但没有 support；
- `facts_with_turn=0`：连同回合 fact 来源都没有。

当前：

```text
status=no_causal_links
facts_with_turn=0
```

不是 ranker 丢数据，而是没有 explicit fact 带 `source_turn_id`。

**验证**

- 停掉 live 服务后跑全门禁，避免测试与生产进程同时写 config；
- **373 passed / 92%**，fusion 70/70。

### 14.48 受控 replay 验证 support（2026-11-01）

用户允许受控 replay 后：

- 将生产库只读备份到临时库；
- 使用真实 active traits；
- 构造一个 `feiyu_say` 回合；
- 同回合提供 `SubconsciousChordResult(explicit_fact=...)`；
- 跑真实 `on_turn_completed`。

结果（临时库，无生产写入）：

```json
{
  "trait_id": 66,
  "fact_id": 362,
  "fact_source_turn": "controlled-replay",
  "support_links": [{"memory_id": 362, "relation": "supports"}],
  "ranker_scores": {"362": 1.0},
  "shadow_trait_ids": [45, 66]
}
```

证明：

- 同回合 explicit fact 会带 `source_turn_id`；
- trait evidence 与 fact 建 support；
- ranker 看见 support；
- shadow 同时记录 active traits。

同时新增正式集成测试 `test_same_turn_explicit_fact_becomes_support`。

**验证**

- 全门禁：**374 passed / 92%**，fusion 70/70；
- 生产库未写入 replay；
- 生产 support 仍为 0，因为真实同回合样本还没出现。

### 14.49 手动 support 标注（2026-11-01）

用户明确需要手动标注，新增：

```text
scripts/manual_trait_support.py
```

规则：

- 必须指定 trait / evidence / semantic memory / reason；
- 默认 dry-run；
- 只有 `--apply` 才写；
- evidence 必须属于该 trait；
- memory 必须存在；
- reason 必填；
- 写入 `relation='supports'`、`is_context=0`、`note=reason`；
- context 行会被升级，不重复插入。

示例：

```bash
python scripts/manual_trait_support.py \
  --trait-id 66 \
  --evidence-id 14 \
  --memory-id 292 \
  --reason "手动确认：同回合语音行为"
```

当前只做了 dry-run，没有自动写生产。  
自动 support 仍只接受同回合 explicit fact。

**验证**

- 手动 support 升级 context + note + ranker 得分测试；
- 全门禁：**375 passed / 92%**，fusion 70/70。

### 14.50 手动 support 向导（2026-11-01）

用户不需要记 ID，新增交互式：

```text
scripts/manual_trait_support_wizard.py
```

流程：

1. 列出 active trait，选编号；
2. 列出该 trait 最近 evidence，选编号；
3. 列出最近 semantic memory，选编号；
4. 写一句理由；
5. 输入 `y` 才写，其他取消。

默认不写；只写一条 `supports` link，`note=理由`。  
不自动扩展、不批量、不改 trait 状态。

**验证**

- 向导 dry 交互已跑通；
- 全门禁沿用：**375 passed / 92%**，fusion 70/70。

### 14.51 首批真实手动 support（2026-11-01）

用户手动确认两条 support：

| trait | memory | note |
|---|---|---|
| 45 看图习惯 | 361「回音嘴硬反」自组织图式 | 下文有回复 |
| 66 发语音习惯 | 359「回音顺势吐」自组织图式 | 这个和上下文明显有关联 |

结果：

```text
status=ok
active_traits=2
shadow_since_activation=51
nonempty_shadow=51
causal_links=2
facts_with_turn=2
```

ranker 首次在生产中看到真实 support。

说明：

- 这是**人工确认**，不是自动 support；
- 自动 support 仍只接受同回合 explicit fact；
- 手动 link 带 note 审计；
- 没有改人格/prompt 参数。

**验证**

- 全门禁沿用：**375 passed / 92%**，fusion 70/70。

### 14.52 手动 support 的检索效果（2026-11-01）

只读对照：同一批真实 semantic facts，比较有/无 trait support。

```text
chat_key=group:813506156
query=回音唱歌 老婆 嘴硬
facts=220
support_scores={359: 1.0, 361: 1.0}
```

排名：

| memory | 无 support | 有 support |
|---|---:|---:|
| 359 | 44 | **6** |
| 361 | 30 | **4** |

top5 无 support：

```text
48, 3, 59, 1, 2
```

top5 有 support：

```text
48, 3, 59, 361, 1
```

结论：

- 手动 support 不只是写表，确实改变 live ranker 的排序；
- 359/361 都显著提前；
- 没有改变 raw facts，也没有伪造；
- manual note 可审计。

产物：

`eval/baselines/ranker-support-2026-11-01.json`

**验证**

- 只读脚本；
- 全门禁沿用：**375 passed / 92%**，fusion 70/70。

### 14.53 多 query 稳定性（2026-11-01）

5 个不同 query，只读对照：

| query | 359 前→后 | 361 前→后 |
|---|---|---|
| 回音唱歌 老婆 嘴硬 | 44→6 | 30→4 |
| 老婆 耳机 吃醋 | 44→9 | 133→31 |
| 唱歌 好听 震撼 | 141→31 | 42→9 |
| 回音 嘴硬 主人 | 125→13 | 24→4 |
| 语音 唱歌 哄 | 142→31 | 137→29 |

两条 support 在所有 query 下都提前，没有反向。

但也要诚实：

- 它们仍不总是进 top5；
- 一次 query 中 361 进 top4；
- support 是有效信号，但不是万能召回。

产物：

`eval/baselines/ranker-support-5q-2026-11-01.json`

**验证**

- 只读；
- 全门禁沿用：**375 passed / 92%**，fusion 70/70。

### 14.54 support 过拟合门控（2026-11-01）

新增 4 条手动 support 后，多 query 对照显示：

- support 会同时抬高无关 query 的 359/361；
- 例如“老婆 耳机 吃醋”里 361 从 30 升到 4，但 361 与耳机无关。

修复：

- `unified_rank` 的 trait ranker 只保留 **BM25 > 0** 的 memory；
- 0 是“无词法命中”，不是新阈值；
- trait support 只能放大已经和 query 有词法关联的记忆，不能凭空拉进。

门控后：

| query | 359 前→后 | 361 前→后 | 342 前→后 |
|---|---|---|---|
| 回音唱歌 老婆 嘴硬 | 44→6 | 30→4 | 193→193 |
| 老婆 耳机 吃醋 | 44→9 | 133→133 | 162→162 |
| 唱歌 好听 震撼 | 141→141 | 42→8 | 164→164 |
| 语音 唱歌 哄 | 142→142 | 137→137 | 167→167 |
| 调试 网关 模型 | 141→141 | 45→9 | 55→10 |
| 阿斋 端口 设置 | 149→149 | 144→144 | 51→9 |

结论：

- 无关 query 不再被无关 memory 污染；
- 相关 query 仍有提升；
- 门控仍不是完美语义判断，但消除了最明显的 over-boost。

**验证**

- 全门禁：**375 passed / 92%**，fusion 70/70。

### 14.55 手动标注候选上下文（2026-11-01）

向导 memory 列表新增关键词筛选，避免较早 fact 不在最近 30 条里。

候选（只建议，不自动写入）：

| trait | evidence | memory | 关系 |
|---|---|---|---|
| 45 看图 | 13「豆包画的白发蓝眼小姑娘」 | 301「群友发标着豆包生成的图片」 | 同属看图/豆包图 |
| 45 看图 | 3「这张蓝发女仆是谁呀」 | 311「照片/主人先给你穿上」 | 照片上下文 |
| 66 语音 | 12「谢谢你听我唱歌」 | 263「阿斋夸回音唱得好听」 | 唱歌反馈 |
| 66 语音 | 14「陪你说说话…慢慢吐气」 | 303「回音语音表示龙王让给菲菲」 | 语音表达 |

操作：

1. 向导选 trait；
2. 选 evidence；
3. 输入关键词（豆包/照片/唱歌/语音）；
4. 选 memory；
5. 写理由，`y` 确认。

**验证**

- 向导筛选已跑通；
- 全门禁沿用：**375 passed / 92%**，fusion 70/70。

### 14.56 6 条手动 support 复验（2026-11-01）

用户又补 2 条：

- trait 45 → 332；
- trait 66 → 332。

当前：

```text
support rows=6
distinct support memory=4（359/361/342/332）
status=ok
```

门控后 9 个 query：

| query | 359 | 361 | 342 | 332 |
|---|---:|---:|---:|---:|
| 回音唱歌 老婆 嘴硬 | 44→6 | 30→4 | 193→193 | 184→184 |
| 老婆 耳机 吃醋 | 44→9 | 133→133 | 162→162 | 152→152 |
| 唱歌 好听 震撼 | 141→141 | 42→8 | 164→164 | 156→156 |
| 回音 嘴硬 主人 | 125→13 | 24→4 | 200→200 | 189→189 |
| 语音 唱歌 哄 | 142→142 | 137→137 | 167→167 | 157→157 |
| 调试 网关 模型 | 141→141 | 45→10 | 55→11 | 49→9 |
| 阿斋 端口 设置 | 149→149 | 144→144 | 51→10 | 47→9 |
| dsh 窗口 端口 | 138→138 | 134→134 | 163→163 | 49→9 |
| 毛玉 截图 图片 | 157→157 | 153→153 | 177→177 | 171→171 |

结论：

- 332/342 只在调试/端口类 query 提升；
- 图片类 query 不被调试记忆污染；
- 361 仍会在“调试 网关 模型”提升，因为其 fact 文本含“模型”，词法门控允许；
- 词法门控消除了明显的跨话题 boost，但不是完美语义判断。

**验证**

- 全门禁沿用：**375 passed / 92%**，fusion 70/70。

### 14.57 真实 query 下的 support 审计（2026-11-01）

最近 20 条真实群消息作为 query：

```text
queries=20
improved=3
unchanged=77
worsened=0
```

提升样例：

| query | memory | before → after |
|---|---|---:|
| 昨天忆染也发过一串… | 332 | 56→9 |
| 那是橡皮的号 不是我的 | 332 | 70→9 |
| 噗，五抽就出… | 361 | 43→9 |

结论：

- 没有恶化；
- 但提升的 query 有“串/号/五抽”这类**弱相关**；
- 词法门控仍会因单个 bigram 命中而 boost；
- 不能把这 3 次提升当成“语义正确”；
- 不继续调参/加阈值，先记录。

产物：

`eval/baselines/support-live-queries-2026-11-01.json`

**验证**

- 只读；
- 全门禁沿用：**375 passed / 92%**，fusion 70/70。

### 14.58 风格监控接线（2026-11-01）

新增只读：

```text
GET /api/mind/style-health
```

返回最近 24h self 消息的确定性指标：

- n
- avg_len
- long_rate
- explain_rate
- roleplay_rate
- multi_question_rate

这是 C5 的接线；不改 prompt，不接 LLM judge。

**验证**

- Web 测试覆盖 endpoint；
- `app.py` 保持 300 行；
- 全门禁：**375 passed / 92%**，fusion 70/70。

### 14.59 删除 7 条 legacy trait（2026-11-01）

用户确认删除无 evidence 的 legacy trait。

删除前审计：

- 7 条全部 `legacy_unverified`；
- `trait_evidence=0`；
- `trait_memory_links=0`；
- `trait_candidates=0`；
- 备份：`eval/baselines/deleted-legacy-traits-2026-11-01.json`。

删除 ID：

```text
120, 154, 156, 158, 162, 163, 165
```

结果：

```text
all_traits=2
active_traits=2
current_prompt_len=1222
active_only_prompt_len=1222
delta=0
```

说明：

- 现在 prompt 实际只剩 2 条 active；
- 当前 filter 仍保留 `legacy_unverified` 分支，供未来显式迁移使用；
- 但库里已经没有 legacy，所以行为等同 active-only；
- 没有删除 active trait/evidence/support。

**active-only prompt 定义**：

```text
只渲染 status='active' 的 trait；
candidate / dormant / retired / legacy_unverified 不进入 prompt。
```

**验证**

- 健康：`ok`；
- shadow=53；
- support=6；
- 全门禁沿用：**375 passed / 92%**，fusion 70/70。

### 14.60 active-only prompt 正式启用（2026-11-01）

删除 legacy 后，把 filter 从：

```text
active + legacy_unverified
```

改为：

```text
active
```

同时修复 `trait_prompt_shadow`：候选替换文本时保留原 trait 的 status，避免 shadow 对比里 active 被降成 legacy。

当前生产：

```text
all_traits=2
active_traits=2
prompt_len=1222
```

未来新 trait 必须先经过 evidence/lifecycle 成为 active，才会进入 prompt。

**验证**

- 测试夹具更新为显式 active；
- 全门禁：**375 passed / 92%**，fusion 70/70。

### 14.61 action eligibility 语义（2026-11-01）

先定语义，不直接接 live：

```text
allowed_tools 为空  → 不限制任何工具
allowed_tools 非空  → 仅白名单内工具允许
```

理由：

- active trait 45/66 的证据都是 assistant 文本，没有 tool 证据；
- 如果“空=拒绝所有”，会让正常回合无法发送/看图；
- 空授权只能表示“没有额外限制”，不能表示拒绝。

新增：

```python
Eligibility.permits_tool(tool)
```

测试：

- 空授权允许 send_message / look_at_image；
- 非空白名单只允许白名单内工具。

**边界**

- 仍未接 live；
- `allow_refusal` 仍只在 shadow 记录；
- 接 live 前还需要决定：白名单是“额外允许”还是“硬性限制”。

**验证**

- 全门禁：**377 passed / 92%**，fusion 70/70。

### 14.62 action eligibility 接 live（2026-11-01）

采用**额外授权**语义，不是硬白名单：

- 基础工具集保持不变；
- active trait 的 tool evidence 只**追加**允许工具；
- 空授权不改任何工具；
- 当前 active 45/66 都是 assistant 证据，所以线上工具集不变。

实现：

- `mind/trait_tool_grants.py::apply_live_grants`；
- `compute_and_grant` 在 facade 构建 frame 时调用；
- `allow_refusal` 仍未接 live。

测试：

- tool grant 追加，不替换 send_message；
- 无 tool 证据不变；
- 无 evidence store no-op。

**验证**

- 全门禁：**380 passed / 92%**，fusion 70/70。

### 14.63 allow_refusal 接 live 许可（2026-11-01）

`allow_refusal` 从 shadow 字段变为 `CyberneticCoreState.allow_refusal` 许可：

- active taboo → true；
- 只在 prompt 增加“本轮允许拒绝”提示；
- **不强制拒绝**；
- 当前没有 active taboo，所以线上值仍为 false。

`apply_live_grants` 同时合并：

```text
tool grants（追加）
allow_refusal（许可）
```

测试：

- active taboo 无 tool evidence 时，工具集不变、allow_refusal=true；
- 普通 active trait 仍 false。

**验证**

- 全门禁：**381 passed / 92%**，fusion 70/70。

## 14.64 代码审计发现的文档盲区（2026-11-01）

以下是代码与真实数据中已经存在、但原计划没有单列的缺口。它们不是“没写代码”，而是“机制不完整或没有进入 live”。

### 当前真实基线

```text
active_traits=2          # 45 看图、66 语音
legacy_traits=0          # 7 条已删除并审计
shadow=53                # 全部非空 [45,66]
support_links=6          # 4 个不同 memory
facts_with_turn=2
tests=381
prompt=active-only
```

### G1 自动 candidate → active 晋升（未做）

现状：

- `TraitTextGenerator` 能生成带 `situation/behavior/result` 的候选；
- 但只在离线脚本中使用；
- live `adapt_from_outcome` 直接写 evidence/lifecycle，不生成 candidate，也没有自动晋升器。

缺口：

```text
真实证据
  → candidate（未接 live）
  → 自动 review（未接）
  → active（仍靠 evidence 直达或人工）
```

未做原因：

- candidate 质量评估和晋升边界尚未冻结；
- 自动晋升会直接改变 prompt，必须先有回放/A-B 证据。

### G2 narrative identity 实时闭环（未做）

现状：

- 模型文档有 narrative identity 设计；
- 代码没有“把 active trait + 关键情节合成第一人称叙事”的 live 服务；
- prompt 里没有叙事层。

缺口：

- 叙事生成、去重、冲突消解、隐私过滤均未实现。

未做原因：

- 没有评估集判断叙事是否改善一致性；
- 容易把 trait 文本复述成空话。

### G3 自动 support 的语义级门控（部分）

现状：

- 自动 support 只接受同回合 explicit fact；
- ranker 只保留 `BM25 > 0` 的 memory；
- 真实 20 query 审计仍有“串/号/五抽”这类弱相关命中。

缺口：

```text
BM25 > 0
  ≠ 语义相关
```

未做原因：

- 没有可靠的 query-memory 相关性标签；
- 加阈值或 LLM judge 会引入新的未校准参数；
- 当前用手动 support 作为可控路径。

### G4 action eligibility 硬限制模式（未做）

现状：

- 已接 live 的是“额外授权”：
  - tool evidence 只追加工具；
  - taboo 只授予拒绝许可；
- 不是硬白名单，不会移除基础工具；
- 也不会强制拒绝。

缺口：

- “白名单=硬性限制”的语义没有实现；
- “taboo=强制拒绝”没有实现。

未做原因：

- 当前 active trait 都是 assistant 证据；
- 硬限制会误伤正常回复；
- 需要先有 active taboo/tool trait 的真实样本。

### G5 dormant / 长期不活跃策略（未做）

现状：

- `dormant` 只是状态类型；
- lifecycle 只写 candidate/active/retired/legacy；
- 没有“长期无强化 → dormant”的规则。

缺口：

- 没有有来源的不活跃时间窗口；
- 没有 dormant 的恢复/退场路径。

未做原因：

- 不愿拍脑袋定“多少天算 dormant”；
- 需要论文或真实数据支持。

### G6 support ranker 的强度/校准（未做）

现状：

- support 仍是 presence-only（1.0）；
- RRF 等权；
- 没有置信度/证据强度权重。

缺口：

- 无法区分“强支持”和“弱支持”；
- 多条 support 会等权叠加。

未做原因：

- 没有可靠的相关性/强度标签；
- 任何权重都会是新的未校准参数。

### G7 风格监控只报告，不拦截（设计如此，未闭环）

现状：

- `/api/mind/style-health` 可看 24h 指标；
- 没有在生成后做拦截、重写或告警。

缺口：

- 风格漂移没有自动响应；
- 没有“超过目标就回退 prompt”的机制。

未做原因：

- 之前 trait 改风格的 A/B 没有稳定收益；
- 强行拦截可能损伤内容质量。

### G8 外部 benchmark 适配器（未做）

现状：

- LongMemEval 只跑了 100 题 retrieval；
- GroupMemBench / CharacterEval 未接；
- 没有数据许可/字段映射/评分脚本。

缺口：

- 没有外部有效性证据；
- 没有多人群聊/中文人格的横向比较。

未做原因：

- 数据集、许可、适配协议尚未落地；
- 不应在没有数据时写“已接”。

### G9 文档自身的历史漂移（已发现）

第 0 节仍写着：

- 9 条 trait；
- 321 tests；
- trait→记忆未接；
- style 未跟踪。

这些已被 14.1–14.63 推翻。  
本节的“当前真实基线”应作为后续入口；第 0 节保留为历史快照。

### 优先级

| 优先级 | 缺口 | 进入条件 |
|---|---|---|
| P1 | G5 dormant 策略 | 找到有来源的不活跃窗口 |
| P1 | G6 support 强度 | 有相关性/强度标签 |
| P2 | G4 硬限制 | 有 active taboo/tool 真实样本 |
| P2 | G1 自动晋升 | 候选质量评审 + 回放通过 |
| P3 | G2 narrative | 评估集 + 隐私过滤 |
| P3 | G3 语义门控 | 相关性标签或校准过的 judge |
| P3 | G8 外部 benchmark | 数据/许可/适配 |
| P4 | G7 风格拦截 | 有稳定风格收益证据 |

**验证**

- 文档更新，无代码变更；
- 全门禁基线：**381 passed / 92%**，fusion 70/70。

## 14.65 任务闭环矩阵（2026-11-01）

### 已闭环（本轮或已存在）

| ID | 证据 |
|---|---|
| D1 | 固定自称已通过 `bot_naming()` 渲染；`grep -R` 仅剩 naming 默认值与 enricher 否定词 |
| D2 | `bond_recorder.record_turn_events` 已在 `live_client` 回合完成处调用 |
| G4 | `apply_live_grants(mode="additive"|"whitelist")`；默认 additive，whitelist 有测试 |
| C5 | `/api/mind/style-health` 已接线 |
| A1/A3/A5/A6 | evidence、active-only、trait ranker、资格许可均 live |
| A7/C1 | 30/90 天 replay 基线已存在 |
| G9 | 文档历史基线已标注 |

G4 语义：

```text
additive: 基础工具 + 允许工具（默认）
whitelist: 有 grants 时只保留 grants；无 grants 时保持基础工具
```

### 明确排除：需要长期数据/外部集

| ID | 原因 |
|---|---|
| G3 | 需要 query-memory 相关性标签或校准 judge |
| G5 | 需要 sourced dormant 时间窗 |
| G6 | 需要 support 强度/相关性标签 |
| G7 | 需要稳定风格收益证据 |
| G8/C2/C3/C4 | 需要数据集、许可、远端资源 |
| A8/A9/A10 | 需要构念效度/冻结标签/外部人格集 |
| B1 | 需要确认 ACT-R `d` 的公开来源；无来源不实现 |
| B2/B3 | 需要 shadow/A-B 与层级聚类数据 |
| B7 | 当前规模不触发 ANN |
| D3/D4 | 需要跨群/人工 bond 标签 |

### 仍未闭环、但不属于“长期数据”的工程设计

| ID | 缺口 | 性质 |
|---|---|---|
| B4 | claims `FACTS_V2` 读路径 | provenance/migration，需单独设计 |
| B5 | 披露归因 M6/M7 | memory_knowledge 传播模型 |
| B6 | 事实层时间边 | schema/迁移/读路径 |
| G1 | 自动 candidate → active | 需要质量/晋升评审 |
| G2 | narrative identity | 需要评估与隐私过滤 |

这些不是“跑一阵数据就会自动完成”，而是仍需设计/迁移；不能靠本轮直接拍脑袋接 live。

**验证**

- 全门禁：**383 passed / 92%**，fusion 70/70。

## 14.66 B5 披露归因接线（2026-11-01）

`_handle_choice` 在 persona 选择 `say` / `hint` 后，对 audience 中每个人写入：

```text
memory_knowledge(memory_kind='semantic', memory_id, person_id, state)
state = told_by_me | hinted
```

- `keep` 不写；
- secret/private 硬门仍在前面；
- `who_knows` 可查询谁听到/谁没听到；
- 只有 log 实现 `mark_known` 时写入，测试 fake log 已补齐。

**验证**

- 私密 fact 说给 owner：knowledge 状态为 `told_by_me`；
- 全门禁：**383 passed / 92%**，fusion 70/70。

## 14.67 B6 事实层时间边（2026-11-01）

实现：

- `SemanticFact.valid_to_ms`（`None` = 长期有效）；
- 有效起点复用已有 `event_time_ms`；
- `semantic_facts.valid_to_ms` 迁移；
- 读路径过滤：

```text
event_time_ms = 0 OR event_time_ms <= now
AND (valid_to_ms IS NULL OR valid_to_ms > now)
```

当前真实数据：

- 所有 fact 的 `valid_to_ms` 都是 NULL；
- 因此线上结果不变；
- 新 fact 可以写入明确失效时间。

测试：

- 有效 fact 保留；
- 过期 fact 排除；
- 未来 fact 排除。

**验证**

- 全门禁：**384 passed / 92%**，fusion 70/70。

## 14.68 B4 claims 读路径（2026-11-01）

claims 表补齐 provenance：

```text
scope
source_person_id
owner_id
sensitivity
audience_json
source_quote
source_turn_id
```

`mirror_fact` / `assert_claim` 写入这些字段。  
`FACTS_V2=on` 时：

```text
load claims
  → claims_as_facts
  → confidence / privacy / person filters
  → get_semantic_facts
```

安全：

- 只放行 public/group；
- private/secret 不在 claim 读路径放行；
- 默认 `FACTS_V2=off`，线上仍走 legacy facts；
- 没有自动切换。

测试：

- claim 读路径能看到 provenance；
- secret 被过滤；
- `FACTS_V2=on` 不再 fail-fast；
- 全门禁：**385 passed / 92%**，fusion 70/70。

## 14.69 G2 叙事投影（只读层，2026-11-01）

新增：

```text
mind/narrative_identity.py
scripts/trait_narrative.py
```

规则：

- 只取 `status='active'`；
- 每条 trait 只取最近 1 条真实 evidence；
- 输出第一人称叙事投影；
- **不进入 prompt**；
- 没有 evidence 的 trait 不生成叙事。

真实输出：

```json
{
  "trait_ids": [66, 45],
  "lines": [
    "情绪上来或被哄开心时会直接发语音亲口说给对方听（有次：...）",
    "看到群友发图或视频会凑上去仔细看细节（有次：...）"
  ]
}
```

边界：

- 这是叙事投影，不是 live prompt；
- 接入 prompt 之前仍需评估/隐私过滤；
- 没有编造 trait 或 quote。

**验证**

- 全门禁：**386 passed / 92%**，fusion 70/70。
