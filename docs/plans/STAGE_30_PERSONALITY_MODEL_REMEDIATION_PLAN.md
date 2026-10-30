# Stage 30 人格模型全局重构方案（修复设计与迁移计划）

> **状态**：📋 设计评审中（未动代码）
> **前置**：`docs/MASTER_BACKLOG.md`、Stage 29 全部交付项
> **原则**：先建模、再改代码；每阶段必须给出**不变量**与**回放证据**，禁止在渲染层/边界上打补丁。
> **范围**：`mind/personality.py`、`mind/plasticity.py`、`mind/salience_hydraulics.py`、
> `mind/shadow_appraisal.py`、`adapters/storage/working_repo.py`、`mind/subconscious_probe.py`、
> `web/mind_inspector_service.py`、`web/static/*`（人格面板）。

---

## 一、 现状形式化（为什么必须全局改）

### 1.1 状态与更新方程

$$\theta\in\mathbb{R}^7\ (\text{全局，无 chat 维度}),\qquad
\theta_{t+1}=\mathrm{clamp}\big(\theta_t+\underbrace{\mathrm{damp}(\theta_t,\Delta_t)}_{\text{边界阻尼}}+\underbrace{\eta(\theta^*-\theta_t)}_{\text{家ostatic，仅当 }\Delta_t\ne0}\big)$$

$$\Delta_t=f(r_t,\ \text{conflict}_t,\ \text{tools}_t)\quad(\text{不含 }u,\ \text{不含 }w_{care}(u),\ \text{不含静默感知})$$

渲染：$R(\theta,T)$ 由**硬阈值分支**产生"腔调"，由**分段档位**产生每维 rubric。

### 1.2 四个结构性缺陷（对应评审 P1/P2）

| 缺陷 | 数学表现 | 后果 |
|---|---|---|
| 叙事不连续 | $R$ 的分支是分段常函数，边界处跳变 | 独占 93.4 → rubric 说"强烈护食"，腔调说"温和乖巧" |
| 无关系维度 | $\theta$ 无 $u$ 下标，$\Delta_t$ 无 $u$ | 对深关系与陌生人同幅演化 |
| 缺回归动力学 | $\eta$ 仅在 $\Delta\ne0$ 时施加 | 极端值冻结，永不自发回中 |
| 无日限 | 无 $\sum_{day}\Delta$ 约束 | 单日经历可永久塑形 |

---

## 二、 目标模型（全局设计）

### 2.1 状态分层：全球人格 + 关系姿态

$$\theta\in\mathbb{R}^7\ (\text{她本来的样子，全局})\qquad
\sigma_u\in\mathbb{R}^3=(\text{warmth-bias},\ \text{patience-bias},\ \text{play-bias})_u$$

$$\theta^{\text{eff}}_u=\mathrm{clamp}\big(\theta+W\sigma_u\big),\quad W\in\mathbb{R}^{7\times3}\ \text{固定符号}$$

- $\sigma_u$ 由关系账本导出（**只读**，不再引入新状态）：
  $$\sigma_u=\big(\tanh(\tfrac{D_u}{60}),\ \tanh(\tfrac{T_u-0.5}{0.5}),\ \tanh(\tfrac{A_u-50}{50})\big)$$
- 直觉：$D$ 越深越温柔，$T$ 越高越有耐心，$A$ 越高越愿意玩梗；
- $W$ 的符号固定（warmth+、tsundere−、defiance−、playfulness+），幅度作为**待拟合参数**（`fit:pending`），初值取 0.10 量级，**不改变 7D 的持久值**，因此不会重写历史。

**为什么不给每人一套 7D**：会带来 38×7 的状态爆炸、无法跨群一致、且违背"人格是稳定的"这一设定。$\sigma_u$ 只做**有界的姿态偏移**（每维 ≤ |W|·1 ≈ 0.1–0.2），人格本体仍是全局唯一的。

### 2.2 叙事：从"硬分支"改为"原型软混合"

