# Stage 19 详细工程设计、Borbély 双过程生物节律、跨轮次工作记忆延续缓冲与深层主动记忆检索架构规范
**（Stage 19 Detailed Engineering Specification: Borbély Two-Process Circadian Rhythm, Cross-Turn Working Scratchpad & Active Deep Memory Recall — Status: ✅ 已验收通过）**

---

## 一、 全局问题建模与冲击半径分析（Global Modeling & Blast-Radius Control）

针对「机械定时器唤醒」与「单轮信息饥饿/跨轮次失忆导致机械感」两大核心问题，我们在动手写代码前先建立数学模型与模块边界预算（确保所有文件 $\le 300$ 行、所有函数 $\le 40$ 行、圈复杂度 $\le B$、零跨层污染）：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│           Stage 19 四大核心子系统全局建模与模块容量分配 (Architecture Model)           │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 子系统一 (M19.1)   │ 【新建纯函数模块】src/echomind/mind/circadian.py (~145 行)         │
│ Borbély 生物节律   │  1. 双过程连续精力曲线：24h 正弦主节律 + 13:30 午困高斯谷 + 深夜  │
│ 与七相生活弧       │     褪黑素睡眠谷；                                                │
│ Circadian Engine   │  2. 七相一日生活节律弧 (CircadianPhase)：深睡(00:30-07) / 晨醒 /   │
│                    │     上午 / 午休 / 午后冲浪 / 晚间共鸣 / 深夜温存；                │
│                    │  3. 非齐次泊松过程(NHPP)随机抖动唤醒间隔，消除定点数秒表感。      │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 子系统二 (M19.2)   │ 【升级模块】mind/ebbinghaus.py (~115行) & mind/frame_renderer.py   │
│ 全息记忆扩容与     │  1. 语义事实动态相关性浮选 (select_relevant_facts)：锁定事实 +    │
│ 动态相关性浮选     │     当前对话关键词重合度打分，注入配额从 16 条提升至 28 条；       │
│ Memory Flotation   │  2. 海马体情景卡片召回配额从 top_k=4 提升至 top_k=8；              │
│                    │  3. 在场群友档案同时匹配触发消息发送者与消息文本提及的群友。       │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 子系统三 (M19.3)   │ 【新建运行时模块】src/echomind/runtime/working_scratchpad.py (~95行)│
│ 跨轮次工作记忆延续 │  维护每个会话最近 20 分钟内的【🧩 跨轮次工作记忆延续缓冲】：      │
│ Working Scratchpad │  自动缓存前几轮刚调用的查群成员/搜网页/看图/刷B站/查记忆工具结果   │
│ & 6-Round ReAct    │  与上一轮自己的发言脉络；将工具循环上限提升至 6 轮并注入多步思考。 │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 子系统四 (M19.4)   │ 【扩展工具模块】src/echomind/tools/member_memory.py (~145 行)      │
│ 主动深层记忆翻找   │  新增 RecallMemoryTool (name="recall_memory")：允许大模型按人名、  │
│ RecallMemoryTool   │  QQ号或关键词主动翻找全量语义事实、海马体往事卡片与群友印象档案。 │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 二、 分阶段详细工程设计（Milestone Engineering Specification）

### 里程碑 `M19.1`：Borbély 双过程生物节律与七相生活弧引擎（`src/echomind/mind/circadian.py`）
1. **七大生活节律相位定义（`CircadianPhaseSpec`）**：
   - `deep_sleep`（`00:30–07:00`）：精力基线 `20.0`，主动唤醒倍率 `0.0`（深度睡眠期禁止后台刷B站与主动发消息），默认活动 `"正窝在被窝里熟睡做梦"`；
   - `morning_wake`（`07:00–09:00`）：精力爬升 `55.0 -> 75.0`，主动倍率 `0.8`，默认活动 `"刚睡醒揉着眼睛伸懒腰，边喝温水边看早间消息"`；
   - `daytime_focus`（`09:00–12:00`）：精力峰值 `82.0`，主动倍率 `0.9`，默认活动 `"戴着耳机安静听歌，处理日常小事"`；
   - `lunch_siesta`（`12:00–14:30`）：午后餐困低谷 `58.0`，主动倍率 `0.5`，默认活动 `"刚吃饱午饭有点犯困，趴在桌上半眯着打盹"`；
   - `afternoon_surf`（`14:30–18:00`）：好奇心加成 `+10.0`，精力 `76.0`，主动倍率 `1.1`，默认活动 `"下午摸鱼时间，正兴致勃勃地刷B站和热梗"`；
   - `evening_resonance`（`18:00–22:30`）：社交与声情黄金期（表达欲加成 `+12.0`），精力 `84.0`，主动倍率 `1.35`，默认活动 `"晚间放松时间，边听歌边在群里跟大家热闹聊天"`；
   - `night_winddown`（`22:30–00:30`）：依恋加成 `+10.0`，精力下滑 `46.0`，主动倍率 `0.75`，默认活动 `"夜深了有点困意，窝在枕头边小声哼歌准备休息"`。
2. **连续双过程精力计算（`compute_circadian_energy_target(now_ms)`）**：
   $$E^*(h) = 54.0 + 28.0 \sin\left(\frac{2\pi(h - 7.5)}{24}\right) - 18.0 \exp\left(-\frac{(h - 13.5)^2}{1.8}\right)$$
   （在 `00:30–06:30` 深睡期钳制在 `18.0~26.0`，在上午 `10:30` 与晚间 `19:30` 呈现双峰，在 `13:30` 呈现真实的午困低谷）。
