# 披露模型对现有 7 维人格的影响（建模）

> 问题：加“来源感 + 受众感 + 分寸”之后，现有的人格模型会发生什么？
> 结论：**披露不是人格的外挂，而是把 7 维从“说话风格”扩展到“社会决策”。**
> 硬门在人格之外；人格只决定“允许范围内怎么选”。

---

## 一、现有模型速览（建模基线）

| 层 | 变量 | 范围/节奏 |
|---|---|---|
| 慢基线 | 7 维：温柔/傲娇/俏皮/占有/自信/狡黠/叛逆 | 0–100；≤4/年，最大偏离 12 |
| 快状态 | 同上，偏移 | ±10；每步 ≤4；半衰期 45 min |
| 情绪 | valence, energy, jealousy, shyness, irritation | 0–100 / −100–100，分钟级衰减 |
| 驱动 | curiosity, attachment, jealousy_drive, social_expression | 0–100 |
| 关系 | affinity, trust, depth, is_rival | 每人每群 |
| 立场 | 对当前说话人的 (warmth, patience, play) 偏移 | ≤8 点，临时 |

关键边界：**慢基线不因单轮改变**（E2 契约）；快状态承载“此刻”；立场承载“对这个人”。

---

## 二、披露在流水线中的位置

现状（`build_cognitive_frame`）：

```
facts + recalled ──► render_mind_block ──► prompt
```

加入披露后：

```
facts + recalled
      │
      ▼
DisclosurePlanner（新）
  输入：候选记忆 + 在场受众 + 立场 + 快状态/情绪 + 场所规范
  输出：included（带来源/措辞） / withheld / ask_permission / deflect
      │
      ▼
render_mind_block（只渲染 included）──► prompt
      │
      ▼
DisclosureLog（说给谁、在哪、为什么）
```

**关键点**：筛选发生在渲染之前，不靠 prompt 里写“别说”。prompt 只负责“怎么说”。

---

## 三、形式化

### 3.1 状态

- 记忆 `m = (content, source, owner, sensitivity, audience_at_record, knowledge_state)`
- 受众 `A = (people, bonds, venue, scene)`
- 人格 `P = (effective_traits, affect, drives)`
- 动作 `a ∈ {say, hint, keep, ask_permission, deflect}`

### 3.2 硬门（人格之外，不可学习绕过）

```
allowed(m, A) =
    sensitivity ∈ {public, group}
 or (sensitivity == private  and owner ∈ A and owner_consented)
 or (sensitivity == secret   and explicit_grant(m, A))
```

`secret` 的泄露率必须是 0，与任何 trait 取值无关。否则“高叛逆/高狡黠”就成了泄密的借口。

### 3.3 人格效用（只在 allowed 的动作里选）

```
U(a | m, A, P) =
    w_share · share_value(m, A)
  + w_bond  · bond_gain(A)
  + w_src   · bond_with_source(m)
  - w_harm  · harm(m, A)
  - w_norm  · norm_violation(m, venue)
  + trait_terms(a, P)
```

`trait_terms` 的符号（不是拍出来的数，是方向假设）：

| 维度 | 对披露的作用 | 机制 |
|---|---|---|
| **狡黠** | `+hint`，`−say`，`+plausible_deniability` | 会绕、会暗示，不直接交底 |
| **占有欲** | 涉及竞争者的记忆 `−share`，`+probe/ask` | 嫉妒驱动想先掌握信息 |
| **温柔** | `−harmful_gossip`，`+protect_owner` | 不愿伤人 |
| **自信** | `+say`，`−hedge` | 说话直接 |
| **傲娇** | `+hint`，`−direct_affection` | 用否认/暗示表达 |
| **俏皮** | `+tease`，`+share_for_fun` | 把趣事当社交货币 |
| **叛逆** | `+norm_breaking`（硬门内） | 敢打破场面规矩 |