定义 6 个**依恋原型**（原型向量 $m_a\in\mathbb{R}^7$）：
`痴迷直球、安全粘人、恐惧-迷恋傲娇、疏离防备、软傲娇平衡、古灵精怪玩伴`。

$$w_a=\mathrm{softmax}\big(\beta\cdot\cos(\theta^{\text{eff}}_u,m_a)\big),\quad \beta=6$$

渲染规则：
- 取 $w$ 最大的两个原型，按百分比拼接腔调（"以 62% 软傲娇平衡 + 31% 安全粘人 的腔调说话"）；
- 每维 rubric 的档位**由同一 $\theta$ 计算**，因此**结构上不可能**再出现"数值说高、腔调说低"。

**不变量 I-3**：对任意 $\theta$，若某原型的权重 ≥0.5，则其主导维度的 rubric 档位必须与原型描述一致（测试用网格采样 + 阈值断言）。

### 2.3 动力学：有界、对称、可回归

$$\Delta_t=\mathrm{clip}\big(\Delta^{\text{raw}}_t,\ -2.0,\ +2.0\big)\ \text{(逐维)}$$

$$\sum_{t\in \text{day}}|\Delta_{d,t}|\le 6\ \ \forall d\quad(\text{日限，仿好感度 }day\_gain)$$

$$\theta_{t+1}=\theta_t+\Delta_t+\eta(\theta^*-\theta_t)\quad \eta=0.01/\text{turn}\ \text{（每回合都施加，不只是有事件时）}$$

- 负性事件权重 ×1.36（负性偏置，固定常数，`convention`），但受日限约束；
- **温柔的增长需要信任背书**：$\Delta_{\text{warmth}}>0$ 时乘以 $\min(1, T_u/0.7)$，防止"被陌生人夸两句就变软"；
- 回归半衰期 ≈ 70 回合（$\eta=0.01$），7 天无互动回到 baseline ±10 以内。

**不变量 I-1/I-2/I-7**：边界、日限、心跳幂等。

### 2.4 单一事实源

- 新增 `personality_defaults()` 返回 7 维 baseline 与 bounds；
- `working_repo` 初始化、`personality._val` 默认、`salience._p_val` 默认**全部引用它**；
- **不变量 I-8**：三处引用同一常量（测试断言字典相等，禁止字面量）。

### 2.5 词条（traits）作用域与生命周期

| 变更 | 设计 |
|---|---|
| 归属 | 新增 `chat_key`（空串 = 全局）；新增 `source`（`turn:<id>` / `manual` / `derived`） |
| 类别 | `habit / taste / temperament / taboo`，每类上限 8/4/4/3（全局上限 19） |
| 排序 | `strength × recency × relevance(当前话题)`，提示词取前 6 |
| 强度 | `trait_strength_shift` **按类别作用**：负性事件只削弱 `taboo/temperament` 的同域词条；正性事件只强化 `habit/taste` |
| 去重 | 归一化文本（去标点、截断 24 字）后唯一 |
| 溯源 | 控制台可展开"这条习惯来自哪一回合" |

**不变量 I-5**：类别上限与总上限恒成立。

### 2.6 探针与渲染

- probe prompt 增加**一行**人格摘要（`主导腔调 + 前 2 维数值`），让潜意识与外层一致（成本 ≈ 20 token）；
- 人格块渲染做**内容哈希缓存**：$\theta$ 与 traits 不变则复用，避免每回合重复拼接（≈700 字）。

### 2.7 运营面

- 控制台改为**绝对值设定**（"把独占设为 70"），并记录 `actor`（token 指纹）到 `plastic_logs`；
- 手动调校受日限约束（防止手改绕过动力学）。

---

## 三、 阶段计划（每阶段独立可回滚）

