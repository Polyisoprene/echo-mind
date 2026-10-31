# 全局修复模型与接入影响评估

> 日期：2026-10-31 ｜ 范围：人格/记忆文档中的 P0/P1/P2 + 当前代码
> 结论：**现在不是“已修复”，而是多个局部增强叠加。** 继续加 boost 会把问题藏得更深；应先合并成一个可校准的评分器，并把所有数值参数纳入同一张依赖图。

---

## 0. 一句话结论

当前检索链路有三套打分：

1. 关键词：`overlap*3 + 主体*6 + locked*5 + confidence + recency*4 + order*6`
2. 语义：`cosine + recency*0.25 + order*0.5`
3. RRF 融合后，再用关系可达性做一次“命中前置”

问题不是“某个参数不够好”，而是：

- 同一个 recency/order 在两路各加分一次，RRF 又会放大两路共识；
- 关系命中在 RRF 之后直接前置，绕过了融合分数；
- `memory_relations.valid_from/to` 和 `confidence` 有字段但没参与；
- 多个参数是内联字面量，账本看不到，无法联动校准；
- 30 天半衰期、4/6 权重、0.25/0.5、2 跳、0.8 置信度都没有直接论文依据。

---

## 1. 当前全局数据流

```
percept
  │
  ├─ 硬门（private/secret；先于任何打分）
  │
  ├─ 关键词 rank
  │    overlap*3 + subject*6 + lock*5 + confidence
  │    + recency*4 + entity_order*6
  │
  ├─ 语义 rank
  │    cosine + recency*0.25 + entity_order*0.5
  │
  ├─ RRF(k=60)  ← 两路 rank 融合
  │
  ├─ relation boost ← 关系可达事实直接前置（无 validity、无 confidence）
  │
  └─ top-k → prompt
```

**同一信号被重复计分**：recency 和 order 在关键词、语义两路都出现，再经 RRF 融合。  
**关系通道是后置补丁**：不在统一分数里，无法与 recency/importance 比较。  
**validity/confidence 是孤岛**：字段存在，但不影响边是否 active、也不影响 boost 大小。

---

## 2. 参数审计（当前值 + 证据状态）

| 参数 | 当前值 | 位置 | 现状 | 证据状态 |
|---|---:|---|---|---|
| `FACT_RECENCY_HALF_LIFE_DAYS` | 30 | `mind/ebbinghaus.py` | 时间衰减半衰期 | ❌ 无直接来源；fit_pending |
| `FACT_RECENCY_WEIGHT` | 4.0 | 同上 | 仅评测基线 `select_relevant_facts`；live 全部用 recency ranker | ❌ 无来源；convention |
| `ENTITY_ORDER_WEIGHT` | 6.0 | 同上 | 仅评测基线 `select_relevant_facts`；live 全部用 order ranker | ❌ 无来源；convention |
| 语义 recency 权重 | 已删除 | `mind/semantic_retrieval.py` | 语义排序改纯 cosine | ✅ 消除重复计分 |
| 语义 order 权重 | 已删除 | `mind/semantic_retrieval.py` | 语义排序改纯 cosine | ✅ 消除重复计分 |
| `RRF_K` | 60 | `mind/retrieval_fusion.py` | 7 路 rank 融合 | ✅ Cormack et al. 2009 常用值 |
| 关系跳数 | 已删除 | `domain/relation.py` | 改为 Personalized PageRank | ✅ 不再需要固定跳数 |
| `RELATION_CONFIDENCE` | 0.8 | `mind/relation_extractor.py` | 抽取置信度 | ❌ 未参与排序；值无来源 |
| 关系 validity | 字段存在 | `memory_relations` | 已按 `valid_from/to` 过滤 | ✅ 已接入 |
| BM25 K1/B | 1.2 / 0.75 | `mind/ranker_fusion.py` | 词面 ranker 参数 | ✅ Robertson & Zaragoza 2009 默认值 |
| PPR damping/iter/tol | 0.85 / 100 / 1e-6 | `domain/relation.py` | 图传播 | ✅ NetworkX 默认 + HippoRAG 思路 |
| 真人感长度 | 26 字 | `personality.REALISM_MAX_CHARS` | 已收常量/账本，prompt 软约束 | ✅ 高分组 n=19：中位 15、p75 20、max 26 |

