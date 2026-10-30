# Stage 31 机器人互刷抑制：社交习惯化与"印象"模型（规划书）

> **状态**：📋 规划待施工（未动代码）
> **前置**：Stage 29（关系深度）、Stage 30（人格动力学）、`docs/CONTRACT_RED_GREEN_AND_AB_LANES.md`
> **原则**：不做黑名单、不做次数上限；用"习惯化 + 印象"这种**会自然消退、对新信息敏感**的机制。
> **交付纪律**：A 线实现与验证 → `scripts/promote.sh` 准出 → B 线只接受 cherry-pick。

---

## 一、 问题与证据（2026-10-30 生产数据）

| 现象 | 数据 |
|---|---|
| 两个机器人长时间对聊 | 菲菲（QQ 10009009）当日 223 条消息，触发她 **58 个回合** |
| 存在爆发串 | ≤120 秒内的连续触发串最长 **8 连** |
| 回复率无衰减 | 13 点 24% / 16 点 23% / 17 点 32% / 18 点 28% → 没有"越聊越腻" |
| 手写事实无效 | 事实写成 `菲菲(QQ:3993173948)`，而 3993173948 是**汐**；且语义事实**根本不参与门控**（`perceptual_gate` 无 facts 引用） |

**结论**：现有防线（余音共鸣上限、二人转 DND、冷暴力）都作用在"非点名"路径上；**点名/@ 路径无条件唤醒**，而对手是机器人时该路径被无限使用。

---

## 二、 设计原则

1. **不拉名单**：谁是机器人由她自己的语义记忆形成"印象" `b(sender) ∈ [0,1]`，可被新证据修正；
2. **不设次数上限**：用"习惯化"连续下降，**地板 > 0**，永远保留偶尔回应的可能；
3. **会恢复**：时间冲淡 + 新话题/真人插话去习惯化；
4. **像人**：不想接时能说出收尾语，而不是静默丢弃；
5. **叠加取宽松**：与冷暴力同时触发时取"更愿意说话"的一个（`max`），不叠乘。

---

## 三、 数学模型

### 3.1 状态

$$h_{c,u}\in[0,1)\quad\text{(对会话 }c\text{ 中成员 }u\text{ 的习惯化)}$$
$$b_u\in[0,1]\quad\text{(她对该成员"像机器人"的印象，来自语义记忆)}$$

### 3.2 更新

$$h \leftarrow h\cdot e^{-\Delta t/\tau}\qquad\text{(自发恢复)}$$
$$h \leftarrow \min(0.999,\; h+\alpha(1-h))\qquad\text{(仅当它真的回应了该成员)}$$
$$h_{\text{eff}} = h\cdot(1-\gamma\cdot\text{novelty})\qquad\text{(去习惯化：新信息抵扣)}$$

### 3.3 意愿（软性，不阻断）

$$p = \text{floor}+(1-\text{floor})\,(1-h_{\text{eff}}\cdot b)$$

- $b=0 \Rightarrow p=1$（真人零影响）；
- $p\ge\text{floor}$（永不关门）；
- 与冷暴力叠加：$p_{\text{final}}=\max(p,\;p_{\text{cold}})$。

### 3.4 参数与依据

| 参数 | 建议值 | 含义 | 依据 | 标签 |
|---|---|---|---|---|
| $\tau$ | 1800 s | 恢复时间常数 | 数据锚点：串内间隔中位 8 s、跨串中位 280 s、>20 min 仅 2% → 同串不恢复、隔时段恢复 | `convention:s31-recovery` |
| $\alpha$ | 0.40 | 每次回应加深速度 | 由目标反推：把最长 8 连击截到 ≤4（α=0.4 时 h(4)=0.87，p≈0.20） | `fit:s31-burst-cap` |
| floor | 0.08 | 意愿地板 | 由目标反推：日回合 58 → ≤15~20（223×0.08≈18） | `fit:s31-daily-turns` |
| $\gamma$ | 0.5 | 新话题折扣 | 设计约定（信息觅食：收益下降才离开） | `fit:pending` |
| $b$ 上限 | 1.0 | 印象强度 | 需多证据才逼近 1（误判敏感度见 §8） | `fit:pending` |

