# E1 参数分类报告

> 目标：把 32 条 `fit_pending` 从“有字段”推进到“有判断”。
> 结论：**0 删除 · 4 转约定 · 2 条可用现有数据解决 · 21 条进实验队列 · 5 条被样本量阻塞**。

---

## 一、判定规则

| 判据 | 去向 | 本轮数量 |
|---|---|---|
| 能引文献，且能给页码/公式/取值 | `src` | **0** |
| 由产品目标反解、或策略上限（无自由参数） | `convention` | **4** |
| 有现成数据可拟合（点估计 + CI） | `data` | **2** |
| 需要设计对照实验 | `experiment` | **21** |
| 无引用、无数据、且无人使用 | `delete` | **0** |

**为什么 `src` 是 0**：这不是偷懒，是事实。关系模型的权重（GAIN/BIAS/W_*）、人格温度（ATTACHMENT_BETA）、
门控阈值都没有可直接引用的数值。之前唯一的 `src` 标签（`W_RESP=1.4`）指向依恋模型 DOI，
但论文里没有 1.4 这个数，已在前一轮降级。**给一个 DOI 却给不出页码和公式，不算溯源。**

## 二、32 条总表

| 组 | 符号 | 现值 | 提议 | 状态 |
|---|---|---|---|---|
| E1-A 关系模型 | `AFFINITY_OFFSET` | 38.0 | experiment | ⏳ |
| E1-A 关系模型 | `AFFINITY_SPAN` | 70.0 | experiment | ⏳ |
| E1-A 关系模型 | `BETRAYAL_HALF_LIFE` | 3.0 | experiment | ⏳ |
| E1-A 关系模型 | `BIAS` | 2.6 | experiment | ⏳ |
| E1-A 关系模型 | `DEPTH_BONUS` | 0.35 | experiment | ⏳ |
| E1-A 关系模型 | `DIVERSITY_SATURATION` | 42.0 | experiment | ⏳ |
| E1-A 关系模型 | `FREQ_SATURATION` | 452.0 | experiment | ⏳ |
| E1-A 关系模型 | `GAIN` | 1.6 | experiment | ⏳ |
| E1-A 关系模型 | `IMPACT_SATURATION` | 45.0 | experiment | ⏳ |
| E1-A 关系模型 | `W_BETRAY` | 1.6 | experiment | ⏳ |
| E1-A 关系模型 | `W_RESP` | 1.4 | experiment | ⏳ |
| E1-B 校准 | `DEFAULT_TAU` | 0.35 | experiment | ⛔ 阻塞 |
| E1-B 校准 | `MIN_OBS_FOR_CALIBRATION` | 20 | experiment | ⛔ 阻塞 |
| E1-B 校准 | `SHRINK_TAU` | 2.0 | experiment | ⛔ 阻塞 |
| E1-B 校准 | `SLOPE_BOUNDS` | (0.5, 2.0) | experiment | ⛔ 阻塞 |
| E1-C 人格动力学 | `ATTACHMENT_BETA` | 6.0 | experiment | ⏳ |
| E1-C 人格动力学 | `DELTA_CLIP` | 2.0 | experiment | ⏳ |
| E1-C 人格动力学 | `HOMEOSTATIC_PULL_RATE` | 0.02 | experiment | ⏳ |
| E1-C 人格动力学 | `STANCE_MAX_POINTS` | 8.0 | experiment | ⏳ |
| E1-C 人格动力学 | `STATE_HALF_LIFE_MIN` | 45.0 | experiment | ⏳ |
| E1-C 人格动力学 | `STATE_MAX_ABS` | 10.0 | experiment | ⏳ |
| E1-C 人格动力学 | `STATE_MAX_STEP` | 4.0 | experiment | ⏳ |
| E1-D 门控与召回 | `CLEAR_THRESHOLD` | 0.55 | experiment | ⏳ |
| E1-D 门控与召回 | `FUZZY_THRESHOLD` | 0.22 | experiment | ⏳ |
| E1-D 门控与召回 | `STRONG_SIGNAL_SCORE` | 0.55 | experiment | ⏳ |
| E1-E 情敌均衡 | `RIVAL_EQUILIBRIUM` | 45.0 | experiment | ⛔ 阻塞 |
| E1-F 关系等级 | `AFFINITY_THRESHOLDS` | (50.0, 100.0, 200. | data | ⏳ |
| E1-G 社交饱和 | `TAU_S` | 1800.0 | data | ⏳ |

## 三、4 条已转 `convention`

| 符号 | 现值 | 理由 |
|---|---|---|
| `DEPTH_CEILING` | 0.97 | 策略上限：w_care 封顶 0.97，避免单点关系无限接近 1；无自由参数 |
| `ALPHA` | 0.4 | 由产品目标「8 次往返后意愿 ≤0.4」反解，公式在模块注释中；属约定不是拟合 |
| `FLOOR` | 0.08 | 由产品目标「日回合 ≤18」反解，公式在模块注释中；属约定不是拟合 |
| `DUNBAR_ACQUAINTANCE_CAP` | 85.0 | 产品策略：熟人区上限 85 分。Dunbar 层数只提供“分层”概念，不提供 85 这个数 |

## 四、两个现在就能用数据解决的

### 4.1 `AFFINITY_THRESHOLDS`——与实测分布严重脱节

现网 `social_bonds`（n=41）的好感分布：

| 统计量 | 值 |
|---|---|
| min / p25 / p50 / p75 / p90 / max | 26.7 / 30.0 / 31.1 / 42.8 / 53.2 / 97.1 |

现阈值 `(50, 100, 200, 500)` 对应的实际效果：

| 等级 | 条件 | 实际人数 |
|---|---|---|
| Lv.1 | < 50 | **36/41（87.8%）** |
| Lv.2 | < 100 | 5/41（12.2%） |
| Lv.3–5 | ≥ 100 | **0（max 仅 97.1，永远不可达）** |

也就是说，**等级系统事实上是二值的，而且几乎所有人都停在 Lv.1**。
这不是“参数没拟合”，是**刻度和阈值不匹配**：分数分布在 27–97，阈值却按 0–500 设计。

处理选项（需要产品决定，我不替你选）：

1. **分位阈值**：用 p25/p50/p75/p90（30 / 31 / 43 / 53）重定义 Lv.1–5；
2. **重标定分数**：把 affinity 拉伸到 0–500，使旧阈值重新有意义；
3. **保留阈值但改展示**：UI 直接显示原始分，不显示等级。

推荐 1，因为它不需要改分数生成逻辑，只改分档，且能用现有 41 条样本给出初始分位（随数据增长再校准）。

### 4.2 `TAU_S`——用突发结构重估

现网 5,850 个消息间隔：p50=7s、p95=181s、p99=1,144s；当前恢复常数 1,800s。
注释声称 1,800s 来自突发结构，但**没有留下计算过程**。

行动：写 `scripts/fit_satiation_tau.py`，先识别突发（间隔 < 60s 连续段），再取**突发间间隔**的分布拟合恢复常数，
输出点估计与 95% CI，替换注释里的“据说”。

## 五、实验队列（5 组）

| 组 | 参数数 | 协议 | 前置 | 成本 |
|---|---|---|---|---|
| **E1-A 关系模型** | 11 | 回放历史消息，参数 ±20% 扰动，要求联系人深度排序 Spearman ρ ≥ 0.95 | 回放夹具 | 2–3 天 |
| **E1-B 校准** | 4 | LOGO 留一群交叉验证 | ⛔ 仅 2 个群 | 阻塞 |
| **E1-C 人格动力学** | 7 | `persona_sensitivity --repeats 3` 测可辨性与一致性；先 STATE 三参数，再 DELTA/STANCE/BETA/HOMEOSTATIC | 已有审计框架 | ~1 周（按需） |
| **E1-D 门控与召回** | 3 | 回放唤醒决策，与 200 条人工标注“该不该回”对齐，最大化 F1 | 需要标注 | 1 天标注 + 1 天拟合 |
| **E1-E 情敌均衡** | 1 | 用情敌样本拟合均衡点 | ⛔ 仅 2 个情敌 | 阻塞 |

## 六、被样本量阻塞的（这是本轮最重要的发现之一）

| 组 | 现有样本 | 需要 | 解锁方式 |
|---|---|---|---|
| E1-B 校准 | **2 个群** | ≥ 5 群才能留一验证 | 接入更多群，或构造合成群 |
| E1-E 情敌 | **2 个情敌** | ≥ 20 | 累积真实对手关系 |

在这两项解锁之前，任何“已校准”的说法都不成立；保留现值并标注 `blocked` 是唯一诚实的处理。

## 七、下一步

1. **立即**：`AFFINITY_THRESHOLDS` 的分档方案（产品决策）+ `TAU_S` 拟合脚本；
2. **短期**：E1-C 的 STATE 三参数（审计框架已就绪，`--repeats 3`）；
3. **中期**：E1-A 回放敏感性；
4. **待数据**：E1-B / E1-E。

---

*生成：E1 分类会话 · 2026-10-31*