### 人工标签对“40 字”的实际支撑

50 条人工总体分中：

- 高分（4–5）n=19：长度中位数 **15**，p75 **20**，最大 **26**；
- 低分（1–2）n=13：中位数 16，最大 85。

结论：**40 字不是数据支持的阈值**；高分组最大 26 字，因此上限收敛到 26（不再加无依据的余量）。长度也不是唯一因素，不能只靠截断。

---

## 3. 公开论文/仓库依据

| 方法 | 可用的依据 | 对本项目的含义 |
|---|---|---|
| RRF | Cormack et al., SIGIR 2009, k=60 | `RRF_K=60` 可保留；但 RRF 是 rank 融合，不是加权分数 |
| Generative Agents | Park et al. 2023 + 官方 `retrieve.py` / `scratch.py` | 它用 recency/importance/relevance 三特征，代码里 `recency_decay=0.99` 是**按节点序号**衰减，不是 30 天时间半衰；`gw=[0.5,3,2]` 是经验权重，不是 universal |
| ACT-R | Anderson et al. 2004 | 若要叫 ACT-R，应实现 base-level `B_i=ln(Σ t_j^-d)` + spreading + partial matching；当前只有指数 recency |
| HippoRAG | Gutiérrez et al. 2024 | 多跳用 Personalized PageRank，不是固定 2 跳；`max_hops=2` 没有论文依据 |
| Zep/Graphiti | Rasmussen et al. 2025 | 时间知识图应带 bi-temporal validity；我们的 `valid_from/to` 有字段但没参与检索 |
| BGE | BAAI/bge-small-zh-v1.5 | 512 维、模型隔离是模型事实，不是打分参数 |
| 人工标签 | 本项目 50 条 + 90 组成对 | 可用于风格/长度约束；不能反过来证明 30 天/4/6/0.25/0.5/2/0.8 |

**结论：目前只有 RRF_K、BGE 维度和人工风格长度有依据；其余 7 个数值没有直接证据，不能继续当作“科学默认值”。**

---

## 4. 参数联动矩阵

| 参数 | 应该影响 | 现在影响 | 缺口 |
|---|---|---|---|
| `event_time` | recency、关系 validity、时间顺序 | 只影响 recency | 关系边不按时间过滤 |
| `valid_from/to` | 关系是否 active、多跳路径 | 已过滤过期边 | ✅ |
| relation confidence | 关系特征强度 | 已进入路径分数（连乘） | ✅ 已接入；0.8 本身仍待校准 |
| `max_hops` | 多跳范围/成本 | 固定 2 | ❌ 无图直径/成本约束 |
| lexical recency/order | 关键词排序 | 已加，权重独立 | 与语义权重不一致 |
| semantic recency/order | 语义排序 | 已加，内联 0.25/0.5 | 不在账本、不可联动 |
| lexical/dense | RRF 融合 | RRF(k=60) | 没有权重/校准 |
| importance | 事实/情景排序 | 事实未用；情景用 | 两套记忆不一致 |
| source/scope | 可信度/可见性 | 硬门用 scope；source 未进分 | source 与分数脱节 |
| 风格长度 | 输出 | prompt 软约束 | 40 字无强证据 |

---

## 5. 建议的统一模型（不是再加 boost）

### 5.1 一个 scorer，硬门在外

```
active_relation = valid_from <= now < (valid_to or +inf)
r = normalize(recency(event_time))
g = graph_score(active_relation, confidence)   # PPR / 可达
s = w_l*z(lexical) + w_d*z(dense) + w_r*z(r)
  + w_i*z(importance) + w_g*z(g) + w_s*z(source)
```