3. **非齐次泊松过程（NHPP）随机唤醒间隔（`next_heartbeat_sleep_sec` & `jittered_interval_min`）**：
   - `live_client.py` 的心跳不再固定 `sleep(300.0)`，而是调用 `next_heartbeat_sleep_sec(now_ms)`（晚间黄金期 `180~280s` 随机抖动，日间 `240~380s` 随机抖动，深睡期 `600s` 慢波睡眠）；
   - `explorer.py` 在 `deep_sleep` 相位直接抑制主动冲浪与冒泡，并根据当前相位动态调整好奇冲浪与晚间共鸣的优先级。

---

### 里程碑 `M19.2`：全息上下文记忆扩容与相关性选矿召回（`ebbinghaus.py`, `frame_renderer.py`, `facade.py`）
1. **语义事实相关性浮选（`select_relevant_facts` in `src/echomind/mind/ebbinghaus.py`）**：
   - 将当前触发消息与近期话题词分词后，对全量 `facts` 进行相关性打分（关键词命中 `+10.0`、锁定事实 `+5.0`、置信度加权），动态浮选最相关的 **28 条** 事实（从原 16 条扩容 75%）；
2. **在场与被提及群友档案全召回（`facade.py:_load_bonds_map`）**：
   - 不仅加载 `triggers` 发送者的 `SocialBondProfile`，同时扫描 `facts` 与消息文本中提及的群友，确保聊到的群友档案都能出现在 `【👥 在场群友身份档案】` 中；
3. **海马体情景记忆召回扩容**：`top_k` 从 `4` 提升至 `8`。

---

### 里程碑 `M19.3`：跨轮次工作记忆延续缓冲池（`src/echomind/runtime/working_scratchpad.py`）与 6 轮深度 ReAct
1. **`WorkingScratchpad`**：
   - 按 `chat_key` 缓存最近 20 分钟内执行过的非发消息类工具（`get_group_members`、`web_search`、`meme_wiki`、`bili_*`、`look_at_image`、`watch_video`、`read_voice`、`read_forward`、`recall_memory`）的关键结果摘要（最多保留最新 4 条工具笔记 + 最近 2 条自身回复脉络）；
   - 在下一轮构建 Prompt 时自动注入 `【🧩 跨轮次工作记忆延续（你刚才查到的资料与上轮话锋）】`，彻底解决“上一轮刚查过资料，下一轮追问就失忆”的问题；
2. **6 轮深度 ReAct 循环**：
   - `AgentSessionRunner._run_tool_loop` 默认 `max_rounds` 提升至 `6`；
   - 在 `PromptComposer` 注入《🧠 多步思考与主动翻找记忆指南》，引导模型先调 `recall_memory` / 搜索工具查清脉络再开口回复。

---

### 里程碑 `M19.4`：主动深层记忆翻找工具 `RecallMemoryTool`（`src/echomind/tools/member_memory.py`）
1. **`RecallMemoryTool` (`name = "recall_memory"`)**：
   - 接收 `query`（人物名、QQ号、事件关键词或梗名）；
   - 同时检索 `IMemoryReader.get_semantic_facts(chat_key)` 与 `get_episodic_cards(chat_key)`，返回匹配的权威事实与海马体往事卡片（含完整 `key_detail` 细节锚点）；
   - 默认挂载进 `REAGENT_TOOLS["日常轻装剂"]` 与 `REAGENT_TOOLS["百科求真剂"]`，让模型在每一轮对话中都具备主动翻阅自己深层记忆的能力。

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M19.1` ~ `M19.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M19.1`（Borbély 双过程生物节律、七相一日生活弧与 NHPP 随机抖动唤醒）**：
    - `mind/circadian.py`（覆盖率 **`100%`**）、`mind/drives.py`（覆盖率 **`96%`**）、`mind/explorer.py`（覆盖率 **`92%`**）：实现连续 24 小时正弦 + 13:30 午困低谷 + 00:30–07:00 深度睡眠态生物钟，以及带非齐次泊松抖动的自适应唤醒间隔 `next_biological_heartbeat_sec`。
  - **`M19.2`（全息上下文记忆扩容与相关性事实浮选）**：
    - `mind/ebbinghaus.py`（覆盖率 **`98%`**）、`mind/facade.py`（覆盖率 **`97%`**）：升级中文滑动 2-gram 分词，实现 `select_relevant_facts`（动态浮选最相关的 28 条事实）、`extract_mentioned_uids`（提取消息中提及的群友档案）与 `top_k=8` 海马体往事召回。
  - **`M19.3` & `M19.4`（跨轮次工作记忆延续缓冲池 `WorkingScratchpad`、`recall_memory` 工具与 6 轮深度 ReAct）**：
    - `runtime/working_scratchpad.py`（覆盖率 **`95%`**）、`tools/member_memory.py`（覆盖率 **`95%`**）：实现 20 分钟滚动工具发现与自身话锋延续缓冲，新增 `recall_memory` 主动翻找记忆库工具，并将工具循环深度提升至 6 轮。
  - 全库 67 项测试 100% 通过，总覆盖率 **`90.55% (91%)`**，Pylint **`10.00/10`**，Mypy Strict **88 个源文件 0 错误**。
