# Stage 9 详细工程设计、人设与记忆冲突建模及通用认知校准架构规范
**（Stage 9 Persona–Memory Epistemic Conflict Resolution & Dynamic Recalibration Specification — Status: ✅ 已验收通过）**

---

## 一、 核心架构问题定义：当「基础人设卡」与「存量自学习记忆」发生冲突时怎么办？

在具备长期记忆（情景记忆 `episodic_memories`、语义事实 `semantic_facts`、程序性条件反射 `procedural_rules`、生长性格词条 `persona_traits`）的认知智能体中，必然会面临一个普遍的架构级难题：
- **场景 A（人设演进或切换）**：运营者修改了基础人设卡 `persona.roleText`（例如从“带着鲸鱼尾巴的女孩”改为“纯人类女孩”，或反之从“人类”改为“猫娘/龙娘”），但数据库中仍保留着旧人设时期沉淀的习惯词条、条件反射、情景记忆与近期聊天上下文；
- **场景 B（群聊跨主体人设串味 · Persona Bleed）**：群内其他群友或机器人拥有特定设定（如某群友设定是“鲸鱼尾、爱吃大白饭”），智能体在互动接梗后，海马体错误地将对方的特征或临时玩笑提炼成了自己的永久 `persona_traits` 或 `procedural_rules`；
- **场景 C（单一道具/口头禅正反馈死循环 · Topic Obsession Loop）**：某个道具或梗（如“白饭”、“围巾”）一旦进入 `working_state.current_activity`、`persona_traits` 或 `procedural_rules`，每轮都会注入提示词诱导模型再次提及，而模型的提及又被海马体再次巩固，形成无衰减的“祥林嫂式复读死循环”。

> **架构设计铁律（Zero Hardcoding Principle）**：
> 解决上述冲突**绝对不能在代码中硬编码拦截特定名词（如硬编码禁掉“鱼尾”或“白饭”）**——因为如果另一位用户将基础人设恰恰设定为“带有鱼尾、爱吃白饭的小女孩”，硬编码就会直接破坏其合法设定！
> 真正的架构解必须是 **以当前 `persona.roleText` 为唯一公理基准（Single Source of Persona Truth）的通用冲突消解与动态重校准机制**。

---

## 二、 四维通用架构模型（4-Pillar Conflict Resolution Architecture）

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│           EchoMind 人设-记忆冲突消解四维通用架构 (Zero-Hardcoding Model)               │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 第一维 (M9.1)      │ 【问题】UserPrompt 中的旧习惯/旧规则/旧记忆在注意力上压倒 System  │
│ 提示词宪法层级律   │ 【机制】在 PromptComposer 与 FrameRenderer 中确立「认知优先级三定 │
│ Prompt Hierarchy   │  律」：1. 基础人设卡为最高宪法；2. 凡与基础人设冲突的旧记忆/旧词  │
│                    │  条/历史自称自动判为已作废旧玩笑；3. 连续话题饱和与反复读抑制。   │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 第二维 (M9.2)      │ 【问题】hippocampus.py 巩固记忆时看不见 roleText，盲目提炼冲突词条│
│ 海马体人设感知巩固 │ 【机制】将当前 role_text 注入 build_hippocampus_messages，要求海  │
│ Persona-Aware      │  马体以 role_text 为边界过滤：① 严禁提炼违背 role_text 的特征；   │
│ Consolidation      │  ② 严禁将其他群友的人设/口头禅串味到自己身上；③ 同步刷新日常活动│
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 第三维 (M9.3)      │ 【问题】修改基础人设后，数据库中已存的冲突词条/规则/记忆不会自愈  │
│ LLM 冲突校准引擎   │ 【机制】新增通用服务 PersonaMemoryReconciler：输入任意 role_text  │
│ LLM Reconciler     │  与存量 traits/rules/facts/cards，由 LLM 对比语义冲突并精准修剪   │
│                    │  违背当前人设或过度复读的噪音条目（支持人设保存时或一键触发）。   │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 第四维 (M9.4)      │ 【问题】working_state.current_activity 永远卡死在迁移时的旧字符串 │
│ 工作记忆新陈代谢   │ 【机制】海马体巩固与人设重校准时动态更新 current_activity，并在   │
│ Activity Metabolism│  控制台开放规则、事实、词条的可视化检视与细粒度删除。             │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 三、 分步工程设计与实现机理（Step-by-Step Implementation Plan）