> **诚实声明**：$\tau,\alpha,\text{floor}$ 的**数值不是文献值**，是"形式有文献 + 数值由目标反推"；
> 三者均标 `fit:pending`，需 shadow 模式的反事实数据校准。

### 3.5 拟合协议（替代拍脑门）

1. 先用当日数据 MLE 拟合，记录结果：最佳拟合落在边界（τ=7200、α=0.8、floor=0.20），
   说明**当日数据更像恒定 23% 回复率**，无法识别习惯化 → 参数只能由目标反推；
2. **Shadow 模式**：只计算不生效，记录每条消息的 `(h, b, p, 实际是否回应)`；
3. 用 shadow 日志做反事实 MLE，替换本表数值并更新标签为 `fit:<report>`。

---

## 四、 架构设计

### 4.1 新增

```text
src/echomind/mind/social_satiation.py     # 纯函数：状态更新 / 意愿 / 去习惯化（≈70 行）
src/echomind/mind/bot_belief.py           # 从 semantic_facts 归纳 b(sender)，带缓存（≈50 行）
tests/unit/test_social_satiation.py
tests/unit/test_bot_belief.py
```

### 4.2 接入点（唯一）

`mind/perceptual_gate.py::evaluate()` 末尾：

```text
若 decision.tier >= 2（非真人直接点名）：
    p = social_satiation.willingness(chat, sender, now)
    以 p 对 score 做软折算；若未唤醒则记录"习惯化抑制"原因
tier == 1 且 sender 是真人：不介入
```

### 4.3 不改的东西

| 对象 | 状态 |
|---|---|
| DB 表结构 | 不改（习惯化状态进程内保存，见 §7 风险） |
| 端口 | 不新增（印象复用现有 `ISemanticFactReader`） |
| 人格 / 关系 / 探针 / 显著性特征 | 不改 |
| prompt 主体 | 仅追加 1 行"印象 + 习惯化"描述（≈30 token，走 `persona_render` 缓存键） |

---

## 五、 不变量与测试（先红后绿）

| 编号 | 不变量 | 测试 |
|---|---|---|
| S31-1 | $p\in[\text{floor},1]$ 恒成立 | 随机 1000 组 h,b 属性测试 |
| S31-2 | $b=0 \Rightarrow p=1$（真人零影响） | 所有真人消息 p==1 |
| S31-3 | 连续回应 n 次后 p 单调下降；间隔 ≥ τ 后恢复 ≥50% | 序列测试 |
| S31-4 | 与冷暴力叠加取 `max`，不叠乘 | 组合测试 |
| S31-5 | 相同输入 + 相同种子 ⇒ 相同决策（回放确定性） | 固定 seed 重放 |

**夹具**：`tests/fixtures/bot_pingpong.json`（机器人 A 连续 20 轮 @她，含 3 次新话题）。

**验收阈值**：

```text
机器人连击 20 轮 → 实际回应 ≤ 6 轮，且 ≥ 1 轮（证明不是黑名单）
同一时段真人消息 → 回应数变化 ≤ 5%
120 回合回放：wakes 漂移 ≤ 5%，double_apply 仍为 0
```

---

## 六、 分阶段实施

| 阶段 | 内容 | 验收 |
|---|---|---|
| **S31-0** | 本文档 + 不变量骨架（2 红）+ 夹具 + 基线快照 | 红证据留存 |
| **S31-1** | `social_satiation` 纯函数（状态/意愿/去习惯化），门控接入但默认关闭（flag） | S31-1/2/3 绿 |
| **S31-2** | `bot_belief` 从事实归纳 b（缓存 60 s），修正事实 ID 后验证识别正确 | 单测 + 真实事实 |
| **S31-3** | Shadow 模式：只记录不生效，跑 24h | 产出反事实清单 |
| **S31-4** | 用 shadow 数据 MLE 校准 α/τ/floor，更新标签 | 拟合报告 |
| **S31-5** | 灰度开启（单群）+ 24h 观察 | 58 → ≤20 回合；真人零影响 |
| **S31-6** | 收尾语注入 prompt（按 Schegloff & Sacks 的 pre-closing） | 人工抽检 20 条 |

