# Stance 校准数据审计（2026-11-01）

> 问题：能否用现有“90 组 pairwise 标签”标定 `STANCE_MAX_POINTS`？
> 结论：**不能。现有标签是模型 A/B，不是 stance 边界标签。**

## 1. 现有标签实际是什么

### 50 条绝对分

人工对单条回复评分：

- 人格一致性；
- 自然度；
- 边界感；
- 总体。

没有“同一人设、不同 stance 偏移”的对照。

### 90 组成对比较

`eval/calibration/persona_pairwise_v2/pairs.csv`：

```text
编号,场景编号,场面,回复A,回复B,
哪条更像真人(A/B/平局/都差),
哪条更适合发群(A/B/平局/都差),备注
```

回复 A/B 来自**不同模型**，不是“同一模型 + 不同 stance 强度”。

`persona-pairwise-v2-human-2026-10.json` 也是按模型聚合：

```text
more_human.models[kimi-k3/glm-5.3/...]
more_group.models[...]
```

所以它回答的是：

> 哪个模型更像真人 / 更适合发群

不是：

> 对熟人暖 4 分和暖 8 分，哪个是自然，哪个是漂移

## 2. 为什么不能拟合 STANCE_MAX_POINTS

`STANCE_MAX_POINTS` 要的是：

```text
同一场景、同一内容、同一模型
只改变 stance offset（0/4/8/12...）
标注“自然 / 过头 / 漂移”
```

现有标签没有控制变量：

- 模型不同；
- 回复内容不同；
- 没有 stance 强度；
- 没有“过头/漂移”标签。

把它们当 stance 标签，会把“模型差异”误学成“姿态幅度”，是典型局部补丁导致全局错误。

## 3. 结论

- `STANCE_MAX_POINTS` 保持 `fit_pending`；
- 不跑序数回归；
- 不引入新的手调 stance 参数；
- 没有新的 stance 对照数据前，不对外声称 stance 已校准。

## 4. 若将来要校准，需要什么

最小设计：

```text
同一 persona 快照
同一场景
同一回复内容骨架
stance ∈ {0, 4, 8, 12}
盲评：自然 / 略过 / 明显漂移
```

这不是现有 90 组标签能替代的；也不应让用户重新大量标注。

## 5. 对 Stage 42 的修正

- P2 的“用 90 组 pairwise 做 stance 序数回归”**取消**；
- 改为“数据不足，保留 pending”；
- 下一步转向不依赖 stance 标签的 dormant / ACT-R 研究。