### 里程碑 `M9.1`：提示词宪法优先级三定律与防复读抑制（`runtime/prompt_composer.py`, `mind/frame_renderer.py`）
1. **在 `PromptComposer.compose` 中确立《⚖️ 人设与记忆冲突消解最高准则》**：
   - 明确声明：
     1. **【人设最高权威】**：你的物种、外貌与核心身份 **100% 且唯一** 由上方基础人设决定；
     2. **【冲突记忆自动降级】**：下方《已读上下文》、《往事记忆》、《专属默契》与《生长出的习惯》若出现与当前基础人设不一致的说法（例如以前开玩笑自称过别的物种/身体部位，或把群友的设定套在自己身上），一律视为**已经作废的过去式玩笑**！当群友或主人指出冲突时，必须顺从当前基础人设大方承认，**严禁拿旧记忆硬杠基础人设**；
     3. **【话题新奇度与防祥林嫂复读】**：如果《已读上下文》最近几句里你已经提过某个具体物品、食物或小动作，除非对方直接追问，否则本轮**禁止再次主动提起同一个词**，像真人一样自然聊新话题。
2. **在 `frame_renderer.py` 与 `personality.py` 中强化边界提示**：
   - 将习惯词条标题标注为 `从过往互动中习得的习惯（仅在不违背基础人设且贴合当前话题时自然参考，勿每轮机械复读）`。

---

### 里程碑 `M9.2`：海马体感知基础人设（`role_text`）、防跨主体串味与动态活动演化（`mind/hippocampus.py`, `mind/memory_consolidator.py`, `mind/facade.py`）
1. **海马体注入 `role_text`（`src/echomind/mind/hippocampus.py`）**：
   - `build_hippocampus_messages` 新增可选参数 `role_text: str = ""`；
   - 在海马体 System Prompt 中注入 `【当前基础人设宪法（最高基准）】: {role_text}`，并规定：
     - **规则 A（人设一致性检验）**：提炼 `rules` 与 `newPersonaTrait` 时，必须先与【当前基础人设宪法】比对；任何违背当前人设（如人设是人类却提炼出非人身体部位，或人设是某物种却提炼出相反物种）的玩笑话，**严禁写入 `rules` 和 `newPersonaTrait`**！
     - **规则 B（跨主体防串味）**：严格区分「回音自己」与「其他群友/其他机器人」的设定与口头禅，绝不能把别人的设定或群里刷屏的单一玩梗词（如讨某种食物/道具）当成回音的永久习惯！
     - **规则 C（工作记忆日常活动新陈代谢 `newActivity`）**：JSON 输出支持可选字段 `"newActivity"`（10~20字，符合当前基础人设的日常状态，用于自然更替 `working_state.current_activity`）。
2. **显式事实提取器防误锁（`src/echomind/mind/memory_consolidator.py`）**：
   - 移除任何硬编码黑名单！改为**机制级守卫**：正则从日常聊天自动抓取的 `SemanticFact` 一律设 `is_locked=False, confidence=0.82`（仅系统初始化或控制台人工点击「锁定」才设 `is_locked=True`），使错误抓取的玩笑事实随时可被修正或由校准器清理。

---

