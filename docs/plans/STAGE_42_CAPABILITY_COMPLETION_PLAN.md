# Stage 42：可做未做能力完善计划（建模 / 外部依据 / 分阶段）

> 日期：2026-11-01
> 目标：把“当前可做但还没做”的能力补齐，同时避免局部打补丁造成全局退化。
> 原则：先建模评估 → 查公开论文/产品依据 → 用本机工程数据定范围 → 落文档 → 再实现。
>
> 当前基线见 [CURRENT_STATE_2026-11-01.md](../CURRENT_STATE_2026-11-01.md)。

---

## 0. 结论先行

当前最该补的不是“更多文本”，而是：

1. **Response attribution（回应归因）**：她说完一句话后，谁回应、是否针对她、结果如何；
2. **外部评测补全**：LongMemEval 500 + QA/abstention、GroupMemBench、CharacterEval；
3. **已有标签/理论可完成的校准**：stance、dormant、ACT-R、HyDE；
4. **实验型检索增强**：语义 support gate、RAPTOR；
5. **多 venue 数据扩展**：更多 QQ 群/私聊；B 站评论只作观察语料，不作为 trait evidence。

---

## 1. 不做“局部补丁”的全局约束

### 1.1 数据分层

```text
InteractionOutcome   她的行为 + 针对她的回应      → trait evidence / social reward
ObservationCorpus    别人的评论/视频/梗           → 世界知识 / 风格参考
Memory               事实 / 情节 / 关系           → 检索
Evaluation           外部 gold / 冻结标签         → 只评估，不写入人格
```

硬约束：

- B 站评论区默认进 `ObservationCorpus`，**不得**写 `trait_evidence`；
- 只有“她的行为 → 针对她的回应”才可成为 social reward/evidence；
- 任何新 source 必须带 provenance 与 privacy 字段。

### 1.2 三态交付

每个能力必须经过：

```text
shadow（只计算不生效）
  → 离线/外部 benchmark
  → 小流量 live
  → 默认启用 + 回滚开关
```

没有 shadow 与验收数据，不允许直接改 live 行为。

### 1.3 参数规则

- 不新增手调权重；
- 所有窗口/阈值必须有论文、公开实现或本机工程数据；
- 新常数进 `docs/params/ledger.json`；
- `fit_pending` 不能写成 `fit`；
- 同一指标至少 3 个 query/场景，避免单次偶然。

---

## 2. P0：Response attribution（最高优先）

### 2.1 为什么

当前 `chat_messages` 有 8,326 条、self 1,709 条，但系统不知道“她的话造成了什么结果”。人格证据的瓶颈不是内容条数，而是**反馈归因**。

### 2.2 本机工程数据（2026-11-01）

对 1,709 条 self 消息统计：

| 窗口 | 任意后续他人消息 | 明确点名/叫回音/尾尾 |
|---|---:|---:|
| 1 min | 1,452（85.0%） | 349（20.4%） |
| 5 min | 1,615（94.5%） | 784（45.9%） |
| 15 min | 1,642（96.1%） | 1,147（67.1%） |
| 30 min | 1,654（96.8%） | 1,333（78.0%） |

直接回应延迟：

```text
median 208.9s
p75    568.1s
p90    1122.2s
p95    1371.9s
mean   382.2s
```

### 2.3 建模

```text
SelfMessage
  → candidate replies: same chat, after self, within empirical window
  → attribution tier:
      tier A: quote/reply metadata（若有）
      tier B: 明确点名/别名
      tier C: 仅时间相邻（弱，不进 evidence）
  → outcome:
      responded / ignored / directed / not-directed
  → social reward（先 shadow）
```

窗口先取 **30 min**：本机直接回应 p95=22.9 min，30 min 覆盖 p95；不使用拍脑袋的 5 min。

### 2.4 外部依据

- 没有把“任意相邻消息”当回复的公开理论；因此只把 tier A/B 当 directed；
- tier C 只做统计，不进 evidence；
- 这是工程数据驱动的规则，不声称是论文算法。

### 2.5 验收

- 每条 self 消息有 attribution 记录；
- 不把 tier C 写入 evidence；
- 先做规则一致性与可复现性检查；如用户允许，再抽 30 条只读核对，不新增训练标签；
- shadow 下 prompt/ranker 不变。

---

## 3. P1：外部评测补全

### 3.1 LongMemEval 500 + QA/abstention

依据：[LongMemEval, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/d813d324dbf0598bbdc9c8e79740ed01-Abstract-Conference.html)

- 500 题；
- 五个能力：information extraction、multi-session reasoning、temporal reasoning、knowledge update、abstention；
- 当前只跑 100 题 retrieval；需要补 QA 与 abstention。

验收：

- retrieval recall@5 / MRR；
- answer accuracy；
- abstention accuracy；
- 分题型报告，不只总分。

### 3.2 GroupMemBench

