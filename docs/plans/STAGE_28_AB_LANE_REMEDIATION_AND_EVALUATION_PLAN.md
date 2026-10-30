# Stage 28 A/B 双线与红绿测试驱动的修复建模、评估与准出规范
**（Stage 28 A/B Lane Remediation, Red-Green Delivery & Post-Fix Evaluation — Status: 📋 建模完成，待施工）**

---

## 一、 建模分析（Fault Impact Model）

本节把上一轮审计的 **F1 ~ F12** 折算成可计算量，作为修复目标的数学基线。

### 1.1 认知闭环的信号流模型

$$\underbrace{\mathbf{c}_t}_{\text{6D 和弦}} \xrightarrow{\;R(\mathbf{c}_t)\;}\ \underbrace{r_t \in [-0.85, +0.85]}_{\text{social\_reward}} \xrightarrow{\;\Delta A,\ \Delta T\;}\ \underbrace{(A_u, T_u)}_{\text{关系账本}} \xrightarrow{\;\Delta\theta\;}\ \underbrace{\boldsymbol{\theta}_{7D}}_{\text{人格}}$$

其中 Stage 26 起（代码现状）：
$$R(\mathbf{c}_t)=\text{clamp}\big(0.24\\,j+0.08\\,s-0.24\\,h-0.28\\,a-0.35\cdot\text{spoof},\ -0.85,\ +0.85\big)\times(1.12\ \text{if owner})$$

**断裂点**：`live_client` 调用 `compute_turn_social_reward(text, ...)` 时 $\mathbf{c}_t=\varnothing$，函数实现为 `_ = text`，于是

$$r_t \equiv 0.08\ (\text{非主人}),\quad r_t \equiv 0.12\ (\text{主人})$$

### 1.2 断裂后的关系动力学退化

好感度增量（`compute_affinity_delta`）在 $r_t=0.08$ 时：

$$r_t<0.35 \Rightarrow \Delta A = \text{step}\cdot\frac{85-A}{85},\quad \text{step}=\begin{cases}1.10 & \text{direct}\\0.55 & \text{ambient}\end{cases}$$

- **负向分支不可达**：`conflict / spoof / bot_pushback / reward<0` 四条扣分路径全部失效 → $A_u$ **单调不减**；
- **信任度单增**：$\Delta T = +0.005$ 恒定 → $T_u$ 单调趋近 0.98；
- **人格冻结**：`_reward_personality_deltas` 阈值 $\pm0.3$ → 永不触发；
- **禁忌词条不诞生**：`derive_emergent_trait` 需 $r_t\le-0.45$。

**线上实测印证**：`红帽` 仅 12 条消息 → $T=0.875$（$0.815+12\times0.005$）；`阿斋` 76 条 → 0.833；`橡皮` 269 条 → 0.82，好感 45.41 长期贴天花板。

### 1.3 探针成本模型

设 2 秒防抖窗口内群消息数为 $n$，当前实现探针调用数：
$$N_{\text{probe}} = n \quad(\text{逐条、防抖前})$$
目标实现：
$$N_{\text{probe}} = \begin{cases}1 & n\ge 1\\0 & \text{协议硬红灯}\end{cases}$$
单次探针实测 ≈ 1.8 s / ≈ 900 in-token / ≈ 100 out-token。$n=4$ 的刷屏窗口下，成本降幅 $\approx 75\%$。

### 1.4 情绪双计与冷却绕过的量化

唤醒型外围回合中，$\Delta V,\ \Delta J,\ \Delta I$ 被同一 $\mathbf{c}_t$ 计入两次 → 实际约为设计值的 **2.0×**；同时 `in_ambient_cooldown` 恒为 `False`，使 Stage 21/23 的 75 s 冷却对「探针存活的消息」完全失效（实测连续 3 条外围消息全部返回 chord 决策 0.38）。

---

## 二、 修复后评估报告（Post-Fix Evaluation, 目标值与判据）

> 本表在 A 线跑完后逐行回填「实测」，未回填前状态为 `📋 待测`。

