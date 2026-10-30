# Stage 27 详细工程设计、括号内心独白外泄根治与出站思考块隔离规范
**（Stage 27 Engineering Spec: Inner-Monologue Leakage Elimination & Outbound Reasoning Isolation — Status: ✅ 已验收通过）**

---

## 一、 事故现场取证（`data/echomind.db` · `turn_traces`）

实测抓到 `#4144`（`（这轮没点我，主人他们还在聊插件，我先不插嘴）`）被发进群聊的完整链路：

```text
Turn 1484f3443988 | 触发: "汐：叫我了？先说好 拿白饭来换"
  ├─ Step 1 [LLM 主脑]: 未调用任何发送工具，仅在 content 写下：
  │     "（这轮没点我，主人他们还在聊插件，我先不插嘴）"
  └─ Step 2 [send_message(rescue)]: 漏发挽救器把上述括号思考当成正文外发 ❌
```

随后 `Turn ee3225b96839` 触发消息变为 `"汐：括号又漏出来了"`，说明问题已在群内可见。

---

## 二、 三个根因与对应手术

| # | 根因 | 源码位置 | 已落地修复 |
|---|---|---|---|
| 1 | `must_reply=False` 的群聊自由回合在模型“决定闭嘴”时仍被强行挽救外发 | `runtime/agent_runner.py:216`, `runtime/reply_rescue.py` | 非点名回合若原文含括号思考，一律不再挽救；纯干净台词才允许补发 |
| 2 | 括号内心独白 `（…）` / `(…)` 未被识别为思考块 | `runtime/reply_rescue.py`, `adapters/onebot/send_guard.py` | 新增 `PAREN_BLOCK_RE`、`LEADING_PAREN_RE`、`_is_inner_monologue` 与 `LEADING_THOUGHT_PAREN_RE`，双层剥离括号旁白 |
| 3 | 潜意识探针拿到空上下文 + 同行 Bot 外围发言误唤醒 | `mind/facade.py`, `mind/subconscious_probe.py` | `_recent_ctx()` 注入最近 6 条门控上下文；同行 Bot（`is_rival`）非点名发言跳过探针 |

---

## 三、 出站防线（三层纵深）

1. **生成层**：`rescue_unsent_reply` 逐级剥离 `<think>`、代码围栏、整句括号旁白与前缀括号旁白；剥离后为空则返回 `None`。
2. **语义层**：`_is_inner_monologue` 命中任何括号残留或元认知词（`用户/模型/工具/这轮没/没点我/不插嘴…`）即判定为独白，绝不外发。
3. **出站层**：`sanitize_outbound_text` 在拼装 reply/@ 之前先用 `LEADING_THOUGHT_PAREN_RE` 剥掉泄露前缀，双保险。

---

## 四、 验收记录（2026-10-30）

- 新增回归断言（`tests/unit/test_stage4_tools_and_runtime.py`）：
  - `（这轮没点我…我先不插嘴）` → `None`
  - `（这轮汐点名了，得回）` → `None`
  - `（这轮不用回）哪有 你眼睛太尖了` → `哪有 你眼睛太尖了`
  - `sanitize_outbound_text("（这轮得回）哪有 你眼睛太尖了")` → 不含前导括号
- `./scripts/qa_gate.sh` 全 7 道门禁通过：Ruff / Radon（0 functions worse than B）/ Pylint **10.00/10** / Mypy Strict **0 issues** / 73 项测试全绿 / 覆盖率 **90.24% (>=90%)**。
- `mind/facade.py` 重构后 **300 行以内**，`CognitiveCoreFacade.evaluate_incoming` 复杂度回到 B 级（探针逻辑抽离为 `subconscious_probe.apply_probe_if_allowed`）。
