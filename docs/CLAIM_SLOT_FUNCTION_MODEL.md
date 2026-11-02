# Claims slot 功能模型（2026-11-02）

> 目标：先实现功能，数据精调后置。
> CharacterEval 暂缓，不阻塞本轮。

## 1. 单值槽（人物特征）

只有“人物特征”类槽位是单值：

```text
person.nickname        群昵称/外号
person.gender          性别
person.birthday        生日
person.age             年龄
person.owner           主人/归属
person.city            常住城市
person.job             职业
person.species         物种
person.relationship    恋爱/关系状态
```

多值（永不自动覆盖）：

```text
mentioned
preference.*
habit.*
skill.*
experience.*
event.*
```

## 2. slot_key

格式：

```text
person.nickname
person.gender
...
```

subject 仍表示“谁”，slot_key 表示“哪个属性槽”。  
没有 slot_key 的 claim 不参与覆盖。

## 3. 推断

`infer_slot(subject, value)` 使用显式、可审计的中文/英文 pattern，只识别上面的单值人物特征；命中恰好一个槽才返回，否则返回空。

不做：

- 不按 subject 人名猜；
- 不把 B站视频/格斗技巧/经历当单值；
- 不覆盖 `mentioned`；
- 不从 value 猜“喜欢吃什么”。

## 4. 写入流程

```text
mirror_fact / assert_claim
  → infer_slot（若未显式给 slot_key）
  → claims.slot_key
  → 若 CLAIM_SLOT_SUPERSEDE=on 且 slot 是单值：
       旧 asserted 同 chat+subject+slot+audience/scope/owner/sensitivity
       → superseded + valid_to + superseded_by
```

默认：

```text
CLAIM_SLOT_INFER=on      只写 slot_key，不覆盖
CLAIM_SLOT_SUPERSEDE=off 默认不 supersede
```

## 5. 调试/数据精调方法

1. `scripts/backfill_claim_slots.py`：扫描 222 条 claims，dry-run 统计每个 slot 命中；
2. 检查误判：打印 `claim_id / value / inferred_slot`；
3. 只对确认的单值槽开 `CLAIM_SLOT_SUPERSEDE=on`；
4. 用临时库验证 superseded/valid_to；
5. 70/70 + 500 QA 回归；
6. 不通过回滚 flag。

## 6. 验收

- 单值/多值表明确；
- 未命中 slot 的 claim 永不覆盖；
- mentioned 永不覆盖；
- 默认 supersede off；
- 测试覆盖：nickname/gender 单值、preference/mentioned 不覆盖、audience 不同不覆盖；
- 文档含精调步骤。

## 7. 边界

- pattern 是工程规则，不是语义理解；
- 数据精调阶段会误判/漏判，需 dry-run；
- 不宣称 open-domain slot extraction；
- 不接 CharacterEval。

## 8. 实现状态（2026-11-02）

已实现：

```text
mind/claim_slots.py             显式 pattern + 单值槽集合
claims.slot_key                 已迁移，默认空
claim_repo.assert_claim         slot_key 参数；单值槽可 supersede
scripts/backfill_claim_slots.py 历史回填 dry-run
```

安全默认：

```text
CLAIM_SLOT_INFER=off      不自动推断
CLAIM_SLOT_SUPERSEDE=off  不自动覆盖
```

测试覆盖：

- nickname 单值；
- preference/experience/mentioned 不建槽；
- 一个 value 命中多个槽 → 空；
- 同 audience 的 nickname 新旧可 supersede；
- 回填 `--apply` 需 `CLAIM_SLOT_CONFIRM=yes`。

## 9. dry-run 数据审计（2026-11-02）

```text
scanned = 222
matched = 20
person.nickname 13
person.owner 4
person.city 1
person.gender 2
```

已发现误判：

- `自组织图式:外号` 被当成 `person.nickname`；
- `本群真实群主` 被当成 nickname；
- `回音的主人` 被当成 person.owner；
- `住在主人电脑里` 被当成 person.city。

因此：

- **未 apply**；
- 推断默认 off；
- 当前 pattern 只作为初始版本；
- 需要精调 subject 过滤/pattern，或人工确认后再回填；
- 生产 claims.slot_key 仍全空。

## 10. 精调/调试方法

1. 先跑 dry-run：

```bash
python scripts/backfill_claim_slots.py --out reports/claim_slots_dry.json
```

2. 逐条检查 `subject/value/slot_key`，标记 false positive；
3. 先修 `infer_slot` 的 subject 过滤和 pattern；
4. 再跑 dry-run，直到误判可接受；
5. 临时库 apply，验证 claims 读路径；
6. 生产小流量 apply 需要：

```bash
CLAIM_SLOT_CONFIRM=yes
CLAIM_SLOT_INFER=on
CLAIM_SLOT_SUPERSEDE=on
```

7. 70/70 + 500 QA 回归；
8. 不通过就关闭 flag。

## 11. 边界

- 这是**功能先实现、数据后精调**的状态；
- 单值槽仅人物特征；
- 多值/事件/偏好不覆盖；
- 生产未启用推断/supersede；
- 不接 CharacterEval。
