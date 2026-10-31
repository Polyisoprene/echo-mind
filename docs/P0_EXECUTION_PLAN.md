# P0 执行计划：关系归人（逐步）

> 目标：同一人在群聊/私聊共享一套信任与深度；温度不随房间变；俏皮保留场合差异。
> 方式：逐步执行，每步有测试与验收；直接上线，可回滚；不做影子。

---

## 步骤与状态

| 步骤 | 内容 | 状态 | 验收 |
|---|---|---|---|
| **P0.1** | 纯函数人级画像：`mind/person_level.py` + 单测 | ✅ 本轮 | 3 条测试通过 |
| **P0.2** | 读取层：按 `user_id` 取跨场合 bond + stats；facade 内构建 profiles（带缓存） | ⏳ | 群/私聊拿到同一 profile |
| **P0.3** | 立场接线：`apply_stance_for` 接受 profile；温柔/耐心用人级，俏皮用场合 | ⏳ | 同一人跨场合温柔/耐心差 ≤2 |
| **P0.4** | care 接线：`care_weight` 用人级好感/信任/深度；重标定 `AFFINITY_OFFSET/SPAN` | ⏳ | 你本人在私聊 care > 0 |
| **P0.5** | 一致性测试 + 41 条关系 dry-run 对照 | ⏳ | 旧/新逐条可解释 |
| **P0.6** | 部署（重启两实例）+ 观察 | ⏳ | 线上快照显示同一 profile |

---

## P0.1 已完成的内容

`src/echomind/mind/person_level.py`：

- `PersonProfile(person_id, trust, affinity, depth_raw, depth_percentile)`；
- `build_profiles(bonds, stats)`：按人合并，trust/affinity 按消息量加权，depth 由跨场合汇总统计计算后取**全局百分位**；
- `stance_from_profile(bond, profile)`：返回 `(warmth, patience, play)`——温柔/耐心来自人级，俏皮来自场合好感；
- `care_weight_from_profile(profile)`：用人级好感，绕开旧公式的 38 截断。

测试 `tests/unit/test_person_level.py`：

1. 同一人两个场合 → 同一 trust、同一温柔/耐心；俏皮按场合不同；
2. 组内排名归零的人 → 人级深度不为 0；
3. 跨场合统计正确相加。

**为什么用全局百分位而不是原始绝对深度**：
原始 `depth_from_stats` 在 452 饱和常数下会把大多数人压到 60–90，sigmoid 后差异变小；
全局百分位保留排序与区分度，同时让同一人跨场合可比。

---

## P0.2 具体做法（下一步）

新增读取方法（`adapters/storage/working_repo.py` 或新 `person_level_repo.py`）：

```python
async def list_bonds_for_person(person_id: str) -> tuple[SocialBondProfile, ...]
async def list_stats_for_person(person_id: str) -> tuple[BondDepthStats, ...]
```

facade 内：

- 对 `bonds_map` 里的每个 `user_id` 取跨场合 rows；
- `build_profiles` 生成 `profiles: dict[str, PersonProfile]`；
- 缓存 30–60 秒（关系变化慢），避免每帧查库。

验收：同一人在群/私聊的 `PersonProfile` 完全一致（trust、depth_percentile）。

---

## P0.3 具体做法

`persona_stance.py`：

```python
def stance_for_profile(
    bond: SocialBondProfile, profile: PersonProfile | None
) -> tuple[float, float, float]:
    return stance_from_profile(bond, profile)
```

`apply_stance_for(params, bonds_map, sender_id, profiles=None)`：
- 有 profile → 用 `stance_from_profile`；
- 无 profile → 保持旧 `stance_vector`（兼容测试/未接线路径）。

facade 两处调用（`_advance`、`_apply_shadow_and_save`）传入 profiles。

验收：
- 同一人跨场合 `warmth/patience` 完全相同；
- `play` 仍由 `bond_venues.affinity` 决定；
- 现有 stance 测试不破。

---

## P0.4 具体做法（含 bug 修复）

现状：`care_weight(affinity, trust, depth)` 的 `base = clamp((affinity-38)/70)`。
私聊好感 32.1 < 38 → care = 0。

改：

```python
def care_weight_from_profile(profile):
    return care_weight(profile.affinity, profile.trust, profile.depth_percentile)
```

并重标定 `AFFINITY_OFFSET/SPAN`：

1. 取现网 41 条好感分布；
2. 用 P5/P95 或分位重标（E1 式，记 n 与 CI）；
3. 旧值 38/70 保留为 `convention:legacy` 对照，不直接删。

验收：
- 你本人私聊 care > 0；
- 41 条关系 care 变化均值 ≤ +0.01，最大值可解释（归零修复）。

---

## P0.5 dry-run 对照

用 `scripts/person_level_impact.py` 扩一版 `--apply-plan`（只读输出）：

- 每条关系：旧 depth / 新 depth_percentile / 旧 stance / 新 stance / 旧 care / 新 care；
- 标出 `|Δwarmth| > 4` 的 3 人，逐条注明原因；
- 输出 JSON 到 `reports/p0_dry_run.json`。

上线前必须人工过一遍这 3 条。

---

## 已知风险

| 风险 | 处理 |
|---|---|
| 全局百分位改变“深度”语义 | 文档明确：stance 用百分位，展示用绝对深度 + 场合排名 |
| 人级深度仍受消息量影响 | 记录人级 P95=396 vs 饱和 452；下次重拟合 |
| 私聊 care=0 | P0.4 必须修 |
| 缓存导致关系更新延迟 | 30–60 秒；手动改关系后失效 |
| 旧测试依赖 `stance_vector` | 保留旧函数，新增 profile 路径 |

---

## 回滚

- 新增模块与 profile 路径都是**可选参数**：`profiles=None` 时行为与现在完全一致；
- 配置开关 `ECHOMIND_PERSON_LEVEL=off|on`（P0.3 加），关闭即回旧路径；
- 不改表结构，回滚无需迁移。
