# Live 更新检测模型（2026-11-01）

> 背景：GroupMemBench change-only 在 KU 上 0.688–0.833，但 live 没有 `decision_type=changed`。
> 目标：检查 live 是否已有等价“同主题更新”信号。

## 1. 数据事实

`claims` 表有：

```text
status          asserted / superseded / retracted
superseded_by
valid_from_ms / valid_to_ms
subject / predicate / value
```

但当前生产：

```text
superseded = 0
retracted  = 0
```

同时存在 8 组同一 `subject+predicate` 的多条 `asserted`：

```text
最近B站冲浪: ...       8 条 asserted
不要象挑战...            7 条
冰色-瑟瑟馍馍...         6 条
...
```

说明：

- 读侧 `claim_views` 只读 `status='asserted'`；
- 但写入侧没有把旧 claim 标成 superseded/retracted；
- 所以“同主题更新”在 live 里没有真正闭合；
- `semantic_facts.revision_count` 也只是计数，没有 supersede 关系。

## 2. 为什么不能直接迁移 change-only

GroupMemBench 的 changed 是**显式标注**：

```text
decision_type=changed
decision_change_metadata
```

live 没有等价字段；如果按 `subject+predicate` 最新一条硬选，会：

- 把多条同时成立的事实误杀；
- 把不同 predicate 的价值混在一起；
- 破坏现有 claims 读路径。

## 3. 正确的下一步（先建模，不写）

写入侧：

```text
新 claim 与已有 asserted 同 subject/predicate
  → 旧 claim status=superseded
  → old.valid_to_ms = new.valid_from_ms
  → old.superseded_by = new.id
```

但必须先确认：

- 哪些 predicate 是函数型（value）可覆盖；
- mentioned 等非函数型不能覆盖；
- 同一 subject 多值是否合法；
- 隐私/audience 是否一致；
- 回滚与审计。

读侧：

- 只读 asserted；
- superseded 保留历史，不进当前事实；
- 与 `valid_to_ms` 过滤一致。

## 4. 验收

- 先 shadow：只记录“将要 supersede 的旧 claim”，不写；
- 人工/规则核对 8 组多 asserted；
- 再小范围写入；
- 70/70 与 500 QA 不退化；
- 不通过就保留现状。

## 5. 结论

> live 目前没有可靠的更新检测语义；“同 subject/predicate 多条 asserted”是数据缺陷，不是可直接利用的信号。

在写入侧 supersede 模型通过验证前，change-only 只能作为 GroupMemBench 适配，不能迁移到 live。