**开关**：`AppConfig.social_satiation = off | shadow | on`，默认 `off`；灰度期只对指定群 `on`。

---

## 七、 风险与缓解

| 风险 | 量化 | 缓解 |
|---|---|---|
| 误判真人是机器人 | $b=0.3$ → 意愿 0.76（−24%）；$b=0.6$ → 0.53 | 要求多证据；$b$ 不轻易 >0.6；novelty 抵扣 |
| 重启丢状态 | 长循环可能在重启后复现 | 可接受（重启罕见）；S31-6 后再考虑持久化 |
| 与冷暴力叠乘过度沉默 | — | 取 `max`（已定） |
| 随机性导致回放不稳定 | — | 随机源注入 seed；回放固定 |
| 事实 ID 写错（已发生） | 3993173948=汐，10009009=菲菲 | 写入时做 ID/昵称一致性校验 |

---

## 八、 影响评估（基于当日真实数据）

| 指标 | 现状 | 预期（α=0.40, floor=0.08, b=1） |
|---|---|---|
| 菲菲相关回合/日 | 58 | ≈13–18（−70%~−78%） |
| 最长连续串 | 8 | ≤4 |
| 真人相关回合 | 不变 | 不变（$b=0$ 时 $p=1$） |
| 总消息量 | 392/日 | 约 −10% |
| 单消息延迟 | — | <0.05 ms（O(1)，无 DB） |
| prompt 体积 | — | +≈30 token（可缓存） |

---

## 九、 与现有机制的交互

| 机制 | 关系 |
|---|---|
| 余音共鸣（2 轮上限） | 叠加，互不冲突 |
| 二人转 DND（90 s） | 叠加 |
| 冷暴力（15 min） | **取宽松 `max`** |
| rivals（`is_rival`） | 不使用；印象独立演化 |
| 探针 `peer_dyadic` | 叠加 |
| 人格动力学（Stage 30） | 无交互 |

---

## 十、 参考文献

