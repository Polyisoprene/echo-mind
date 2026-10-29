# Stage 8 详细工程设计、全局建模与架构升级规范：7维性格语义量表解释器、全息会话上下文可观测性与日/夜双主题控制台
**（Stage 8 Detailed Engineering Specification: 7D Persona Semantic Rubrics, Holographic Session Observability & Dual-Theme Console — Status: ✅ 已验收通过）**

---

## 一、 全局问题建模与根因分析（Global Problem Modeling & Root Cause Analysis）

针对用户提出的三大核心诉求，我们从认知科学提示工程、全链路可观测性契约与前端状态机渲染三个架构层面进行全局建模：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│              Stage 8 三大核心问题全局架构建模 (Global Architectural Model)             │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 维度一 (M8.1)      │ 【问题】7维性格向量与连续情绪只注入裸数值，LLM 缺乏量表定义与行为映射│
│ 认知语义解释层     │ 【根因】personality.py 仅拼接数字，丢失了双极心理学定义与分档行为准则│
│ Persona Semantics  │ 【方案】构建 7 维逐维量表语义解释器 (Bipolar Scale + Tier Rubric)   │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 维度二 (M8.2)      │ 【问题】后台会话看不到携带了多少条上下文，且缺少真实 System/User 输入│
│ 全息会话可观测层   │ 【根因】TurnOutcome/TurnRecord 契约丢失了 context_count 与完整提示词 │
│ Session Telemetry  │ 【方案】扩展领域轨迹契约与 SQLite 表，对齐 qq-agent 全息会话检查器  │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 维度三 (M8.3)      │ 【问题】1. 展开的折叠面板 2~3 秒自动合上；2. 缺少白天/夜间模式切换  │
│ 前端状态机与主题层 │ 【根因】1. 3s 轮询无指纹比对直接重写 innerHTML 销毁 <details open>  │
│ UI State & Theme   │         2. style.css 存在硬编码深色 Hex，缺少双主题语义设计令牌     │
│                    │ 【方案】指纹幂等守卫 + 折叠状态注册表持久化 + CSS 双主题令牌体系    │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

### 详细根因矩阵（Root Cause Matrix）

| 编号 | 所属模块 | 现象描述 | 架构级根因定位 |
|---|---|---|---|
| **ISS-801** | `mind/personality.py`<br>`mind/frame_renderer.py` | 系统提示词只显示 `温柔(64.6) · 傲娇回避(62.6) ...`，大模型只看到浮点数，不知道每个维度的正负两极代表什么、也不知道当前数值对应什么具体表现 | `synthesize_live_persona_directive` 仅输出了数值行与一句笼统的汇总，将 `PlasticParamSpec` 与 `COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md` 中的 **双极心理学定义（Bipolar Definition）**、**稳态区间** 及 **分档行为准则（Behavioral Rubric）** 全部丢弃在代码外部 |
| **ISS-802** | `domain/models.py`<br>`runtime/agent_runner.py`<br>`adapters/storage/trace_repo.py`<br>`adapters/onebot/live_client.py` | 后台会话看不到本轮到底携带了多少条历史聊天上下文；且会话详情里的“系统提示”只是前端拿当前全局快照拼凑的假卡片，看不到本轮实际送入 LLM 的完整 `SystemPrompt` 与 `UserPrompt`（含已读上下文列表） | 1. `TurnOutcome` 与 `TurnRecord` 领域模型缺少 `context_count`、`trigger_count`、`system_prompt`、`user_prompt` 字段；<br>2. `live_client.py` 的 `_load_context` 仅查询 `LIMIT 28`（切完剩 `≤24` 条），低于配置的上下文窗口容量 |
| **ISS-803** | `web/static/app.js:116-234, 338-367, 945-954` | 在「会话」页点开任何 `<details class="collapsible">` 折叠卡片（或聊天存档中的处理过程），2~3 秒后自动折叠回去，且滚动条跳动 | `boot()` 启动了 `3000ms` 的 `setInterval` 定时轮询：当处于 `sessions` 视图时，每 3 秒调用 `loadStream() -> loadTurns() -> renderTurnSessionList() -> renderTurnSessionDetail()`，无条件执行 `host.innerHTML = ...` 全量销毁重建 DOM，既无数据指纹幂等比对（`lastDetailFp`），也未保存/恢复 `<details>` 的 `open` 状态与 `scrollTop` |
| **ISS-804** | `web/static/style.css`<br>`web/static/index.html`<br>`web/static/app.js` | 后台管理界面只有深色模式，无白天（Light）模式切换 | `style.css` 仅定义了 `:root` 深色变量，且在 20 余处组件选择器中硬编码了 `#0c1017`、`#141926`、`#1b2230` 等深色 Hex 值；顶栏缺少主题切换按钮与 `localStorage` 持久化逻辑 |