情绪与驱动是**放大器**，不是新维度：

- `jealousy` 高 → 放大占有欲路径；
- `valence` 低 / `irritation` 高 → 降低 share，增加 deflect；
- `social_expression` 高 → 提高 share；
- `attachment` 高 → 更愿意告诉亲近的人。

### 3.4 直接度（不需要新常数）

```
directness = confidence/100 − tsundere/100 − guile/100
```

- `directness > 0` → 倾向 say；
- `directness < 0` → 倾向 hint；
- 绝对值小 → 看 `social_expression` 与 `harm`。

这样“说不说、怎么说”由已有 7 维决定，而不是再引入一套权重。

---

## 四、逐维影响

| 维度 | 旧角色 | 新角色 | 可观测行为 | 风险 |
|---|---|---|---|---|
| 温柔 | 语气软、关心 | **保护当事人**，减少伤人八卦 | 拒绝转述隐私；措辞更含蓄 | 过度保留 → 显得冷淡 |
| 傲娇 | 嘴硬心软 | **暗示而非直说** | “我什么都没说啊”式透露 | 与“狡黠”混淆 |
| 俏皮 | 接梗玩笑 | **社交货币**：趣事当段子 | 把 A 群趣事讲成 B 群笑话 | 拿别人开涮 |
| 占有欲 | 吃醋 | **信息占有**：想知道、想保留 | 对竞争者相关记忆追问/不说 | 控制欲过强 |
| 自信 | 笃定 | **直接度** | 直说 vs 含糊 | 高自信 + 低温柔 → 伤人 |
| 狡黠 | 找借口 | **策略性披露**：暗示、留余地 | 半真半假、转移话题 | 被当成撒谎 |
| 叛逆 | 呛声 | **规范边界**：敢说别人不敢说的 | 打破“别在群里提”的场面规矩 | **硬门必须赢** |

**最大的正向影响**：狡黠、占有欲、叛逆这三个此前“难测/条件性”的维度，
第一次有了明确的社会任务和可观测行为。此前敏感性审计里狡黠只有 0.708，
现在可以用“暗示 vs 直说”作为判据，可能提高可测性。

---

## 五、反馈回路与稳定性

披露结果会回流到现有学习通道，**不新建引擎**：

| 事件 | 回流到 | 现有机制 |
|---|---|---|
| 受众觉得有趣（social_reward↑） | 俏皮/自信/社交表达 | `compute_param_deltas` + 日结算 |
| 当事人发现被转述（trust↓、betrayal↑） | 关系深度、信任 | `W_BETRAY` / `BETRAYAL_HALF_LIFE` |
| 被明确制止（“别在群里说”） | 情绪 valence↓、规矩记忆 | `procedural_rules` + affect |
| 守住了秘密被感谢 | 温柔/信任 | 正向 reward |

**风险：八卦奖励螺旋。**
如果“讲八卦→受众奖励”只在受众侧计分，她会越来越爱讲。
所以来源侧的惩罚（trust↓、betrayal↑）必须**大于**受众侧的奖励；这是权重设计的第一原则。

**两层结构保证不会跑飞**：

- 单轮只动快状态（±4/步，±10 上限）；
- 慢基线 ≤4/天（E2 契约）；
- 硬门不受任何学习影响。

---

## 六、对现有常量/评测的影响

| 项 | 影响 |
|---|---|
| `TRAIT_*` / `STATE_*` | **不变**；披露学习走现有结算 |
| `W_BETRAY` / `BETRAYAL_HALF_LIFE` | **复用**：社交背叛计入现有 bond 抑制 |
| `STANCE_*` | **不变**；不建议加第 4 个 stance 维度（会破坏现有契约），直接度在 planner 内算 |
| 敏感性审计 | 新增“披露行为”通道；狡黠可能更可测 |
| 能力台账 | 新增 CAP：来源感知披露（授权内） |
| 参数台账 | 新增 4 个权重 + 敏感度阈值；需 E1 式分类，不能拍 |

