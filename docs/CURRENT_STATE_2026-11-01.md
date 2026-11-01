# EchoMind 当前真实状态（2026-11-01）

> 本文件是当前状态的**单一入口**。历史规划、旧阶段文档中的数字如果与本文件冲突，以本文件为准。
>
> 一句话：**人格与记忆的工程闭环已经真实跑通；但“真人感”和外部有效性还没有达标。**

---

## 1. 当前生产基线

| 项 | 当前值 |
|---|---|
| 测试门禁 | **393 passed / 93%** |
| Persona/Memory Eval | **70/70** |
| 参数账本 | **59 compliant** |
| 服务 | 3310 / 3312 正常 |
| active trait | **2**：45 看图、66 发语音 |
| legacy trait | **0**（7 条无证据 legacy 已删除并备份） |
| trait evidence | **16** 条真实证据 |
| shadow 行 | **68** 条历史；active 后 **56** 条非空 |
| trait memory links | **58** 条：6 条 support、其余 context |
| interaction outcomes | **1654**（1333 mention / 321 temporal） |
| semantic facts | **221** |
| episodic memories | **209** |
| prompt | **active-only** |

健康接口：

```json
{
  "status": "ok",
  "active_traits": 2,
  "shadow_since_activation": 56,
  "nonempty_shadow": 56,
  "causal_links": 6,
  "facts_with_turn": 2
}
```

---

## 2. 人格模型现在是什么

```text
7D 慢基线
  + 快状态
  + 每日结算
  + 关系/立场
  + trait 证据与生命周期
  → active-only prompt
```

### 已实现

- 7D 人格慢基线 + 快状态 + 日结算；
- trait evidence 账本：真实 quote、context、polarity；
- Beta(1+s, 1+c) 后验 + 至少 2 个独立 context 才 active；
- candidate/active/retired/legacy 状态；
- active-only prompt；candidate/retired 不进入人格；
- CAPS 风格 `situation/behavior/result` 签名；
- 手动 support 向导 + 审计 note；
- trait→记忆 ranker：support 经词法门控进入 RRF；
- action eligibility：工具额外授权 + active taboo 拒绝许可；
- shadow：每轮记录 active trait、允许工具、实际工具；
- 只读叙事投影（不进入 prompt）；
- 健康/证据/风格 API。

### 当前水平

- 有真实 active trait，但只有 2 条；
- 自动 support 仍稀有，6 条 support 全部是手动确认；
- `dormant` 只有类型，没有时间窗策略；
- 自动 candidate→active 已有结构评审器，但生产 pending candidate=0；
- 叙事投影 A/B 无稳定收益，因此不接 prompt；
- 风格：7 天平均 41.6 字、长句率 33.6%、括号动作 10.1%；最近 24h 约 28 字、长句率 14%、括号动作 3.2%；
- 还没有稳定达到“1–2 句、尽量 ≤26 字”。

**定位：可审计的自演化人格原型，不是成熟生产级人格模型。**

---

## 3. 记忆模块现在是什么

### 检索

```text
BM25
+ bge-m3 dense
+ recency
+ order
+ relation PPR
+ confidence
+ lock
+ trait support（可选）
→ RRF(k=60)
```

- 不手调 ranker 权重；
- trait support 只对 active trait + support link 生效；
- support 有 BM25>0 的词法门控；
- 隐私/secret 硬门在检索之前。

### 存储

- SQLite WAL；
- semantic facts / episodic cards / claims / evidence；
- memory relations / memory vectors / memory knowledge；
- claims 已补 provenance 和带隐私过滤的 `FACTS_V2` 读路径；
- `FACTS_V2` 默认仍关闭，线上读 legacy facts；
- semantic fact 支持 `valid_to_ms` 失效时间。

### 真实效果

- support 手动对照：memory 359 从 44→6，361 从 30→4；
- 真实 20 query 审计：3 改善 / 77 不变 / 0 恶化；
- 但存在“串/号/五抽”这类弱词法命中，不是语义级；
- LongMemEval-S 500 题：session recall@5 **95.4%**，MRR **0.892**（conditional ranker 后；旧 hybrid 为 52.8%/0.375，BM25-only 为 94.0%/0.868）；
- LongMemEval 500 QA：non-CoT **417/500 (83.4%)**，CoT **431/500 (86.2%)**，top10 **430/500 (86.0%)**（均为评测开关，不改 live prompt）；30 题样本 23/30；oracle reading 24/25。GroupMemBench、CharacterEval **未做**。

**定位：小规模、混合检索完整的工程原型；不是生产级记忆系统。**

---

## 4. 真实自演化闭环

```text
真实回合
  → shadow
  → 真实 evidence
  → active trait
  → context / manual support
  → 词法门控 ranker
  → active-only prompt
  → action eligibility
```

已经验证：

- 真实 image/feiyu 回合能写 evidence；
- 53+ 条 shadow 均记录 `[45,66]`；
- 手动 support 能改变真实排序；
- 同回合 explicit fact 能产生 context→support 升级；
- 受控 replay 在临时库验证了完整 support/ranker 路径。

---

## 5. 已完成 / 部分完成 / 数据依赖

### 已完成

- A1 trait evidence 账本；
- A3 active-only 可见性；
- A5 trait→记忆；
- A6 action eligibility（additive + refusal permission）；
- B4 claims provenance/read path；
- B5 disclosure knowledge；
- B6 fact validity；
- C5 风格监控；
- D1 硬编码自称清理核查；
- D2 bond event 接线；
- G1 结构评审自动晋升器；
- G2 只读叙事投影。

### 部分完成

- 自动 support 仍稀有；
- dormant 策略未实现；
- support ranker 仍是 presence-only；
- action eligibility 硬限制模式未启用；
- 7D ↔ Big Five/HEXACO 未映射；
- 立场系数仍 pending。

### 需要长期数据/外部集

- G3 语义 support 门控；
- G5 dormant 时间窗；
- G6 support 强度校准；
- G7 风格拦截；
- G8/C2/C3/C4 外部 benchmark；
- A8–A10 构念/标签/外部人格集；
- B1 ACT-R、B2 HyDE、B3 RAPTOR、B7 ANN；
- D3/D4 跨群/人工 bond。

---

## 6. 文档入口

- 计划与完整实现记录：[plans/STAGE_41_UNFINISHED_REMEDIATION_AND_SELF_EVOLUTION_PLAN.md](plans/STAGE_41_UNFINISHED_REMEDIATION_AND_SELF_EVOLUTION_PLAN.md)
- 下一阶段能力完善计划：[plans/STAGE_42_CAPABILITY_COMPLETION_PLAN.md](plans/STAGE_42_CAPABILITY_COMPLETION_PLAN.md)
- 文档索引：[docs/README.md](README.md)
- 人格状态：[PERSONA_STATUS_CN.md](PERSONA_STATUS_CN.md)
- 自演化状态：[PERSONA_SELF_EVOLUTION_STATUS_CN.md](PERSONA_SELF_EVOLUTION_STATUS_CN.md)
- 能力台账：[capabilities.json](capabilities.json)
- 风格监控：[PERSONA_STYLE_MONITORING.md](PERSONA_STYLE_MONITORING.md)

---

## 7. 关键产物

- `eval/baselines/ranker-support-6links-gated-2026-11-01.json`
- `eval/baselines/support-live-queries-2026-11-01.json`
- `eval/baselines/narrative-prompt-ab-2026-11-01.json`
- `eval/baselines/controlled-replay-2026-11-01.json`
- `eval/baselines/trait-health-2026-11-01-manual.json`
- `eval/baselines/deleted-legacy-traits-2026-11-01.json`
