# 让人格真正自演化：设计

> 目标不是“参数会动”，而是：
> **经历能长出特质 → 特质改变她想起什么/怎么做 → 新行为产生新经历 → 再强化或推翻特质。**

现在的系统只有第一段：参数会漂。缺的是后两段。

---

## 1. 先定义：什么才算自演化

最低标准（MVP）：

1. **记得为什么变**：每条特质有证据，不是一句固定文案；
2. **会筛选**：证据不足的不进人格，反证多了会退场；
3. **会复利**：特质影响记忆检索，记忆再影响行为；
4. **会稳定**：不会一轮变一个人，不会振荡；
5. **可回滚**：能看见“她为什么变成现在这样”。

不包含：

- 自己改代码；
- 自己改 prompt 结构；
- 自己生成价值观；
- 无限制地改 7 维。

这些不是自演化，是失控。

---

## 2. 目标闭环

```
对话/事件
  ↓
ExperienceEvent（发生了什么、她做了什么、结果如何）
  ↓
TraitEvidence（支持/反证，带原话和场景）
  ↓
Trait 生命周期：candidate → active → dormant/retired
  ↓
active trait 进入：
  ├─ prompt 人格块
  ├─ 记忆检索（trait resonance）
  └─ 行为资格（哪些主动行为允许出现）
  ↓
新行为 → 新经历 → 再更新证据
```

关键：**trait 不是只影响“怎么说”，还要影响“想起什么”和“做不做”。**

---

## 3. 第一阶段：把“证据”做成真账本

### 现状

`persona_traits` 只有：

- `evidence_count`
- `contradiction_count`
- `last_evidence_ms`

没有：

- 哪一轮、哪句话是证据；
- 证据属于哪个场景；
- 是支持还是反证；
- 证据是否来自独立场景。

### 改造

新增表 `trait_evidence`：

```sql
trait_evidence(
  id,
  trait_id,
  session_id,
  turn_id,
  quote,           -- 原话/行为片段，必须能在原文找到
  polarity,        -- +1 支持 / -1 反证
  context_hash,    -- 场景指纹，防止同一场景刷证据
  created_ms
)
```

`evidence_count` / `contradiction_count` 从表里派生，不再手工 +1。

### 特质生命周期

- **candidate**：出现一次，只记录，不进 prompt；
- **active**：至少在 **2 个独立场景**有支持证据，且没有明显反证；
- **dormant**：长期无强化，强度衰减；
- **retired**：反证超过支持，或长期不用。

“2 个独立场景”不是拍脑袋阈值，是最低可判别条件：  
一次只能说明“这次这样”，两次不同场景才能说明“她倾向这样”。

### 为什么先做这个

没有证据账本，后面的“筛选/淘汰/回滚”都做不了；  
现在的 `evidence_count` 只是计数，不能解释“为什么留下”。

---

## 4. 第二阶段：让特质从经历里长出来，而不是 5 条固定文案

### 现状

`derive_emergent_trait` 只有 5 个 if：

- 被命令 → 讨厌工具人；
- 被冒充 → 拆穿；
- 看图 → 看细节；
- 发语音 → 直接说；
- 查梗 → 现学现卖。

这不是成长，是**条件触发的固定台词**。

### 改造

1. 每条 `ExperienceEvent` 记录：
   - 场景（群/私聊、对象、话题）；
   - 她的行为（说了什么/用了什么工具/拒绝还是接）；
   - 结果（接茬、冷场、冲突、被夸）；
   - 情绪/驱动变化。
2. **模式挖掘**：只在同一类场景重复出现时，生成 candidate；
3. **LLM 只做总结，不做发明**：
   - 输入是证据原话；
   - 输出必须是 `{category, trait_text, evidence_quotes}`；
   - `evidence_quotes` 必须能在原文中找到，否则丢弃；
4. 人工不参与；用结构校验 + 反证测试防胡编。

这样 trait 文本可以随经历变化，而不是永远那 5 句。

---

## 5. 第三阶段：trait → 记忆检索（复利）

### 现状

- 记忆影响 trait/state；
- trait 不影响检索；
- 所以她“变温柔”不会优先想起照顾类记忆。

### 改造

新增 `trait_memory_links`：

```sql
trait_memory_links(
  trait_id,
  memory_kind,   -- semantic / episodic
  memory_id,
  relation,      -- supports / contradicts
  evidence_ms
)
```

检索时加一个 **trait ranker**：

- 只对 active trait 生效；
- 事实/情节与 trait 有 link 的，排名上升；
- 和现有 BM25/dense/recency/order/relation/confidence/lock 一样走 RRF；
- 不引入手调权重。

同时做 **trait-conditioned query expansion**：

- active trait 提供主题词（照顾/竞争/新奇/边界）；
- 只扩展检索，不改用户原话；
- 硬门（private/secret）仍在检索后、渲染前。

### 验收

- 同一问题，开/关 trait ranker，比较召回的记忆类型；
- 检查隐私/边界不退化；
- 用 hard negatives 防止“ trait 把无关记忆拉上来”。

---

## 6. 第四阶段：trait → 行为资格（不是打分）

不要给 trait 加一个“行为权重”，那会变成拍数值。

用**资格门**：

- active `boundary` trait → 允许“拒绝/冷处理”动作；
- active `care` trait → 允许“主动关心/追问”动作；
- active `novelty` trait → 允许“搜索/玩梗/探索”动作；
- 没有对应 trait → 动作不进入候选。

这样行为变化可解释：**不是“权重高了 0.2”，而是“她长出了这个倾向，所以这类动作被允许”。**

---

## 7. 第五阶段：长期漂移评测（先能测，再谈调）

没有这个，前面全是盲改。

设计 **counterfactual replay**：

- 同一初始人格；
- 三条经历流：
  - A：持续被温柔对待；
  - B：持续被冒犯；
  - C：混合/矛盾；
- 每条跑 30 天；
- 看：
  - trait 是否按证据出现/退场；
  - 7 维漂移是否在预算内；
  - 行为是否跟着变；
  - 是否振荡/身份崩坏；
  - 隐私/边界是否退化。

不需要真人标注；这是**结构一致性测试**，不是“好不好玩”。

---

## 8. 优先级（不要一次全做）

### P0：证据账本 + 生命周期

- `trait_evidence` 表；
- candidate/active/retired；
- prompt 只读 active；
- 不动 7 维预算。

### P1：trait 文本生成

- 用证据模式 + LLM 总结；
- 替换固定 5 条；
- 结构校验 + 原文引用校验。

### P2：trait → 记忆检索

- `trait_memory_links`；
- trait ranker 进 RRF；
- 隐私/边界回归。

### P3：trait → 行为资格 + 长期 replay

- 资格门；
- 30 天 counterfactual；
- 再谈是否调 7 维/立场系数。

---

## 9. 一句话

**先让她“记得为什么变”，再让她“因为变了而想起不同的事”，最后才谈“变成什么样”。**

没有证据账本和 trait→memory，7 维调得再细，也只是漂移，不是自演化。