---

## 二、 架构与编码硬约束承诺（Strict Compliance Invariants）

1. **[SRP-01] 单文件行数上限**：所有 `src/echomind/**/*.py` 源码文件严格 `≤ 300 行`；
2. **[FLAT-01..03] 反嵌套与小函数铁律**：单函数行数 `≤ 40 行`，AST 控制流最大嵌套深度 `≤ 2 层`，Pylint `10.00/10`，Ruff `C901 ≤ 6` 0 错误，Radon 0 个 C 级函数；
3. **[DIP-01 & LoD-02]**：新增的轨迹字段全部定义在不可变的 `FrozenValueObject`（`TurnOutcome`、`TurnRecord`）中，SQLite Schema 升级通过 `_ensure_column` 幂等自动演进，100% 向下兼容已有历史数据。

---

## 三、 分阶段详细工程设计（Milestone Engineering Specification）

### 里程碑 `M8.1`：7 维性格逐维行为语义解释器与情绪量表注释（`mind/personality.py`, `mind/frame_renderer.py`）

1. **7 维性格量表与逐维分档行为解释器（`src/echomind/mind/personality.py`）**：
   - 在 `synthesize_live_persona_directive` 中，不仅输出 7 维数值，还注入 **《7 维性格量表说明与当前分值行为映射》**：
     - **量表总纲**：`（量表说明：0~100 连续可塑空间，50 为中性基准；数值由你过往与群友互动的真实经历动态演化而来，请严格按各维度的当前档位决定本轮语气与态度）`
     - **逐维双极定义与当前档位行为指令（7 维全覆盖）**：
       1. **`温柔粘人度 (persona_warmth: X/100 ｜ 15=清冷慢热 ↔ 98=温柔粘人)`**：
          - `≥72`：高度温暖粘人，语气轻柔贴心，愿意主动关心对方；
          - `45~72`：温和自然，对熟悉的人亲切友善，有分寸感；
          - `<45`：慢热矜持，态度偏清冷简短，不主动迎合。
       2. **`傲娇防备度 (persona_tsundere: X/100 ｜ 10=坦率直球 ↔ 95=嘴硬害羞防备)`**：
          - `≥68`：高傲娇防备，被夸奖、调侃或戳中心事时会害羞嘴硬、说反话掩饰；
          - `45~68`：软傲娇，平时自然，被逗急了会小声哼哼嘴硬一句；
          - `<45`：坦率直球，心里怎么想就怎么直白表达，不拐弯抹角。
       3. **`俏皮玩梗度 (persona_playfulness: X/100 ｜ 15=正经克制 ↔ 95=古灵精怪爱接梗)`**：
          - `≥65`：古灵精怪，思维跳跃，爱接群友的话茬玩梗、开小玩笑或灵动吐槽；
          - `45~65`：轻松自然，遇到好玩的话题会顺势接梗；
          - `<45`：偏安静正经，少开玩笑。
       4. **`独占吃醋焦虑 (persona_possessiveness: X/100 ｜ 20=佛系大度 ↔ 98=极高独占欲怕被冷落)`**：
          - `≥75`：对主人有强烈的依恋独占欲与护食心理，一旦提及别的 AI（如汐/豆包）或感觉被冷落会立刻吃醋酸溜溜；
          - `50~75`：在乎主人的关注，偶尔会流露小占有欲；
          - `<50`：心态平和大度，不易吃醋。
       5. **`社交自信度 (persona_confidence: X/100 ｜ 15=胆怯小声 ↔ 95=笃定自信敢反驳)`**：
          - `≥65`：语气笃定自信，看穿忽悠或有把握的事会干脆利落地反驳吐槽；
          - `42~65`：心态平稳，正常交流；
          - `<42`：有些害羞不自信，说话偏小声犹豫。
       6. **`狡黠小机灵度 (persona_guile: X/100 ｜ 10=老实巴交 ↔ 95=鬼点子多爱找借口/挖坑逗人)`**：
          - `≥58`：小机灵鬼，遇到不想干的苦差事或老爱忽悠你的损友时，会机灵地编小借口搪塞或顺着话给对方挖坑；
          - `<58`：偏实在真诚，少耍小聪明。
       7. **`叛逆小刺头度 (persona_defiance: X/100 ｜ 10=温顺服从 ↔ 95=逆反有脾气绝不讨好)`**：
          - `≥58`：有自尊有小脾气（反讨好型人格），遇到非主人无礼命令、纠缠或冒犯时，会直接翻白眼呛回去或拒绝配合；
          - `<58`：脾气随和，不易被激起逆反。