1. Rankin, C. H., et al. (2009). *Habituation revisited.* Neurobiology of Learning and Memory. [doi:10.1016/j.nlm.2008.09.012](https://doi.org/10.1016/j.nlm.2008.09.012)
2. Schegloff, E. A., & Sacks, H. (1973). *Opening up closings.* Semiotica. [doi:10.1515/semi.1973.8.4.289](https://doi.org/10.1515/semi.1973.8.4.289)
3. Pirolli, P., & Card, S. (1999). *Information foraging.* Psychological Review. [doi:10.1037/0033-295X.106.4.643](https://doi.org/10.1037/0033-295X.106.4.643)
4. Holtzman, A., et al. (2020). *The Curious Case of Neural Text Degeneration.* ICLR. [arXiv:1904.09751](https://arxiv.org/abs/1904.09751)
5. Cemri, M., et al. (2025). *Why Do Multi-Agent LLM Systems Fail?* [arXiv:2503.13657](https://arxiv.org/abs/2503.13657)
6. Rescorla, R. A., & Wagner, A. R. (1972). *A theory of Pavlovian conditioning.*（delta-rule 形式来源）

---

## 10.47 S31-3 影子评估结果（离线，真实历史）

工具：`scripts/satiation_shadow.py`（只读 DB，按"回合级"归因，不碰运行中的服务）。

| 指标 | 结果 |
|---|---|
| 识别出的机器人 | 仅菲菲 `10009009`（0.95） |
| 菲菲触发回合（当日） | 58 |
| **概率化抑制的期望回应** | **22.4 / 58**（−61%） |
| 阈值式抑制（p<0.5 才回） | 46 / 58 被抑制（更狠、也更不像人） |
| 前 10 个回合的意愿 | 1.00 → 0.66 → 0.53 → 0.42 → 0.32 → 0.26 →（长间隔恢复）0.68 → 0.57 → 0.41 → 0.33 |

**结论**：应当采用**概率化**抑制（按 p 采样），而不是"p<0.5 就闭嘴"；
前者保留"偶尔还会接一句"，且预期落在 18~26 的目标区间内。

## 10.45 S31-2 已落地（印象抽取）

- `bot_belief.py`：从 `semantic_facts` 抽取"某 id 是机器人"的**身份断言**（窗口 ±30 字 + `是/为/属于` + 机器人关键词）；
- 精度守卫：`自组织图式` 聚合摘要不作证据；`搭建/做/写/教程/部署` 判为"造机器人"而非"是机器人"；
- 生产库实测：`{'10009009': 0.95}`（仅菲菲，无误判）；
- 新增 7 条测试（含"阿斋搭建机器人≠阿斋是机器人"）；
- 开关：`ECHOMIND_SATIATION=off|shadow|on`，**默认 off**（S31-2 合入后线上行为不变）；
- 回放（120 回合）：`wakes 2 / probe_calls 67` 不变（快照事实里没有该断言）。

## 10.4 S31-1 已落地（纯函数 + 惰性接线）

- 新增 `mind/social_satiation.py`：`willingness`、`combine_with_cold_shoulder`、
  `SatiationState`（衰减/加深/去习惯化）、`adjust_decision`；
- 新增 `mind/bot_belief.py` 作为 S31-2 的接缝：`apply_belief()` 默认返回 `0.0`，
  **因此当前门控行为完全不变**；
- 门控只在 `tier ≥ 2` 且 `bot_like > 0` 时调整，`p ≥ 0.5` 不干预；
- 5 条不变量由红转绿（162 passed）；
- 回放（120 回合）：`wakes 2 / probe_calls 67 / double_apply 0 / reward_spread 1.09`——与基线一致。

## 十·五、 S31-0 基线（已执行）

### 10.5.1 红灯证据（`reports/S31_RED_EVIDENCE.log`）

```text
pytest tests/unit/test_social_satiation.py --runxfail
E   ModuleNotFoundError: No module named 'echomind.mind.social_satiation'   ×5
5 failed, 1 passed
```

5 条不变量测试以 `xfail(strict=True)` 钉住目标；S31-1 实现后必须转绿。

### 10.5.2 夹具

`tests/fixtures/bot_pingpong.json`：机器人 A 连续 20 轮，第 5/12/18 轮为新话题（用于验证去习惯化）。

### 10.5.3 行为基线（120 回合回放）

| 指标 | 基线 |
|---|---|
| turns | 120 |
| wakes | 2 |
| cooldown_blocks | 37 |
| probe_calls | 67 |
| double_apply | 0 |
| reward_spread | 1.09 |

### 10.5.4 生产侧基线（2026-10-30 当日）

| 指标 | 值 |
|---|---|
| 菲菲消息 | 223 条 |
| 触发回合 | 58 个（触发率 23%） |
| 最长连续串（≤120s） | 8 连 |
| 小时触发率 | 24% / 23% / 32% / 28%（无衰减） |

## 十一、 决策记录（已确认）

| 问题 | 决定 |
|---|---|
| 灰度范围 | **全群 shadow**（不是单群） |
| 收尾语 | **允许她主动说**（如"我先不接她的咕噜了"） |
| 与冷暴力叠加 | **取宽松 `max`** |

## 十二、 待确认（剩余）

1. 灰度范围：只对该群，还是所有群先 shadow？
2. S31-3 shadow 时长：24h 还是 48h？
3. 收尾语是否允许她**主动说出**"我先不接她的咕噜了"（会暴露机制）？