- 硬门最先，隐私不参与分数；
- 每个特征先做**同一 query 内归一化**，避免 4/6/0.25/0.5 这种量纲混用；
- 关系只在 valid 时进入 `g`，confidence 作为 `g` 的系数，不再后置覆盖 RRF；
- RRF 只作为“没有校准权重时的 fallback”，不与加权分数同时使用；
- 权重用现有 70 条内部场景 + 50 条人工标签拟合，不拍脑袋。

### 5.2 参数登记

所有数值进入 `docs/params/ledger.json`，并标注：

- `source`：论文/仓库/数据；
- `fit_pending`：未拟合前不得作为生产真值；
- `experimental`：只允许 shadow，不允许进默认路径。

内联字面量（0.25/0.5/2/40）已收进常量/账本；`RELATION_CONFIDENCE=0.8` 已有账本。它们仍标记为 `fit_pending`，不是生产真值。

### 5.3 分阶段接入

| 阶段 | 改动 | 不改什么 |
|---|---|---|
| P0 | ✅ 参数登记；✅ 关系 validity/confidence 接入 | 只改关系边合法性与权重，评测集未退化 |
| P1 | 统一 recency/order，去掉双路重复计分；关系进统一分数；RRF 降为 fallback | 不改硬门、不改隐私 |
| P2 | 用 70 场景 + 50 标签拟合权重；重跑 60/70 关键词、70/70 语义、role/temporal/multihop | 不新增无依据参数 |
| P3 | PPR/树/HyDE 作为独立实验，先 shadow | 不直接改生产 |

---

## 6. 接入后的影响评估（含第 3 轮消融实测）

### 6.0 消融结果（70 条内部场景，语义模式）

| 关闭的特征 | role | temporal | multihop | overall |
|---|---:|---:|---:|---:|
| 不关（基线） | 10/10 | 10/10 | 10/10 | **70/70** |
| recency | 10/10 | **0/10** | 10/10 | 60/70 |
| order | **0/10** | 10/10 | 10/10 | 60/70 |
| recency + order | **0/10** | **0/10** | 10/10 | 50/70 |
| relations | 10/10 | 10/10 | **0/10** | 60/70 |

结论：

- recency 唯一负责 temporal；
- order 唯一负责 role；
- relations 唯一负责 multihop；
- 三个信号不是可有可无的装饰，但**数值大小仍未被证明**；
- **只关关键词侧或只关语义侧的 recency/order，仍然 70/70**：两侧互为备份，证明存在重复计分；两侧同时关才掉到 50/70；
- 因此语义侧 0.25/0.5 已删除，recency/order 只保留在关键词侧；语义排序改为纯 cosine。
- 这也暴露了旧 probe 的缺陷：原 multihop 题面含“工作”，关键词就能命中，关系通道是假通过；已改成无字面重叠并加语义相近干扰项，关系关闭后 multihop 才真的掉到 0/10。

### 6.1 检索

### 6.1 检索

| 维度 | 当前 | 统一 scorer 的预期 | 风险/缓解 |
|---|---|---|---|
| 关键词 recall@5 | 60/70 | 可能变化，必须重跑 | 去掉 4/6 双计分后 role/temporal 可能掉；用校准权重 |
| 语义 recall@5 | 70/70 | 可能变化 | 关系 validity 过滤会减少旧边；先 shadow |
| role / temporal | 10/10 / 10/10 | 不应低于基线 | 归一化后重新校准 order/recency |
| multihop | 10/10（seed） | 真实图更可信 | 线上关系只有 38 条，不能把 seed 10/10 当线上能力 |
| 隐私 | 0 泄露 | 不变 | 硬门仍在最前 |

### 6.2 延迟/成本

