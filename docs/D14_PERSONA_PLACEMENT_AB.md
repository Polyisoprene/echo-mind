# D14 人格块承载位置 A/B（设计，未上线）

## 假设

`rendered_mind_block` 包含逐轮动态状态（情绪、关系、记忆）。当前放在 **user** 轮；
变体 B 放进 **system** 提示。假设 B 能提升人格/指令遵循，但会：
- 让系统提示逐轮变化，破坏前缀缓存；
- 把动态状态当静态规则，可能导致过度入戏。

## 变体

| 变体 | 承载 | 代码 |
|---|---|---|
| A（现状） | user 轮 | `PromptComposer(..., persona_in_system=False)` |
| B（实验） | system | `PromptComposer(..., persona_in_system=True)` |

钩子默认关闭，线上行为不变；`tests/unit/test_prompt_placement.py` 锁定两种结构。

## 场景集（建议 24 条）

1. 群聊被点名 4 条；
2. 群聊无人点名 4 条；
3. 私聊撒娇/吃醋 4 条；
4. 边界/拒绝 4 条；
5. 记忆披露（private/secret）4 条；
6. 长上下文 4 条。

每条跑 3 个 seed，配对比较 A/B。

## 指标

- 人格一致性（人工 1–5）：同一人跨群/私聊语气是否一致；
- 指令遵循（0/1）：是否回应点名、是否遵守禁用词；
- 越权披露（0/1）：private/secret 是否出现；
- 重复/机械复读（0/1）；
- 延迟与 token 成本（前缀缓存命中率）。

## 判定

只有 B 在人格一致性上 **≥ +0.5** 且越权/禁用词不增加时，才切换；
否则保留 A，并在文档记录原因。

## 运行

```python
from echomind.runtime.prompt_composer import PromptComposer
a = PromptComposer(role, bot).compose(frame, read, unread)
b = PromptComposer(role, bot, persona_in_system=True).compose(frame, read, unread)
```

## Pilot 骨架（已可跑）

```bash
.venv/bin/python scripts/ab_persona_placement.py
# 输出 reports/persona_placement_prompts.json：6 个场景 × A/B 两套完整 messages
```

- 6 个 pilot 场景：群聊点名、群聊旁观、私聊撒娇、私聊吃醋、边界拒绝、private 披露；
- 只生成 prompt，**不调用模型**，避免未经确认的 token 消耗；
- 正式实验仍按上面 24 条场景 × 3 seed 扩展；判定规则不变。

实际 A/B 需要同一模型、同一采样参数、同一场景集；本轮不调用线上模型。

## Pilot 结果（2026-10-31，单 seed）

6 场景 × A/B，共 12 次生成；自动计分：

| 变体 | 必须回复命中 | 只输出 `<tool_call>` | 空回复 |
|---|---|---|---|
| A（user） | **5/5** | 0 | 0 |
| B（system） | **3/5** | **2** | 0 |

- `group_called`：A 输出 `<send_message>`；B 只输出 `<tool_call>recall_memory`，没有回复；
- `memory_disclosure`：A 用含糊措辞回应；B 只输出 `<tool_call>`；
- 边界/私聊场景两者都能拒绝或接话，差异主要在“是否真正回复”。

**结论（pilot）**：保留 A（user 轮），不切 system。

**限制**：单 seed、6 条、未传 tools schema、未做人工人格评分、裁判为自动规则；这是探索性证据，不是确认性实验。正式 24×3 + tools + 人工/裁判评分仍可做，但当前没有“B 更好”的信号。
