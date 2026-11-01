# 人格自演化：现在到哪一步

> 日期：2026-11-01（Stage 41 收口后）
> 一句话：**闭环已经真实跑通，但“自动长大”仍然受控、稀疏，主要靠人工 support 补最后一环。**
>
> 当前数字见 [CURRENT_STATE_2026-11-01.md](CURRENT_STATE_2026-11-01.md)。

## 1. 现在真在演化的部分

```text
真实回合
  → 快状态（±10，45min 半衰）
  → 日结算：慢基线（年预算 4，偏离≤12）
  + TraitEvidence（真实 quote + context）
  + trait 生命周期
  + 关系/记忆更新
```

- 慢基线：7 维，每天最多推一点，全年最多 4 点；
- 快状态：每轮变、会衰减；
- trait：真实 evidence 累计，Beta(1+s,1+c)；
- active：至少 2 个独立 context 且后验 >0.5；
- candidate/retired：不进入 prompt；
- shadow：每轮记录 active trait、允许工具、实际工具。

## 2. 真实闭环

```text
active trait
  → shadow
  → 新 evidence
  → context links
  → manual support
  → 词法门控 ranker
  → active-only prompt
```

已验证：

- 真实 image/voice 回合会写 evidence；
- 56 条 active 后 shadow 全部非空；
- 手动 support 能改变真实排序；
- 受控 replay 在临时库验证了 support/ranker 全路径。

## 3. 当前真实状态

```text
active_traits=2
legacy_traits=0
trait_evidence=16
support_links=6（4 个不同 memory）
context_links=52
shadow_active=56
```

## 4. 已完成 vs 未完成

### 已完成

- 证据账本；
- Beta + 独立 context 生命周期；
- active-only；
- trait→memory ranker；
- action eligibility：工具额外授权 + taboo 拒绝许可；
- 手动 support 向导 + 审计；
- G1 结构评审自动晋升器（默认 dry-run）；
- G2 只读叙事投影；
- 30/90 天 replay 基线。

### 未完成

- 自动 support 仍稀有，6 条 support 全部手动；
- dormant 策略未实现；
- support 仍是 presence-only，没有强度校准；
- 自动 candidate→active 没有真实 candidate 流；
- 叙事接 prompt 被 A/B 否决；
- 外部长期评测未做。

## 5. 当前判断

这不是“开放式自演化”，准确说是：

> **证据驱动的受控自演化。**

它会：

- 从真实行为累计 evidence；
- 让 active trait 进 prompt / memory / action permission；
- 用 support 影响检索；
- 通过 shadow 可审计。

它不会：

- 自己改代码/改 prompt 结构；
- 自己生成价值观；
- 无限制地改 7 维；
- 自动把低证据候选写进人格。

## 6. 最关键的限制

1. 只有 2 条 active，成长样本很少；
2. support 主要靠人工，自动同回合 explicit fact 很稀有；
3. 词法门控不是语义门控；
4. 长期漂移/外部有效性还没有证据。

**结论：自演化闭环已经成立，但还只是“小规模、可审计、受控”的闭环。**