- embedding 调用不变（每轮 ≤1 次）；
- validity 过滤是 SQL/内存判断，可忽略；
- PPR 比固定 2 跳贵，需限制节点数/缓存；
- 关系抽取是离线/整合时，不增加每轮 LLM 调用。

### 6.3 人格

- 风格约束只影响输出，不影响检索；
- 40 字改为数据支持的 25–30 字区间更合理，但会牺牲技术/安慰长回答；
- 建议保留“默认短、明确需要时展开”，不做硬截断；
- 人格→记忆耦合（P6）仍未做，trait 不影响检索。

### 6.4 维护性

- 统一 scorer 后，新增特征只需加一列 + 权重，不再加“后置 boost”；
- 参数账本 + shadow 开关让回滚成本低；
- 关系 validity/confidence 接入后，旧关系不会永久污染。

---

## 7. 本轮已经落地的部分

- 语义侧 0.25/0.5 已删除：消融证明只留关键词侧仍 70/70；
- 2（关系跳数）、40（风格长度）已收成显式常量；
- 全部登记到 `docs/params/ledger.json`，状态为 `fit_pending/quarantined`；
- `param_gate` 通过（58 constants compliant）；
- 语义排序改为纯 cosine，关键词侧独占 recency/order，消除双路重复计分；
- 关系 `valid_from/to` 已过滤过期边；`confidence` 已连乘进两跳路径分数；
- 关系命中排序改为按 confidence 从高到低，而不是所有命中一律前置；
- 评测集未退化（关键词 60/70、语义 70/70、multihop 10/10）；
- 新增消融开关：`--ablate recency|order|recency_order|relations`，用于以后每次改评分器复测。
- 30 天/4/6/0.25/0.5/2/0.8 仍登记为 `fit_pending`，没有冒充已校准。

## 8. 不建议做的事

1. 不要继续加“关系命中 +6”之类的后置 boost；
2. 不要把 30 天/4/6/0.25/0.5/2/0.8 当科学默认值；
3. 不要用单模型 judge 绝对分做门禁（QWK 0.097，已证伪）；
4. 不要用 seed multihop 10/10 证明线上多跳能力。

---

## 9. 依据链接

