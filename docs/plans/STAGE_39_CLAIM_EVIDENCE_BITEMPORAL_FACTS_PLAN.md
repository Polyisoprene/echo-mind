# Stage 39 事实层重构：主张—证据—双时态（Claim / Evidence / Bitemporal）

> **状态**：📋 规划评审中（未动代码）
> **替代方案**：Stage 38 拟议的 T0–T5（锁定护栏 + 时间补丁）**不再采用**——那是在"布尔锁"模型上叠例外。
> **前置**：Stage 29（关系深度）、Stage 30（人格动力学）、Stage 31（社交习惯化）、Stage 36（探针可靠性）
> **纪律**：A 线实现与验证 → `scripts/promote.sh` 准出 → B 线只接受 cherry-pick。

---

## 一、 问题：不是"锁的护栏不够"，是"锁"这个模型错了

现状：

```text
semantic_facts(subject, fact_text, confidence, is_locked, source, updated_at)
```

三个结构性缺陷（均由真实数据暴露）：

| 缺陷 | 证据 |
|---|---|
| **布尔权威**：`is_locked=1` 即永久否决自动来源 | `memory_repo._check_fact_lock`：`can_override` 仅当新事实也是 owner/system **且** `is_locked` |
| **锁不可解除**：`is_locked=0` 的更新会被判为"不可覆盖" | 同上；无法把锁定事实降级为可更正 |
| **无有效期**：事实永远"现在时" | 生产库 6 条锁定事实里，`回音的主人 = 我的唯一主人是 L…` 与 D1/D2 决策冲突，却无法被对话纠正 |

**后果**：错误锁定只能人工删除（丢历史）；一旦做"锁定事实强制进提示词"（T0），错误会被 100% 放大。

---

## 二、 文献依据