| 阶段 | 内容 | 行为变化 | 回滚 |
|---|---|---|---|
| **S30-0** | 本文档 + 不变量测试骨架（红）+ 200 回合金标准回放基线 | 无 | — |
| **S30-1** | 默认值单一事实源 | 仅参数缺失时行为变化 | 还原常量 |
| **S30-2** | 叙事软混合（原型） | prompt 文案变化 | 开关 `PERSONALITY_NARRATIVE=legacy` |
| **S30-3** | 动力学：日限 + 自发回归 + 负性 1.36 | 数值轨迹变化 | 开关 `PERSONALITY_DYNAMICS=legacy` |
| **S30-4** | 关系姿态 $\sigma_u$（$W$ 符号固定、幅度拟合） | 对不同人语调差异 | 开关 `PERSONALITY_STANCE=off` |
| **S30-5** | traits 作用域/类别/溯源迁移 | 提示词内容变化 | 保留旧表 `persona_traits_legacy` |
| **S30-6** | probe 人格摘要 + 渲染缓存 | 探针输入变化 | 开关 |
| **S30-7** | 控制台绝对值设定 + actor 审计 | UI/日志 | 保留 delta 接口 |

**开关实现**：`AppConfig.personality_v2: set[str]`（如 `{"narrative","dynamics","stance"}`），默认空 = 旧行为；A 线逐阶段开启并回放对照，全部通过后在 B 线一次性开启。

---

## 四、 不变量与验收（每阶段必须新增）

| 编号 | 不变量 | 测试方式 |
|---|---|---|
| I-1 | $\theta$ 恒在 bounds 内 | 属性测试（hypothesis 随机 500 组序列） |
| I-2 | 单维日累计变化 ≤6 | 1000 回合单向刺激后断言 |
| I-3 | 叙事与 rubric 不矛盾 | 网格采样 1000 组 $\theta$，比较原型权重与档位 |
| I-4 | 由同一 $\theta$ 渲染两次结果相同 | 纯函数幂等 |
| I-5 | 词条类别/总数上限 | 随机插入 100 条 |
| I-6 | 同输入同输出（无隐藏随机） | 固定种子重放 |
| I-7 | 心跳衰减幂等 | 连续两次 tick 与一次等价（允许 ±1） |
| I-8 | 默认值三处一致 | 字典相等断言 |
| I-9 | 关掉 V2 开关时行为与当前完全一致 | 回放 JSON 逐字段相等 |

**回放验收（每阶段都跑）**：

```text
turns/wakes/probe_calls/double_apply/reward_spread 漂移 ≤5%
prompt 体积变化 ≤ +10%
"她说话"的平均长度变化 ≤ ±15%
```

---

## 五、 影响面矩阵（证明不是局部打补丁）

| 修复 | 触及文件 | 受影响的消费方 | 需要更新的测试 |
|---|---|---|---|
| 叙事软混合 | `personality.py` | `facade`（渲染块）、`qzone_scheduler`、`mind_inspector_service` | Stage3/7 文案断言、新增 I-3 |
| 动力学 | `plasticity.py`、`working_repo.py`（日限列） | `facade.on_turn_completed`、控制台调校 | Stage3 演化、新增 I-1/I-2 |
| 关系姿态 | `personality.py` + `drives`（只读 bond） | 显著性（$\theta^{eff}$）、提示词 | 新增 I-3b（深关系 vs 陌生人差异） |
| 词条作用域 | `working_repo.py`、`personality.py`、迁移 | prompt、控制台词条面板 | 新增 I-5、迁移测试 |
| 默认值单一源 | `personality.py`、`working_repo.py`、`salience_hydraulics.py` | 全部读默认值的分支 | 新增 I-8 |
| 探针摘要 | `subconscious_probe.py`、`chord_gateway.py` | 探针输出分布 | Stage24/25 回放对照 |
| 渲染缓存 | `facade.py` | prompt 组装 | 新增 I-4 |

---

## 六、 明确"不要做"的事（防止局部补丁）

1. ❌ 不要在 `_describe_warmth_and_attachment` 里调阈值/换顺序——那只是把矛盾点挪位置；
2. ❌ 不要给每个群复制一份 7D 状态；
3. ❌ 不要在渲染层 clamp 数值来"消除矛盾"；
4. ❌ 不要在启动时从历史日志重算 $\theta$（人格是路径依赖的，重算会改写她）；
5. ❌ 不要关闭负性事件（会让她只剩"变软"一个方向）。