依据：[GroupMemBench](https://ar5iv.labs.arxiv.org/html/2605.14498)

- 多人群聊、speaker grounding、ToM/audience vocabulary；
- 强系统平均仅 46.0%，knowledge update 27.1%，term ambiguity 37.7%；
- BM25 可匹配多数系统，说明结构化/speaker 条件比“堆向量”更重要。

验收：

- 六类问题分项；
- answer accuracy + cost + storage；
- 与当前 BM25/RRF 基线对比。

### 3.3 CharacterEval

依据：[CharacterEval](https://ar5iv.labs.arxiv.org/html/2401.01275)

- 1,785 段中文角色对话、77 角色、13 指标/4 维度；
- 只迁移指标与协议，不直接套既有角色知识；
- CharacterRM 只作辅助，不作唯一门禁。

验收：

- 角色一致性、知识一致性、真人感、共情、表达多样性；
- 与人工历史标签对照，不新增真人测试。

---

## 4. P2：已有标签/理论可完成的校准

### 4.1 Stance 系数（数据审计后暂停）

- 现有 90 组 pairwise 是**模型 A/B**，不是 stance 偏移标签；
- 审计见 [STANCE_CALIBRATION_DATA_AUDIT.md](../STANCE_CALIBRATION_DATA_AUDIT.md)；
- 不能用它拟合 `STANCE_MAX_POINTS`；
- **保持 `fit_pending`**，不跑序数回归，不新增手调值。

### 4.2 Dormant 策略

- 不拍“多少天不活跃”；
- 先查 ACT-R/遗忘曲线与公开实现；
- 无来源则不实现，保留 dormant 类型。

### 4.3 ACT-R base-level

- 公式：`B_i = ln(Σ t_j^-d)`；
- `d` 必须有 ACT-R 公开来源；无来源不实现；
- 先 shadow，与 recency 做留一消融。

来源：[ACT-R subsymbolic notes](https://people.ucsc.edu/~abrsvn/ACT-R_subsymbolic_3.pdf)（需核对可访问副本）。

---

## 5. P3：实验型检索增强

### 5.1 HyDE

依据：[Gao et al., ACL 2023](https://virtual2023.aclweb.org/paper_P4221.html)

- 先生成假设文档 → embedding → 检索；
- shadow 记录原 query vs HyDE top-k；
- 成本/延迟/召回；A/B 通过才启用。

### 5.2 RAPTOR

依据：[Sarthi et al., 2024](https://export.arxiv.org/abs/2401.18059)

- 只对 episodic/session 建树；
- 根节点不替代原始证据；
- 需要规模/聚类数据，暂列 P3。

### 5.3 语义 support gate

当前只有 `BM25>0`；真实 query 有“串/号/五抽”误命中。

- 用现有 6 条 support 做 leave-one-out；
- 比较 BM25 gate vs embedding/LLM gate；
- 没有可靠标签就不替换。

---

## 6. P4：多 venue 与观察语料

- 扩展 QQ 群/私聊：直接互动，高价值；
- B 站评论区：只作 observation corpus，不进 trait evidence；
- 需要 ToS/隐私/限速；
- 先做 response attribution，再扩 venue。

---

## 7. 依赖图

```text
P0 response attribution
  ├─→ social reward / evidence（后续）
  └─→ 多 venue 数据质量评估

P1 LongMemEval 500 / GroupMemBench / CharacterEval
  └─→ 外部有效性（独立）

P2 stance / dormant / ACT-R
  └─→ 生命周期校准（依赖 P0 的 outcome 数据）

P3 HyDE / RAPTOR / semantic gate
  └─→ 检索增强（依赖 P1 评测）

P4 multi-venue / observation corpus
  └─→ 数据规模（不得绕过 P0/P1）
```

---

## 8. 分阶段交付

| 阶段 | 交付 | 进入条件 |
|---|---|---|
| R1 | Response attribution schema + shadow + 30 条核对 | ✅ 2026-11-01 shadow 已跑：1654 outcomes |
| R2 | LongMemEval 500 retrieval + QA/abstention | 🟡 500 retrieval 完成（52.8%）；30 QA 10/30；oracle 24/25；top5 gold 13/30；500 hybrid=0.954/0.892；QA 417（CoT 431，top10 430）/500；内部 70/70 |
| R3 | GroupMemBench 四域 metadata 48.6/52.6/48.3/57.8；KU 日期排序负结果；CharacterEval 缺 CharacterRM | 数据/许可 |
| R4 | dormant/ACT-R 研究；stance 暂缓（无对照标签） | 来源/数据 |
| R5 | HyDE/RAPTOR/semantic gate shadow | R2 基线 |
| R6 | 多 venue/observation corpus | P0 稳定 |

---

## 9. 现在不做什么

- 不把 B 站评论直接写 trait evidence；
- 不新增无来源的 dormant 天数；
- 不把 LLM judge 当门禁；
- 不为了 support 数量放宽词法/语义条件；
- 不在没有外部 benchmark 的情况下宣称“生产级”。

---

## 10. 结论

> 现有系统的下一步不是“堆更多内容”，而是**先建立可归因的互动反馈，再补全外部评测，最后才扩数据源**。

本计划先落文档，后续每阶段按 shadow → benchmark → live 推进；任何结论回填本文与 `CURRENT_STATE`。