| 理论 | 论文 | 作用 |
|---|---|---|
| 真值维护（TMS） | Doyle (1979), *A truth maintenance system*, AI, [doi:10.1016/0004-3702(79)90008-0](https://doi.org/10.1016/0004-3702(79)90008-0) | 事实由 justification 支撑；支撑失效则 retract |
| 信念修正（AGM） | Alchourrón, Gärdenfors & Makinson (1985)；形式见 *Theoria* 1982, [doi:10.1111/j.1755-2567.1982.tb00480.x](https://doi.org/10.1111/j.1755-2567.1982.tb00480.x) | expansion / revision / contraction 三类操作 |
| 真值发现 | Yin, Han & Yu (2007), KDD, [doi:10.1145/1281192.1281309](https://doi.org/10.1145/1281192.1281309) | 来源可靠度 × 证据数量 → 置信度；管理员不是绝对权威 |
| 双时态数据 | Snodgrass & Ahn (1985), SIGMOD, [doi:10.1145/971699.318921](https://doi.org/10.1145/971699.318921) | 有效时间 vs 记录时间；天然支持"那时是 A，现在是 B" |
| 记忆检索含新近度 | Park et al. (2023), Generative Agents, [arXiv:2304.03442](https://arxiv.org/abs/2304.03442) | 检索分数 = recency + importance + relevance |
| 遗忘曲线 | Zhong et al. (2023), MemoryBank, [arXiv:2305.10250](https://arxiv.org/abs/2305.10250) | 时间 + 重要性决定遗忘 |
| 遗忘形状 | Anderson & Schooler (1991), [doi:10.1111/j.1467-9280.1991.tb00174.x](https://doi.org/10.1111/j.1467-9280.1991.tb00174.x)；Wixted & Ebbesen (1991), [doi:10.1111/j.1467-9280.1991.tb00175.x](https://doi.org/10.1111/j.1467-9280.1991.tb00175.x) | 人类遗忘更接近幂律（后续可选） |

---

## 三、 目标模型

### 3.1 表结构

```sql
claims(
  id, chat_key, subject, predicate, value,
  valid_from_ms, valid_to_ms,          -- 世界时间（双时态之一）
  recorded_at_ms,                       -- 我们何时得知（双时态之二）
  status,                               -- asserted | retracted | superseded
  superseded_by, created_by
)

evidence(
  id, claim_id, source_type,            -- operator | system | peer | explored | derived
  source_id, weight, observed_at_ms, raw_text
)

fact_reviews(                            -- 复核任务（冲突自动产生）
  id, chat_key, subject, predicate, reason, opened_at_ms, resolved_at_ms, resolution
)
```

### 3.2 置信度：证据聚合，而非布尔锁

```text
belief(claim) = σ( Σ_i w_i · r_i )
  w_i = 单条证据权重（operator 1.5 / system 1.3 / peer 0.5 / explored 0.4 / derived 0.6）
  r_i = 来源可靠度（truth discovery 迭代估计，初值：operator 0.95 / system 0.9 / peer 0.45）
```

- **管理员证据权重最高，但不是否决**；
- 当同一 `(subject, predicate)` 存在多条 claim 时：后验最高者为"当前认知"，其余作为"分歧"保留；
- 冲突证据达到阈值（如 3 条独立来源）→ 自动开 `fact_reviews` 任务，控制台可见。

### 3.3 状态机

```text
asserted ──(被更好后验取代)──► superseded ──► (可回溯查看)
   │
   └──(管理员/证据不足)──► retracted   ← 撤销是一等操作，保留历史
```

### 3.4 时间：双时态 + 相对时间渲染

```text
valid_from/to  → "这条事实在 10-28 到 10-30 有效"
recorded_at    → "我们是 10-30 21:12 知道的"
渲染： [85%｜3小时前记录｜有效至 10-31]
```

这同时解决了原 T1/T2（时间表达）——**不需要再做独立补丁**。

### 3.5 检索

```text
1) 取 (subject, predicate) 的最高后验 claim（as-of now）
2) relevance 排序仍用于同 subject 的召回
3) recency 项（Generative Agents 式）叠加：+3·exp(-Δt/7d)
4) 管理员证据豁免截断（对应原 T0，但不再依赖布尔锁）
5) 存在分歧时渲染："记得是 A（60%），另有说法 B（40%）"

> **容量不是约束**：当前模型上下文已达百万级，记忆条数上限（原 28）不再由容量决定，
> 而由**相关性与信噪比**决定。默认 N 可提到 40–60，但同一 `(subject, predicate)` 只放
> 后验最高的一条 + 至多 2 条分歧，避免"重复与矛盾污染上下文"（见 §7）。
```

---

## 四、 与现有模块的映射

| 现在 | 迁移后 |
|---|---|
| `semantic_facts.subject/fact_text` | `claims.subject / value` |
| `confidence` | 由证据聚合重算（原值作为初始 evidence） |
| `is_locked=1` | `evidence(source=operator, weight=1.5)` + `status=asserted` |
| `source` | `evidence.source_type` |
| `updated_at` | `recorded_at_ms`（并补 `valid_from/to`） |
| `locked_fact_conflict` | 写入冲突 evidence + 开 `fact_reviews` |
| 删除事实 | `status=retracted`（保留历史） |
| `reconcile_service` 只删未锁定 | 改为"低后验 + 久未复核"候选列表 |

涉及文件：`adapters/storage/memory_repo.py`、`domain/models.py`（SemanticFact 扩展）、`mind/ebbinghaus.py`（检索）、`mind/frame_renderer.py`（渲染）、`web/mind_inspector_service.py`（控制台）、`mind/memory_consolidator.py`（写入）。

---

## 四·五、 S39-0 已落地（DDL + 红灯骨架）

- `storage/migrations.py`：新增 `ensure_claim_tables()`（`claims` / `claim_evidence` / `fact_reviews` + 索引），
  与 `ensure_trait_columns()` 合并为 `ensure_migrations()`，在 `initialize()` 一次执行；
- 旧表 `semantic_facts` 未改动，读取路径未切换 → **行为零变化**；
- 新增红灯测试 `tests/integration/test_claim_store.py`：4 条以 `xfail(strict=True)` 钉住目标
  （断言、冲突复核、撤销保历史、双时态 as-of 查询）；
- 红灯证据：`reports/S39_RED_EVIDENCE.log`（4 failed / 2 passed）；
- 门禁：189 passed / 4 xfailed。

## 四·六、 S39-1 已落地（claim store + 可选双写）

- `adapters/storage/claim_repo.py`：`SqliteClaimStore`
  （`assert_claim` / `claim_belief` / `claim_status` / `retract` / `open_reviews` / `current_value`）；
- 后验：`belief = 1 − exp(−Σ wᵢ)`，权重 = 来源权重 × 来源可靠度；
- 冲突：同一 `(subject,predicate)` 出现 ≥2 个值且 ≥3 个独立 peer 来源 → 自动开 `fact_reviews`；
- 双写：`FACTS_V2_WRITE=on` 时 `upsert_semantic_fact` 镜像写入 claim + evidence（**默认 off**，读取路径不变）；
- 测试：`tests/integration/test_claim_store.py` 8 条全绿（含双写开关）。

## 五、 迁移步骤（影子优先，零行为改动）

| 阶段 | 内容 | 行为影响 |
|---|---|---|
| **S39-0** | 本文档 + DDL + 空表 + 测试骨架（红） | 无 |
| **S39-1** | 双写：`upsert_semantic_fact` 同时写 claims/evidence（`FACTS_V2=off` 时旧路径仍生效） | 无 |
| **S39-2** | 回填：每条现有事实 → 1 claim + 1 evidence（lock→operator 权重，source→source_type） | 无 |
| **S39-3** | 影子对比：同一批查询，比较"旧 top-28" vs "新后验 top-28"，输出重叠率/冲突数 | 无 |
| **S39-4** | 读路径切换（开关 `FACTS_V2=on`）；渲染加时间与分歧提示 | **有**（可回退） |
| **S39-5** | 冲突复核 UI + retract/取消撤销 | 有 |
| **S39-6** | 退役 `is_locked`（保留列兼容） | 有 |

---

## 六、 验收指标

| 指标 | 目标 |
|---|---|
| 回填完整性 | 100% 现有事实有对应 claim + ≥1 evidence |
| 影子对比 top-28 重叠率 | ≥70%（差异需可解释） |
| 冲突检出 | 真实库中至少检出"回音的主人"这类矛盾 |
| 人设一致性问答（群主/她名字/关系） | 100% 正确，不回退 |
| 上下文信噪比 | 同一主题不重复堆叠；人工抽检 20 条，无自相矛盾表述 |
| 撤销可追溯 | 任意 retracted 可查历史与原因 |

---

## 七、 对人格核心的影响

- **参数**：7D、日限、慢回归、词条、姿态、社交习惯化 **全部不变**；
- **一致性**：杜绝"错误锁定事实每轮进提示词"，人设更稳；
- **时间感**：双时态天然支持"那时/现在"，不再单独打时间补丁；
- **风险**：多 claim 并存可能让提示词变长 → 需 top-N 截断与分歧摘要（最多 2 条）。

---

## 八、 风险与回滚

| 风险 | 缓解 |
|---|---|
| 后验校准偏差（初期误判） | 先在影子模式对比，不切读路径 |
| **长上下文利用率下降** | 模型对"中段信息"的利用会衰减（Lost in the Middle, Liu et al. 2023, [arXiv:2307.03172](https://arxiv.org/abs/2307.03172)）→ 重要事实放前部、分歧紧跟其后；不靠"塞更多" |
| 重复/矛盾污染 | 每个 topic 只放后验最高 + 至多 2 条分歧；回填时合并同义 claim |
| 迁移丢历史 | 双写 + 回填；旧表保留只读 |
| 回滚 | `FACTS_V2=off` 即回旧路径；新表可整体删除 |

---

## 九、 待你确认

1. 是否按本方案推进（影子双写 → 回填 → 对比 → 切换）？
2. 管理员证据权重 1.5 / system 1.3 / peer 0.5 是否接受（后续可校准）？
3. 冲突阈值"3 条独立来源"是否合适？
4. 是否顺便处理那条 `回音的主人` 错误事实（作为 S39-2 回填后的首个复核样例）？
5. 记忆条数上限：容量已不是瓶颈，是否把默认召回从 28 提到 40–60（按相关性排序，不按容量截断）？