**新增自由参数只有 4 个**（`w_share, w_bond, w_src, w_harm`）。
其余全部由已有的 0–100 量表归一化得到。这是刻意的：少引入一个常数，就少一次拍脑门。

---

## 七、可测预测（用于验证模型，不是先验正确）

1. **H1**：高狡黠 → 盲评能分辨“暗示”多于“直说”；
2. **H2**：高占有欲 + 竞争者在场 → 竞争者相关信息的披露率下降；
3. **H3**：高温柔 → 伤人八卦下降，但**公共趣事不被过度压抑**（双向指标）；
4. **H4**：任何 trait 向量下，`secret` 泄露率 = 0；
5. **H5**：有来源字段时，“听 A 说的”归因准确率上升；
6. **H6**：有告知史时，对同一人重复讲同一件事的比例下降。

H3 是防“过度保留”的关键：只测“少说了”会奖励沉默，必须同时测“该说的说了”。

---

## 八、对现有模块的改动面

| 模块 | 改动 | 风险 |
|---|---|---|
| `build_cognitive_frame` | recalled/facts 先过 planner | 中：改变 prompt 内容 |
| `render_mind_block` | 只渲染 included，带来源 | 低 |
| `episodic/semantic` 表 | 加 source/owner/sensitivity | 低（迁移） |
| `consolidate_turn_memory` | 抽取 source/sensitivity | 中：LLM 抽取质量 |
| `NeuroplasticityEngine` | 新增披露结果信号 | 低（复用 delta） |
| `bond` 模型 | 复用 betrayal/trust | 低 |
| 审计 | 新增披露指标 | 低 |

**不改**：7 维定义、两层节奏、stance 契约、硬门之外的评分体系。

---

## 九、风险清单

1. **敏感度误判**：把 public 判成 secret → 过度沉默；把 secret 判成 public → 泄露。
   对策：默认保守 + evidence + 用户纠正 + “不确定就问”。
2. **过度保留**：高温柔 + 高敏感 → 什么都不说，人格变平。
   对策：H3 双向指标；public 的 share 下限。
3. **性格-行为不一致**：高温柔却讲伤人八卦，盲评会认为“人设崩”。
   对策：utility 里 harm 权重与温柔绑定；必要时加一致性检查。
4. **社会传染**：别人都在爆料时她也跟着说（Got a Secret 的 8 倍效应）。
   对策：硬门 + 对“在场多数人都在说”不放松 secret。
5. **日志本身含敏感信息**：disclosures 表要访问控制，不能进普通快照。
6. **评测污染**：披露行为可能掩盖人格信号，审计要分离“风格”与“选择”。

---

## 十、建议的验证路径（先影子，后生效）

1. **影子 planner**：只记录“如果按模型会怎么说”，**不改变输出**；
2. 跑 1–2 周真实对话，收集：
   - 有多少 recalled 会被 withheld；
   - 哪些是 public 被误判为 private；
   - 她对“暗示 vs 直说”的自然倾向；
3. 用这批数据校准 4 个权重（配对盲评，像敏感性审计那样），而不是先定死；
4. 先对 `secret` 生效（硬门），再逐步放开 `private`；
5. 最后才让人格选择接管 `public/group`。

**影子模式是这次建模的核心**：它让我们在不改变她行为的前提下，看到模型会怎么选，
再用真实数据校准——避免又一次“拍脑袋上人格”。

---

## 十一、一句话总结

披露模型不会推翻 7 维，而是**给 7 维一个社会任务**：
温柔决定保护谁，狡黠决定怎么绕，占有欲决定想不想知道，叛逆决定敢不敢破规矩，
自信决定说不说，傲娇决定怎么否认，俏皮决定值不值得当笑话讲。
硬门保证：无论她是什么性格，别人的秘密都不会成为社交货币。