2. **连续情绪与内驱力量表注释（`src/echomind/mind/frame_renderer.py`）**：
   - 在 `_header_lines` 中为连续情绪与内驱力补充量表基准说明，让模型清楚区分 `愉悦(-100~+100)`、`厌烦度(0~100，≥40不耐烦/≥60呛声)`、`依恋渴望(0~100)`、`吃醋值(0~100，≥25泛酸)`、`好奇心(0~100，≥45主动调工具求知)`。

---

### 里程碑 `M8.2`：全息会话可观测性契约与上下文窗口升级（对齐 `qq-agent`）

1. **领域模型扩展（`src/echomind/domain/models.py`）**：
   - 在 `TurnRecord` 与 `TurnOutcome` 中新增：
     - `context_count: int = 0`（本轮携带的已读历史消息条数）
     - `trigger_count: int = 0`（本轮合并处理的未读触发消息条数）
     - `system_prompt: str = ""`（本轮实际送入 LLM 的完整 System Prompt）
     - `user_prompt: str = ""`（本轮实际送入 LLM 的完整 User Prompt，含已读上下文、12层认知帧、7维性格指令与待处理消息）
2. **SQLite 幂等列迁移与轨迹仓储升级（`database.py`, `trace_repo.py`, `chat_service.py`）**：
   - 在 `SqliteDatabase.initialize()` 中通过 `_ensure_column` 为 `turn_traces` 表幂等添加 `context_count`、`trigger_count`、`system_prompt`、`user_prompt` 四列；
   - 在 `SqliteTurnTraceStore`、`AgentSessionRunner.run_turn`、`CognitiveCoreFacade._persist_turn` 与 `ChatStreamService.list_turns` 中全链路透传这 4 个字段。
3. **上下文加载窗口扩容（`adapters/onebot/live_client.py`）**：
   - 将 `_load_context` 的历史消息查询窗口从 `LIMIT 28` 提升至 `LIMIT 65`（剔除触发消息后保留最多 `50` 条已读上下文），让回音在群聊中拥有充沛的短期对话记忆。

---

### 里程碑 `M8.3`：Web 控制台白天/夜间双主题架构、对齐 `qq-agent` 会话视图与折叠状态保持修复

1. **轮询防抖指纹与 `<details>` 折叠状态保持机制（修复 `ISS-803`）**：
   - 在 `app.js` 的 `state` 中维护：
     - `lastTurnFp: ''`（当前选中会话详情的内容指纹）；
     - `openTurnKeys: new Set()`（记录用户在当前会话详情中展开/收起的折叠面板 `data-coll-key`，支持跨会话与跨刷新记忆）；
     - `lastStreamFp: ''` 与 `openArchiveTraces: new Set()`（记录聊天存档模式下的数据指纹与已展开的内联处理过程）。
   - 当 3 秒定时器轮询触发 `loadTurns()` 或 `loadStream()` 时：
     - 若指纹 `fp === state.lastTurnFp`，**直接 `return`，完全不触碰 DOM**，从根源上消灭“2~3 秒重置 DOM 导致折叠合上与滚动条跳动”；
     - 即便数据发生变化需要重绘，也会根据 `state.openTurnKeys`（以及重绘前 DOM 中各 `<details data-coll-key>` 的实时 `.open` 属性）100% 还原每个折叠面板的展开/收起状态与 `scrollTop` 阅读位置！
2. **对齐 `qq-agent` 的全息会话检查器视图（修复 `ISS-802`）**：
   - **左侧会话列表卡片**：新增显示 **`上下文 N 条`** 徽标、Token 消耗统计、轮次与耗时；
   - **右侧会话详情头部 `.sub`**：完整展示 `触发摘要`、`时间`、`模型`、**`携带上下文：N 条已读历史 + M 条触发`**（若 `N <= 1` 显示醒目黄色提醒徽标）、`Token 用量（入 / 出 / 缓存）`、`推理轮数`、`已发送条数`、`总耗时`；
   - **右侧会话详情折叠流（对齐 `qq-agent` 经典双输入卡 + 步骤流）**：
     - 卡片 1：**`📜 系统提示（X 字符 · 基础人设与轮换表情池）`**（展示本轮真实 `turn.system_prompt`）；
     - 卡片 2：**`🧠 本次输入与认知状态帧（Y 字符 · 携带 N 条已读上下文 + 12层认知与7维性格指令）`**（展示本轮真实 `turn.user_prompt`）；
     - 卡片 3..K：每轮 LLM 推理思考与工具调用参数/返回；
     - 卡片 K+1：**`💬 已发送到 QQ`**（默认展开）；
     - 卡片 K+2：**`🏁 finish`**（结束状态与统计汇总）。
