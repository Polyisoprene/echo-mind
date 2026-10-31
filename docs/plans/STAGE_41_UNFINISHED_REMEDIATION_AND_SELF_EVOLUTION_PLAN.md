# Stage 41 未完成事项建模、自演化闭环与落实计划

> 日期：2026-11-01
> 范围：以 `docs/PERSONA_MEMORY_AUDIT_AND_ROADMAP.md`、`docs/PERSONA_SELF_EVOLUTION_MODEL.md`、`docs/MASTER_BACKLOG.md` 为基线，覆盖人格、记忆、评测、身份/关系四条未完成线。
> 原则：先建模再写代码；新数值必须有论文/数据/账本依据；不做代码或 prompt 的自修改。

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