- Cormack et al., *Reciprocal Rank Fusion*, SIGIR 2009. [doi:10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114)
- Park et al., *Generative Agents*, 2023. [arXiv:2304.03442](https://arxiv.org/abs/2304.03442)；官方检索代码 [retrieve.py](https://github.com/joonspk-research/generative_agents/blob/main/reverie/backend_server/persona/cognitive_modules/retrieve.py)，参数 [scratch.py](https://github.com/joonspk-research/generative_agents/blob/main/reverie/backend_server/persona/memory_structures/scratch.py)
- Anderson et al., *An Integrated Theory of the Mind*, 2004. [doi:10.1037/0033-295X.111.4.1036](https://doi.org/10.1037/0033-295X.111.4.1036)
- Gutiérrez et al., *HippoRAG*, 2024. [arXiv:2405.14831](https://arxiv.org/abs/2405.14831)
- Rasmussen et al., *Zep*, 2025. [arXiv:2501.13956](https://arxiv.org/abs/2501.13956)
- BAAI, *bge-small-zh-v1.5*. [Hugging Face](https://huggingface.co/BAAI/bge-small-zh-v1.5)
- Edge et al., *GraphRAG*, 2024. [arXiv:2404.16130](https://arxiv.org/abs/2404.16130)


---

## 10. 第 5 轮落地：live 已切到 ranker fusion

`select_facts` 现在优先调用 `SemanticMemoryRetriever.rank_fused`，内部是：

```
BM25 rank ─┐
dense rank ─┤
recency rank ─┤
order rank ─┼─ RRF(k=60) → facts
relation rank ─┤
confidence rank ─┤
lock rank ─┘
```

- 不再使用关键词公式里的 3/6/5/4/6（仅**无 embedding 的关键词回退**仍保留）；
- 语义侧 0.25/0.5 已删除；
- 所有 ranker 等权，没有手调特征权重；
- 只有 RRF k=60（Cormack）与 BM25 k1/b（Robertson）是数值参数，均有来源；
- 关系 validity/confidence 在 relation ranker 内。

### 实测

| 模式 | role | temporal | multihop | overall |
|---|---:|---:|---:|---:|
| fusion 基线 | 10/10 | 10/10 | 10/10 | **70/70** |
| fusion + 关 relations | 10/10 | 10/10 | **0/10** | 60/70 |
| 关键词基线 | 10/10 | 10/10 | 10/10 | 60/70 |

multihop 现在需要 relation ranker，不再靠字面泄漏通过。

### 仍然存在的债务

- live 已无 3/6/5/4/6；这些只留在评测基线 `select_relevant_facts`；
- 关系跳数已由 PPR 替代；`REALISM_MAX_CHARS=26` 已按人工数据校准；
- 7 个 ranker 等权是“无证据时的保守选择”，不是拟合结果；
- 还没做权重拟合/外部 benchmark。


---

## 11. 第 8 轮：关系图改为 Personalized PageRank

线上关系图实测：

- 49 个节点、39 条边、14 个连通分量；
- 有向最短路最大 4 跳，p95 = 3 跳；
- 原来的 `max_hops=2` 覆盖不了图，不是数据驱动。

已删除 `RELATION_MAX_HOPS`，改为 `ppr(starts, now_ms)`：

- 只走 valid 边；
- 边权 = confidence；
- `damping=0.85, max_iter=100, tol=1e-6` 取自 NetworkX PageRank 默认值；
- 多跳路径不再靠固定跳数。

效果：fusion 基线仍 70/70，关 relations 后 multihop 0/10、overall 60/70。


---

## 12. 第 9 轮：ranker 留一消融（结论：等权未被证明）

对 fusion 逐个关闭 ranker：

| 关闭的 ranker | role | temporal | multihop | overall |
|---|---:|---:|---:|---:|
| 无（基线） | 10/10 | 10/10 | 10/10 | 70/70 |
| confidence | 10/10 | 10/10 | 10/10 | 70/70 |
| lock | 10/10 | 10/10 | 10/10 | 70/70 |
| bm25 | 10/10 | 10/10 | 10/10 | 70/70 |
| dense | 10/10 | 10/10 | 10/10 | 70/70 |
| recency | 10/10 | 10/10 | 10/10 | 70/70 |
| order | 10/10 | 10/10 | 10/10 | 70/70 |
| relations | 10/10 | 10/10 | **0/10** | 60/70 |

结论：

- 只有 relations 在留一消融里是**唯一必需**；
- 其余 ranker 都可被其他 ranker 补偿，说明 70 条 probe 仍然饱和；
- **不能宣称 7 ranker 等权已被数据证明**；它只是无证据时的保守选择；
- 下一步必须构造 hard negatives（同词反向、同主题不同时间、同语义不同关系），否则权重/等权都只是自嗨。


---

## 13. 第 10 轮：hard negatives 证明“每个 ranker 都有独立信号”

为每个 ranker 造一组“只有它能区分”的成对事实：

| ranker | hard negative |
|---|---|
| recency | 同文本、不同事件时间，只有新事实对 |
| order | A→B / B→A 同词反向 |
| dense | 同文本、只有 dense 分数区分 |
| relations | 只有关系可达的目标 |
| confidence | 同文本、不同 confidence |
| lock | 同文本、只有 locked 区分 |
| bm25 | 同主题、只有目标含查询词 |

测试结果（`tests/unit/test_ranker_isolation.py`）：

- **只开该 ranker 时，目标都能赢**；
- 关掉全部 ranker 时，目标输给插入顺序；
- 但在 7 个 ranker 全开、信号冲突时，单个 ranker 可能被其他 ranker 的“平票”稀释（例如 role 反向 probe）。

这证明两件事：

1. 7 个 ranker 不是装饰，每个都有独立可判别的信号；
2. **等权融合在信号冲突时会稀释强信号**，因此“等权”仍未被证明，下一步需要校准/优先级规则，而不是继续加 ranker。



---

## 14. 第 11 轮：显式查询约束，先于 RRF

等权 ranker 在冲突时会稀释强信号。没有给 ranker 拍权重，而是加了一层**查询语义约束**：

- 时间问题（“最近/之前/什么时候/哪里”等）→ 先按事件时间收敛候选；
- 方向问题（“把/给/还给/送给”等，且事实出现正反顺序）→ 先去掉反序事实；
- 其余查询不加约束。

约束是确定性的、可测试的，不引入数值权重：

- `tests/unit/test_query_constraints.py`：方向/时间/普通查询；
- `tests/unit/test_ranker_isolation.py`：7 个 ranker 各自 hard negative。

实测：

- fusion 基线 70/70；
- 关 relations 后 multihop 0/10、overall 60/70；
- 约束前出现的 paraphrase 误伤已修：只有“时间疑问句”才触发时间过滤。

边界：这是中文查询启发式，不是通用语义解析；后续应改为意图分类器/结构化查询。


---

## 15. 第 12 轮：约束触发精度审计

对 70 条检索场景的 query 做触发审计：

- 方向约束：只在 **role 10/10** 触发；
- 时间约束：只在 **temporal 10/10** 触发；
- 其余 50 条（paraphrase/privacy/venue/multihop/persona）**0 误触发**；
- 由 `tests/unit/test_query_constraint_precision.py` 固化，后续加题会直接暴露误触发。

这也修掉了之前“最近胃口不好”被时间约束误伤的问题：只有“最近 + 哪里/什么时候”等时间疑问句才触发。

边界：这是中文启发式，不是通用意图解析；但当前 70 条上 precision 为 1.0，已可回归。


---

## 16. 第 13 轮：清掉 live 的最后两个未校准数值

1. **recency ranker 改按 event_time 原值排序**  
   旧实现调用 `fact_recency(...)`，半衰期 30 天；但在 RRF 里 ranker 只输出排序，指数衰减是单调变换，半衰期完全不影响 rank。因此直接按 `event_time_ms` 排序，remove 了 live 的 30 天依赖。

2. **规则抽取关系 confidence 改为 1.0**  
   正则命中即结构明确，不再用无依据的 0.8；LLM 抽取仍用模型自身 confidence。

现在 live 的数值参数只剩：

| 参数 | 来源 |
|---|---|
| RRF k=60 | Cormack 2009 |
| BM25 k1=1.2, b=0.75 | Robertson & Zaragoza 2009 |
| PPR damping/iter/tol | NetworkX 默认 + HippoRAG |
| 风格长度 26 | 50 条人工高分组 max |
| relation confidence 1.0 | 精确规则无不确定性 |

`FACT_RECENCY_HALF_LIFE_DAYS / FACT_RECENCY_WEIGHT / ENTITY_ORDER_WEIGHT` 与 3/6/5 只留在 **legacy 评测基线** `select_relevant_facts`，不进 live；`fact_shadow` 仍用旧分数，属于后续清理项。

实测：fusion 70/70；关 relations 60/70（multihop 0）；门禁 321 passed。


---

## 17. 第 14 轮：清理 fact_shadow 旧分数

`claim_rank` 原来用 `3/6/5 + 2*belief + 1.5*exp(-age/7)`，全是未校准值。现在改为同一 `unified_rank`：

- 词面 BM25、recency、confidence；
- 对 claim 场景关掉 order/relations/lock（这些对 claim 比较无意义）；
- 不再有 2/1.5/7 这类权重。

`tests/unit/test_fact_shadow.py` 仍验证“近期 + 高 belief”优先和按 slot 去重。

剩余旧权重的唯一位置是 **评测脚本/legacy `select_relevant_facts`**，不进 live。