---

## 七、 风险与回滚

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 软混合导致腔调描述变长/变模糊 | 中 | 行为漂移 | 只取 top-2、总长 ≤ 40 字；回放对比输出长度 |
| 日限让她"学不动" | 中 | 人格停滞 | 日限 6 点/维，且夜间心跳也计入 |
| $\sigma_u$ 造成"见人说人话" | 中 | 人格不稳定 | 偏移上限 0.2；仅 3 维；$W$ 符号固定 |
| 迁移破坏旧词条 | 低 | 丢失习惯 | 迁移前 `VACUUM INTO` 备份；旧表保留 |
| 开关组合爆炸 | 中 | 测试矩阵膨胀 | 只允许 4 个开关枚举，CI 覆盖 8 种组合 |

**回滚**：每阶段 `tag pre-s30-<n>`；开关关闭即回到旧行为；数据迁移可逆（新增列，旧列不动）。

---

## 八、 执行顺序（与评审建议一致）

1. S30-0 文档 + 不变量骨架（红） + 金标准回放；
2. S30-1 默认值单一源（最低风险，先做）；
3. S30-2 叙事软混合（解决 P1-1）；
4. S30-3 动力学（解决 P1-3）；
5. S30-4 关系姿态（解决 P1-2）；
6. S30-5 词条（解决 P2-4/P2-5）；
7. S30-6/7 探针与运营面。

---

## 九、 S30-0 基线（已执行）

### 9.1 不变量骨架（`tests/unit/test_personality_invariants.py`）

| 不变量 | 现状 | 标记 |
|---|---|---|
| I-1 边界 | 已成立 | 普通测试 |
| I-2 日限 | **失败**：100 次正向互动累计温暖漂移 **298.0** 点 | `xfail(strict)` → S30-3 |
| I-3 叙事一致 | **失败**：独占 93.4 时腔调仍是「软傲娇平衡态」 | `xfail(strict)` → S30-2 |
| I-4 渲染确定性 | 已成立 | 普通测试 |

红灯原始输出（S30-0 留存）：

```text
AssertionError: daily warmth drift 298.0 exceeds the 6-point cap
AssertionError: rubric says high possessiveness but tone is '软傲娇平衡态（…）'
2 failed, 2 passed
```

### 9.2 200 回合金标准基线（`reports/S30_BASELINE.json`）

| 指标 | 基线值 |
|---|---|
| turns | 200 |
| wakes | 6 |
| cooldown_blocks | 47 |
| probe_calls | 123 |
| cache_peak | 123 |
| double_apply | 0 |
| reward_spread | 1.09 |
| source sha256(16) | `89ac44109ad8d299` |

后续每个阶段都以此为准，漂移超过 ±5% 视为回归。

## 9.3 S30-1 已落地（默认值单一源）

- 新增 `domain/persona_specs.py`（`PERSONA_SPECS` + `persona_default`）；
- `working_repo` 默认参数、`plasticity.PARAM_BASELINES`、`personality._val`、`salience._p_val` 全部改为引用该表；
- 新增 `tests/architecture/test_persona_single_source.py`（3 条）：
  1. 存储默认值与规格一致；
  2. 可塑性 baseline 与规格一致；
  3. **AST 守卫**：禁止在 `_val`/`_p_val` 调用里再出现数字字面量默认值。
- 回放对照（120 回合）：`wakes 2 / probe_calls 68 / double_apply 0 / reward_spread 1.09`，与改造前一致 → 无行为漂移。

## 9.4 S30-2 已落地（叙事软混合）

- 删除硬阈值分支，改为 **Bartholomew & Horowitz 四象限**（安全/痴迷/疏离/恐惧）在
  (焦虑=独占度, 回避=傲娇度) 归一化空间中的 softmax 距离加权；