| 指标 | 基线实测 | 修复目标 | 判据 | 测量手段 |
|---|---|---|---|---|
| $r_t$（辱骂和弦 `ann=3`） | `0.08` | $\le -0.50$ | 硬断言 | 单测 `test_rg_f1_*` |
| $r_t$（真诚夸奖 `joy=3`） | `0.08` | $\ge +0.50$ | 硬断言 | 单测 `test_rg_f1_*` |
| 生产链路 $r_t$ 离散度（20 回合回放） | 恒 0.08（极差 0） | 极差 $\ge 0.60$ | 硬断言 | 回放报告 `reward_spread` |
| tier-1 回合拥有和弦 | 0% | 100% | 硬断言 | 单测 `test_rg_f2_*` |
| 每 2 s 突发探针调用数（n=4） | 4 | $\le 1$ | 硬断言 | 计数器 `test_rg_f3_*` |
| 唤醒回合情绪应用次数 | **2（实测 200 回合双计 8/8）** | 1（实测 0/8） | 硬断言 | `Spy` 计数 `test_rg_f4_*` |
| 冷却期内唤醒（$w_{care}<0.95$） | 是 | 0 次 | 硬断言 | `test_rg_f5_*` |
| `_chord_cache` 条目上限 | 无界 | $\le 256$ | 硬断言 | `test_rg_f6_*` |
| 死配置字段 | 3 个 | 0 个（接入或删除） | 硬断言 | `test_rg_f7_*` |
| 视觉网关注入类型 | `Any` + `getattr` | Protocol | mypy 硬约束 | `test_rg_f8_*` |
| 探针上下文跨群污染 | 有 | 0 | 硬断言 | `test_rg_f9_*` |
| taboo 厌恶可达性 | 不可达 | 可达 | 硬断言 | `test_rg_f10_*` |
| 回放：挑衅型群友 20 回合净好感 | $\ge +8$（错） | $\le -3$ | 硬断言 | 回放报告 |
| 7 道门禁 | 绿 | 绿 | 全 Exit 0 | `qa_gate.sh` |


### 2.1 A 线回放基线（200 回合真实群聊，A 线已实测）

```bash
uv run python scripts/replay_eval.py --db data/replay-snapshot.db \
  --chat-key <群> --owner <主人> --turns 200 --out reports/
```

| 指标 | 200 回合实测 | 判据 | 结论 |
|---|---|---|---|
| turns / wakes | 200 / 8 | — | 唤醒率 4%（外围插话克制） |
| `probe_calls` | 124（0.62/回合） | ≤ 1.2/回合 | ✅ 达标（F3 的目标是 ≤1/突发，仍待改） |
| `cooldown_blocks` | 39 | — | 门控冷却仍在生效 |
| `cache_peak` | 124 | ≤ 256 | ✅ F6 生效 |
| `double_apply`（F4 前） | **8**（= 全部唤醒回合） | 0 | ❌ 双计已复现 → F4 修复后 60 回合切片降为 **0** |
| `reward_samples` / `reward_spread` | 8 / **1.09** | 极差 ≥ 0.60 | ✅ F1 生效（改前极差恒 0） |
| `partial` | false | false | 零 LLM、无预算截断 |

> 说明：报告与快照库均被 `.gitignore` 排除（`reports/`、`data/*.db`），含真实群号者不入库。

**回放报告 JSON 契约**（`reports/replay_<ts>.json`）：
```json
{"turns": 20, "reward_spread": 1.21, "probe_calls": 9, "cache_peak": 20,
 "affinity": {"taunter": -4.2, "friend": 6.8}, "trust": {"taunter": 0.71, "friend": 0.84},
 "wakes": 6, "cooldown_blocks": 4, "double_apply": 0}
```

---

## 三、 A/B 双线架构（Lane Isolation）

```text
┌──────────────────────── B 线（生产） ────────────────────────┐
│ /home/polyisoprene/Documents/echo-mind   branch: main         │
│ service: :3310  db: data/echomind.db   探测/学习真实生效      │
└───────────────────────────▲──────────────────────────────────┘
                            │ 仅当 A 线全绿 + 回放达标 → 合入
┌───────────────────────────┴────────── A 线（修复+回放） ──────┐
│ /home/polyisoprene/Documents/echo-mind-a  branch: lane/a-st28 │
│ service: :3311（可选）                                        │
│ db: data/replay-snapshot.db（只读快照） + data/a-sandbox.db   │
│ 探针: ChordFixtureProbe（录制 JSON，确定性、零 Token）        │
│       --live-llm 需显式开关 + Token 预算上限                  │
│ 产出: reports/replay_<ts>.json + 红绿证据表                   │
└───────────────────────────────────────────────────────────────┘
```

- **隔离规则 AB-1**：A 线绝不写 `data/echomind.db`，回放只读快照 + 沙箱库；
- **隔离规则 AB-2**：A 线默认使用录制的 `ChordFixtureProbe`，保证回放可复现、零费用；
- **隔离规则 AB-3**：B 线在 A 线准出前不接受任何修复提交（含当前未提交改动）；
- **隔离规则 AB-4**：A→B 只允许「全绿提交」通过 `git cherry-pick`（或 fast-forward merge）进入 `main`；
- **隔离规则 AB-5**：合并后 B 线重启，24 h 观察指标（探针/回合、异常日志、信任度漂移方向）不达标即回滚到上一个 tag。

---

## 四、 红绿测试契约（Red-Green-Refactor，先红后绿）

**核心：任何行为改动必须先有一条“失败的测试”，且失败原因必须指向目标缺陷。**

### 4.1 红绿执行序列（每个 finding 一次）

1. **写红**：新增 `test_rg_f<N>_<slug>`，只断言目标行为；
2. **跑红并留证**：`uv run pytest -k test_rg_f<N> -q`，把失败输出（断言值）原样贴入本文档「红证据」表；
3. **改最小实现**：只改到该测试转绿，不做无关重构；
4. **跑绿**：该测试 + 定向回归（`pytest -k "stage2 or stage3 or stage4"`）；
5. **全门禁**：`./scripts/qa_gate.sh` 全 7 道 Exit 0；
6. **登记**：在 4.3 表补齐 `red / green / commit` 三列。