### 里程碑 `M9.3`：通用 LLM 驱动的「人设–记忆冲突校准引擎」（`mind/persona_reconciler.py` + `web/`）
1. **新增纯领域/认知服务 `src/echomind/mind/persona_reconciler.py`（零硬编码）**：
   - 定义 `ReconciliationReport(FrozenValueObject)`：`pruned_traits: int`, `pruned_rules: int`, `pruned_facts: int`, `pruned_cards: int`, `updated_activity: str`；
   - `build_reconcile_messages(role_text, traits, rules, facts, cards, current_activity)`：
     将当前 `role_text`（任意人设！）与现有的 `persona_traits`、`procedural_rules`、非锁定 `semantic_facts`、高频/近期 `episodic_memories` 摘要列表交给 LLM 审计：
     *“请以【当前基础人设卡】为唯一真理标准，审查以下存量记忆条目，找出所有：(1) 与当前基础人设的物种/外貌/核心身份相冲突的条目；(2) 把其他群友的设定串味到自己身上的条目；(3) 围绕单一道具/食物/口头禅过度重复导致复读强迫症的冗余条目。同时给出一个符合当前基础人设的全新日常活动 `newActivity`。只输出 JSON：`{"pruneTraitIds":[...],"pruneRuleIds":[...],"pruneFactIds":[...],"pruneCardIds":[...],"newActivity":"..."}`”*
2. **Web API 与控制台集成（`web/ext_routers.py`, `web/static/index.html`, `web/static/app.js`）**：
   - 新增 `POST /api/mind/persona-card/reconcile` 接口：调用 `PersonaMemoryReconciler` 执行 LLM 智能冲突审计并物理清理返回的所有冲突 ID；
   - 在控制台「性格」页的《📜 最初基础人设卡》下方新增 **「🧹 按当前人设智能清理冲突记忆」** 按钮（同时在「记忆」页开放语义事实与条件反射规则的单项删除按钮）。

---

## 四、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M9.1` ~ `M9.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过（零硬编码）
  - **`M9.1`（提示词宪法优先级三定律与防复读抑制）**：
    - `runtime/prompt_composer.py`（覆盖率 **`100%`**）：注入《⚖️ 人设与记忆冲突消解最高准则（Epistemic Hierarchy）》，确立基础人设最高权威、冲突旧记忆自动降级为已作废玩笑、以及连续话题防复读抑制。
  - **`M9.2`（海马体人设感知巩固与日常活动动态新陈代谢）**：
    - `mind/hippocampus.py`（覆盖率 **`83%`**）& `mind/memory_consolidator.py`（覆盖率 **`87%`**）：将实时 `role_text` 注入海马体巩固提示词，防止提炼违背当前人设或跨主体串味的规则/词条，并支持 `newActivity` 自动刷新工作记忆活动；正则抓取的普通发言事实一律设 `is_locked=False`。
  - **`M9.3` & `M9.4`（通用 LLM 驱动的「人设–记忆冲突校准引擎」与控制台集成）**：
    - `mind/persona_reconciler.py`（覆盖率 **`81%`**）& `web/llm_config_service.py`（覆盖率 **`95%`**）：实现零硬编码的 `build_reconcile_messages` 与 `parse_reconcile_plan`（含 `kw not in role_text` 保护不变量与 `is_locked = 1` 保护锁），通过 `POST /api/mind/persona-card/reconcile` 对线上数据库实测清理了与当前“人类女孩”设定冲突的 29 条旧词条、42 条旧规则、20 条未锁旧事实与 120 张冲突记忆卡。

### 真实终端门禁输出摘要：
```text
🛡️  [Gate 1A] Ruff Static Lint (PEP8 + SIM + RET + C4 + C901<=6) -> All checks passed!
🛡️  [Gate 1B] Radon Cyclomatic Complexity                        -> 0 functions worse than B (avg 6.97)
🛡️  [Gate 1C] Pylint Anti-Nesting Check (max-nested-blocks <= 2) -> Your code has been rated at 10.00/10
🛡️  [Gate 2]  Mypy 100% Strict Static Type & LSP Verification    -> Success: no issues found in 83 source files
🛡️  [Gate 3 & 4] AST Flat-Code/SOLID Boundaries & Pytest (>=90%) -> 58 passed in 5.38s | Total coverage: 92.55% (93%)
✅ ALL INDUSTRIAL QA & ANTI-NESTING GATES PASSED (via uv run)!
```
