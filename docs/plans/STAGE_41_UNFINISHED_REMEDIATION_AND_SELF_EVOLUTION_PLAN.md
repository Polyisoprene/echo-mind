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
  - `trait_id`, `session_id`, `turn_id`, `quote`, `polarity`, `context_hash`, `created_ms`；
  - 唯一约束 `(turn_id, trait_id, polarity)`，防重复计。
- `evidence_count` / `contradiction_count` 改为从表派生。
- 现有 9 条 trait 回填：只回填能追溯到 `source` 和原文的；不能追溯的标 `legacy_unverified`，不得直接 active。
- 先 shadow 写，不改 prompt。

**验收**

- 每条 active trait 都能列出至少 1 条原文引用；
- 同一 turn 重复写不增加证据；
- 开启/关闭账本，prompt 逐字一致（shadow 等价）。

### A2. P1 生命周期（只改可见性）

**实现**

- `persona_traits` 增加 `status`、`active_since_ms`、`last_support_ms`、`last_contradiction_ms`。
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

- 建模：`B_i = ln(Σ_j t_j^-d)`，`d` 用 ACT-R 文献值并登记 ledger；
- 作为 `actr` ranker 进 RRF；
- 与 recency 做消融；无增益就不启用；
- 不允许手调 `d`。

### B2. HyDE / query expansion

- 生成假设答案/扩展 query，再检索；
- 先 shadow，记录延迟/成本；
- A/B 通过才启用；
- 隐私硬门不变。

### B3. 父子链接 / 层级摘要

- 事实/情节/摘要多级；
- 检索可在多级返回，再融合；
- 不做无依据的固定层级数；
- 先做离线 A/B，再上线。

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

- 先确认数据许可和字段；
- GroupMemBench 更贴近多人群聊，优先；
- 无数据不写“已接”。

### C4. 外部中文人格集

- CharacterEval 类；
- 自动指标 + 人工冻结标签；
- 不把 LLM judge 当门禁。

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