### 4.2 硬性规则（写入契约，见 `docs/CONTRACT_RED_GREEN_AND_AB_LANES.md`）

- **RGR-1 先红后绿**：没有红证据的提交一律拒收；
- **RGR-2 红得正确**：红色失败必须来自目标断言，不得靠语法错误/缺 import 制造红；
- **RGR-3 最小实现**：单次提交只服务一个 finding；
- **RGR-4 测试不可回改**：转绿后的契约测试不得为了通过而放宽，除非新开一条红；
- **RGR-5 命名**：`test_rg_f<N>_<slug>`；提交信息前缀 `rg(F<N>):`；
- **RGR-6 生产路径同构**：测试必须走生产同一条调用路径（禁止只测「显式传 chord」的旁路）；
- **RGR-7 回放确定性**：冻结时钟、固定随机种子、探针走录制夹具；
- **RGR-8 双证据**：红证据 + 绿证据（含门禁尾行）同时入档。

### 4.3 红绿证据表（施工时回填）

| Finding | 测试 ID | 红证据（失败断言） | 绿证据 | 提交 |
|---|---|---|---|---|
| F1 | `test_rg_f1_production_reward_not_constant` | `AssertionError: insult turn must lose trust, got 0.755`（`assert 0.755 < 0.75`） | `2 passed` → `74 passed / Cov 90.53% / 7 门禁全绿` | `e023da4` |
| F2 | `test_rg_f2_tier1_turn_gets_chord` | 📋 | 📋 | 📋 |
| F3 | `test_rg_f3_probe_once_per_batch` | 📋 | 📋 | 📋 |
| F4 | `test_rg_f4_chord_applied_once` | `AssertionError: chord must shift mood exactly once per turn, got 2 applications` | `78 passed / Cov 90.56% / 7 门禁全绿`；回放 `double_apply` 8 → 0（60 回合切片） | `720b671` |
| F5 | `test_rg_f5_cooldown_not_bypassed` | 📋 | 📋 | 📋 |
| F6 | `test_rg_f6_chord_cache_bounded` | `AssertionError: chord cache must be bounded, got 300`（`assert 300 <= 256`） | `75 passed / Cov 90.53% / 7 门禁全绿` | 见 `rg(F6)` 提交 |
| F7 | `test_rg_f7_no_dead_config_fields` | 📋 | 📋 | 📋 |
| F8 | `test_rg_f8_vision_port_typed` | 📋 | 📋 | 📋 |
| F9 | `test_rg_f9_recent_ctx_scoped` | 📋 | 📋 | 📋 |
| F10 | `test_rg_f10_taboo_aversion_reachable` | 📋 | 📋 | 📋 |

---

## 五、 施工顺序（批次与依赖）

| 批次 | 内容 | 依赖 | 说明 |
|---|---|---|---|
| **P0-A** | F1（生产 reward 由 chord 反推）+ F6（缓存有界） | 无 | 收益最大、改动面最小 |
| **P0-B** | F4（单次应用）+ F5（冷却传参） | P0-A | 共用 chord 运行时 |
| **P1** | F2（tier-1 补探针，1.2 s 超时） | P0-B | 注意回复延迟预算 |
| **P1** | F9（上下文按 chat_key 过滤） | 无 | 低风险 |
| **P2** | F3（探针下移防抖批次） | P0 | 需改 `live_client` 时序，单独 Stage 更稳 |
| **P2** | F7（死配置接入/删除）、F8（视觉端口化） | 无 | 契约类修复 |
| **P3** | F10、F12（拆文件降行数） | 无 | 机会式 |

> **F3 单独成 Stage 29** 的建议：它改变了「探针在事件入站链上的位置」，属于架构级时序调整，不适合塞进 P0。

---

## 六、 风险与回滚

| 风险 | 缓解 |
|---|---|
| F2 补探针拖慢主人回复 | 1.2 s 硬超时 + 失败即降级为「无 chord」；实测 p95 延迟入回放报告 |
| F1 改变奖励分布导致好感度整体下降 | A 线 20/200 回合回放前后对比，确认「挑衅型下降、友好型上升」方向正确 |
| F3 改造引入事件丢失 | 单独 Stage + 双跑对照（旧链路 shadow 统计） |
| 合并污染生产 | AB-3/AB-4 + 合前 tag `pre-stage28` |

---

## 七、 准出定义（Definition of Done）

1. F1~F10 全部有「红 → 绿」双证据；
2. A 线 7 道门禁全绿，覆盖率 ≥ 90%；
3. 回放报告所有判据达标（第二节表格全绿）；
4. B 线合并后 24 h 观察：探针/回合 ≤ 1.2，异常日志 0 新增，挑衅型群友信任度出现**下降**；
5. 本文档第二节「实测」列与第四节「红绿证据表」全部回填完毕。