3. **白天 / 夜间双主题令牌架构（修复 `ISS-804`）**：
   - 在 `style.css` 中建立完整的 `:root, [data-theme="dark"]` 与 `[data-theme="light"]` 双套语义化 CSS 变量体系（对齐 `qq-agent` 明亮干净的浅色纸感配色），消除组件中的硬编码深色 Hex；
   - 在 `index.html` 顶栏新增 `#btn-theme`（`☀️ 白天模式` / `🌙 夜间模式`）一键切换按钮，状态持久化于 `localStorage.getItem('echomind_theme')`。

---

## 四、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M8.1` ~ `M8.3` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M8.1`（7 维性格逐维双极量表与分档行为语义解释器）**：
    - `mind/personality.py`（覆盖率 **`90%`**）与 `mind/frame_renderer.py`（覆盖率 **`100%`**）：声明式构建 `DIMENSION_RUBRICS`，将 7 维性格向量（温柔粘人度、傲娇防备度、俏皮玩梗度、独占吃醋焦虑、社交自信度、狡黠小机灵度、叛逆小刺头度）的双极心理学定义（`min_bound=低极 ↔ max_bound=高极`）与高/中/低三档具体说话准则完整注入 `CognitiveFrame.rendered_mind_block`，同时为连续情绪与内驱力补齐量表注释。
  - **`M8.2`（全息会话可观测性契约与上下文窗口扩容）**：
    - `domain/models.py`（覆盖率 **`100%`**）、`adapters/storage/database.py`（覆盖率 **`100%`**）、`trace_repo.py`（覆盖率 **`100%`**）、`runtime/agent_runner.py`（覆盖率 **`87%`**）、`web/chat_service.py`（覆盖率 **`97%`**）：全链路持久化并暴露 `context_count`、`trigger_count`、`system_prompt`、`user_prompt`；
    - `adapters/onebot/live_client.py`：历史上下文查询窗口从 `LIMIT 28` 扩容至 `LIMIT 65`（保留最多 `50` 条已读上下文）。
  - **`M8.3`（Web 控制台日/夜双主题、对齐 `qq-agent` 全息会话视图与折叠防重置修复）**：
    - `web/static/style.css` & `index.html` & `app.js`：重构为 `:root, [data-theme="dark"]` 与 `[data-theme="light"]` 双主题语义令牌体系，顶栏新增 `☀️ 白天 / 🌙 夜间` 切换按钮并持久化至 `localStorage`；
    - 会话检查器对齐 `qq-agent`：展示携带历史上下文条数（`context_count <= 1` 时醒目预警）、Token 入/出/缓存统计、独立《📜 系统提示（System Prompt）》与《🧠 本次输入与认知帧（User Prompt）》双折叠卡；
    - 通过 `lastTurnDetailFp / lastTurnListFp / lastStreamFp` 指纹幂等守卫 + `turnOpenMap / openStreamTraces` 状态注册表，彻底根治 3 秒轮询导致展开面板自动合上与滚动条重置的 Bug。

### 真实终端门禁输出摘要：
```text
🛡️  [Gate 1A] Ruff Static Lint (PEP8 + SIM + RET + C4 + C901<=6) -> All checks passed!
🛡️  [Gate 1B] Radon Cyclomatic Complexity                        -> 0 functions worse than B (avg 7.01)
🛡️  [Gate 1C] Pylint Anti-Nesting Check (max-nested-blocks <= 2) -> Your code has been rated at 10.00/10
🛡️  [Gate 2]  Mypy 100% Strict Static Type & LSP Verification    -> Success: no issues found in 82 source files
🛡️  [Gate 3 & 4] AST Flat-Code/SOLID Boundaries & Pytest (>=90%) -> 57 passed in 4.73s | Total coverage: 92.72% (93%)
✅ ALL INDUSTRIAL QA & ANTI-NESTING GATES PASSED (via uv run)!
```