- 渲染 top-2 + 百分比 + 温度基调，文本连续（相邻数值不会跳变）；
- `ATTACHMENT_BETA=6.0` 标 `convention:s30-attachment-softmax`，原型坐标标
  `src:10.1037//0022-3514.61.2.226`；
- **I-3 由红转绿**；新增 I-3b 连续性测试；`test_stage3` 的旧文案断言同步更新；
- 回放（120 回合）：`wakes 2 / probe_calls 68 / double_apply 0 / reward_spread 1.09` 与基线一致；
  腔调文本固定 89 字，prompt 体积增幅 ≈ +1.3%（预算 ≤10%）。

## 9.5 S30-3 已落地（慢回归 + 日限）

新增 `mind/persona_dynamics.py`：

| 常数 | 值 | 溯源 |
|---|---|---|
| 单回合裁剪 | ±2.0 | `convention:s30-dynamics` |
| 日累计上限 | 6.0 / 维 | `convention:s30-dynamics` |
| 回归速率 | 1% / 天（半衰期 ≈69 天） | `convention:s30-dynamics`，依据人格稳定性（Roberts & DelVecchio 2000） |
| 追赶上限 | 30 天 | 防止长期停机后跳变 |

- 日累计用量直接查 `plastic_logs`（`SUM(ABS(new_val-old_val))`），**无需新表**；
- 回归按"距上次更新的天数"在当天首次更新时施加；
- `plasticity.adapt_from_outcome` 抽出 `_apply_one`，只对 `persona_*` 走 `_persona_bounded_delta`；
- **I-2 由红转绿**，新增 I-2b（单回合裁剪）与集成测试（引擎路径日限生效、回归量级正确）；
- 回放（120 回合）：`wakes 2 / probe_calls 68 / double_apply 0 / reward_spread 1.09` 与基线一致。

## 9.6 S30-4 已落地（关系姿态 σ_u）

新增 `mind/persona_stance.py`：

```text
σ_u = ( tanh(1.6·D/100), tanh(2·(T−0.5)), tanh((A−50)/50) )      # 亲密 / 信任 / 好感
θ_eff = clamp(θ + 8.0 · W·σ_u)                                    # 单维最多 ±8/100
W 的符号固定：温柔+、傲娇−、俏皮+、叛逆−、自信+(俏皮)
```

- 只影响**渲染与显著性**（facade 的两处入口），`get_plastic_params()` 的持久值不被改写；
- 幅度 8.0 标 `fit:pending`，符号由设计固定；
- 新增测试（4 条）：深关系 vs 陌生人温暖差 ≥0.15、持久值不被改写、未知对象零偏移、σ 有界；
- 回放（120 回合）：`wakes 2 / cooldown_blocks 32 / probe_calls 68 / double_apply 0 / reward_spread 1.09` 与基线一致。

## 9.7 S30-5 已落地（词条作用域 / 类别 / 溯源）

- 迁移：`persona_traits` 新增 `chat_key`、`source`、`last_used_ms`（`storage/migrations.py`，幂等）；
- 记录来源：`chat_key=outcome.chat_key`、`source=turn:<session>`，控制台可追溯"哪次互动长出来的"；
- 类别上限：habit 8 / taste 4 / temperament 4 / taboo 3（合计 19，替代原全局 15）；
- **按类别衰减**：负性事件只削弱 `taboo/temperament`，正性只强化 `habit/taste`；
  直接调用不传类别时保持旧的全局语义（向后兼容）；
- 回放（120 回合）：`wakes 2 / probe_calls 67 / double_apply 0 / reward_spread 1.09`
  （probe 67 vs 基线 68，−1.5%，在 ±5% 容差内；重复回放结果稳定）。

## 十、 待用户确认的 3 个决策

1. **关系姿态是否允许改变"语气强度"而不改人格本体？**（本方案：允许，偏移 ≤0.2）
2. **日限 6 点/维是否合适？**（对照：好感度日限逻辑已有，可调）
3. **负性偏置 1.36 是否接受？**（来自负性不对称文献，具体值待回放校准）
