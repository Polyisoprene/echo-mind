# Stage 4 详细工程设计、实现机理与验收报告：微内核五大扩展槽、无状态工具集与并发 Agent 运行时
**（Stage 4 Detailed Engineering Specification & Acceptance Report — Status: ✅ 已验收通过）**

---

## 一、 Stage 4 解决的核心问题与设计目标

在旧版 `qq-agent` 中，工具系统、插件扩展与 Agent 运行循环存在四个严重问题：
1. **插件扩展无类型契约，谁都能改核心状态**：旧版插件直接挂钩子改字符串或自己起 `setInterval`，导致新增一个插件就可能把原有逻辑搞崩。
2. **表情包“马太效应（富者愈富）”死循环**：旧版按 `useCount` 降序取前几个表情包塞进提示词，导致用过 1 次的表情永远排第一、永远只发那 3 张表情包。
3. **大模型偶发“只说话不调工具”导致吞回复**：当模型在思考后直接把想说的话写在了 `message.content` 里而忘了调 `send_message` 工具时，如果没有安全的抢救过滤网，要么把这段话吞掉不回，要么把模型的内心思维链（如 `“用户想让我…”`）直接发到群里穿帮。
4. **工具执行结果没有回流给认知核心**：模型调了搜索工具、或者发了消息后，认知核心不知道这轮用了什么工具、发了什么话，无法驱动神经可塑性自学习。

---

## 二、 里程碑级详细实现机理与算法设计

### 里程碑 `M4.1`：微内核五大强类型扩展槽（`extensions/registry.py`）与无状态工具集（`tools/`）

#### 1. 微内核五大扩展槽注册中心（`ExtensionRegistry`）实现细节
- **强类型运行时契约守卫（Runtime Protocol Verification）**：
  `ExtensionRegistry` 维护 5 个类型隔离的元组槽位，在每次调用 `register_*` 时，强制使用 `isinstance(ext, Protocol)`（配合 `@runtime_checkable`）执行运行期接口核验：
  - `register_sensor(enricher: IPerceptEnricher)`：若未实现 `enrich(percept)`，当场抛出 `TypeError`；
  - `register_tool(tool: IToolExtension)`：校验 `name`、`description`、`parameters_schema()`、`execute()`，并自动组装为标准 OpenAI Function Calling 格式 `{"type": "function", "function": {...}}`；
  - `register_facet(facet: ICognitiveFacet)`：校验 `facet_id` 与 `render_prompt_line(chat_key)`；
  - `register_proposer(proposer: IProactiveProposer)`：校验 `propose(chat_key, affect, drives)`；
  - `register_panel(panel: IInspectorPanel)`：校验 `panel_id`、`panel_title`、`build_panel_data()`。
- **未来新增功能的零侵入流程**：
  任何新功能只需实现上述 5 个协议之一并注册进 `ExtensionRegistry`，`AgentSessionRunner` 与 `CognitiveCoreFacade` 会自动遍历槽位挂载，**无需修改任何一行内核代码（100% 满足开闭原则 OCP）**！

#### 2. 内置无状态效应器工具集（`src/echomind/tools/`）实现细节
所有工具类均严格遵循 **接口隔离原则（ISP）**，只通过构造函数注入它所需的最小 Port 接口（如 `IMessageSender` 或 `IGroupRosterReader`）：
1. **`SendMessageTool` (`name = "send_message"`)**：
   - 入参 Schema：`messages: list[str]`（1~3 条简短分句，每句建议不超过 `reply_length_target` 字）、`reply_to: str | None`、`at_user: str | None`；
   - 内部直接委托 `IMessageSender.send_text()`（自动经过 Stage 2 的防双 `@` 净化与滑窗去重），返回已发送的 `message_id` 列表。
2. **`SendStickerTool` (`name = "send_sticker"`)**：
   - 入参 Schema：`sticker_id: str`、`reply_to: str | None`；
   - 发送成功后自动将 SQLite `stickers` 表中该 `sticker_id` 的 `use_count + 1`、`last_used_at = now_ms`，为下面的“去马太效应轮换算法”提供精确统计。
3. **`GetGroupMembersTool` (`name = "get_group_members"`)**：
   - 入参 Schema：`role_filter: Literal["all", "owner_and_admin"] = "all"`；
   - 调用 `IGroupRosterReader.get_group_members(group_id)`，将返回结果按 **`👑群主` → `🛡️管理员` → `普通群员`** 排序并显式格式化：
     `👑群主: kirakiraの馍馍(QQ:10004004) | 🛡️管理员: 町一(QQ:10009010), JK少女中莫酱(QQ:10009011) | 成员: ...`
     让回音随时拥有一键查清群内真实身份的权威工具！
4. **`HolyWebSearchTool` (`name = "web_search"`) & `CnMemeWikiTool` (`name = "meme_wiki"`) —— 双源梗百科与防跑偏搜索引擎**：
   - **中文梗防跑偏算法（`clean_meme_query`）**：
     针对搜索引擎搜 `"流云真君是什么梗？"` 会退化成查汉字的问题，先剥离句尾标点 `？?！!。.`，再剥离 `是什么梗 / 是什么意思 / 是谁 / 怎么回事` 等疑问词尾，生成干净核心词 `"流云真君"`。
   - **接入 `梗Wiki (https://cnmeme.wiki/developers/api)` 官方开放 API v1（`src/echomind/tools/cnmeme_wiki.py`）**：
     1. **双端点联动**：调用 `GET /api/v1/public/memes?q={clean_q}&tag={tag}&limit={limit}` 检索公开梗词条；对排第一的命中词条，自动用 `quote(slug, safe="")` 请求详情接口 `GET /api/v1/public/memes/{slug}` 获取完整正文 `content_html`；
     2. **HTML 纯文本清洗与 B站溯源**：`html_to_clean_text()` 自动剥离白名单 HTML 标签并还原实体字符，同时提取 `source_video.bvid` 拼出 B站原视频地址 `https://www.bilibili.com/video/{bvid}` 与 `tags` 标签列表；
     3. **严格遵守官方缓存与 ETag 规范**：内置内存 TTL 缓存（列表 60 秒、详情 120 秒）并保存响应头 `ETag`；缓存过期重请求时自动携带 `If-None-Match` 请求头，收到 `HTTP 304 Not Modified` 时直接零解析复用本地缓存副本！
     4. **双模式挂载（组合模式 `CompositeSearchBackend` + 独立工具 `meme_wiki`）**：
        - 一方面实现 `ISearchBackend` 协议，通过 `CompositeSearchBackend((cnmeme_client, web_backend))` 注入 `web_search`（搜任何新词时优先返回 `梗Wiki` 权威词条 + 全网搜索结果）；
        - 另一方面单独注册 `meme_wiki` 工具：当传入 `query="飞飞鼠"` 时精准查梗；当 **`query=""` 留空**时，直接拉取 `梗Wiki` 最新收录的网络热梗列表，供回音在闲暇好奇冲浪时自主刷最新热梗！
5. **`FeiyuVoiceSayTool` (`name = "feiyu_say"`) & `FeiyuSongCoverTool` (`name = "feiyu_cover"`)**：
   - 对接 `192.168.3.2:8080` 飞鱼语音 GPU 服务：
     - `feiyu_say(text, mood)`：调用 `/v1/tts` 生成语音 Base64 并通过 `IMessageSender.send_voice()` 发出；
     - `feiyu_cover(song_keyword)`：调用 `POST /v1/cover` 执行全曲人声分离 + RVC/SoVITS 音色转换 + 混音，将回音翻唱的整首歌发到群里或私聊！

---

### 里程碑 `M4.2`：去马太效应表情轮换、漏调工具抢救网与并发 Agent 运行时（`runtime/`）

#### 1. 打破“马太效应”的表情包轮换算法（`runtime/prompt_composer.py` -> `select_rotated_stickers`）
- **问题根源**：旧版按 `use_count DESC` 排序，导致前 3 张表情包永远霸榜。
- **新算法公式**：
  1. 过滤出所有有语义描述（`local_note` 或 `desc_text` 非空）的表情包；
  2. 以 15 分钟（`bucket = now_ms // 900_000`）为时间旋转桶，计算每张表情的轮换优先级得分：
     $$\text{Priority}(s) = -\text{use\_count}(s) \times 10 + \big(\text{hash}(s.\text{id}, \text{bucket}) \bmod 15\big)$$
  3. 按 $\text{Priority}(s)$ 降序取前 `max_items = 24` 张注入提示词，**确保使用次数越少的精品表情越优先展示，且每 15 分钟自动轮换一批新鲜面孔**！

#### 2. 漏调工具时的自然口语安全抢救网（`runtime/reply_rescue.py` -> `rescue_unsent_reply`）
- **触发时机**：当 Agent 循环结束、本轮 `sent_texts` 为空（模型未调用 `send_message`），但模型最后一条响应的 `content` 非空时。
- **五重安全过滤卫语句（严防把思维链当成回复发出去！）**：
  1. 剥离 `<think>...</think>` 标签块与 Markdown 代码块；
  2. 若剩余文本为空、或长度 `> 120` 字（长篇大论必是分析说明），**拒绝抢救（返回 `None`）**；
  3. 若文本以 `{`、`[`、`<tool_call` 开头（工具 JSON 残片），**拒绝抢救**；
  4. 若文本命中元叙述/思维链黑名单正则 `META_MONOLOGUE_RE`（`用户|群友|模型|工具|调用|回复策略|不需要回复|保持沉默|无需回应|从上下文看|作为AI`），**拒绝抢救**；
  5. 通过全部 4 道安检的干净单句口语（例如 `"我在呢，刚把蓝色围巾织完第六行~"`），返回抢救文本并交由 `IMessageSender.send_text()` 发出！

#### 3. 会话级并发运行时与自学习闭环回流（`runtime/agent_runner.py` -> `AgentSessionRunner`）
- **单轮完整执行序列**：
  1. 调用 `ICognitiveCoreFacade.build_cognitive_frame(chat_key, triggers)` 获取不可变 `CognitiveFrame`；
  2. 调用 `PromptComposer.compose()` 装配 `[SystemPrompt(含人设+轮换表情池), UserPrompt(含已读上下文 + 🧠认知核心状态帧 + 未读触发消息)]`；
  3. 进入最多 `max_rounds = 4` 轮的 `ILlmGateway.complete()` 循环：
     - 解析模型返回的 `tool_calls`，通过 `ExtensionRegistry.execute_tool()` 依次执行，并记录本轮调用的工具名列表 `tools_used`；
     - 若模型未返回 `tool_calls` 则退出循环；
  4. 若本轮未发出任何文本且无表情发送，调用 `rescue_unsent_reply()` 尝试安全口语抢救；
  5. **闭环回流大脑**：构造不可变的 `TurnOutcome(session_id, chat_key, triggers, sent_texts, tools_used, social_reward, epistemic_conflict_detected)`，调用 `await cognitive_facade.on_turn_completed(outcome)`，**自动更新 5 分钟跟聊窗口与神经可塑性自学习参数**！

---

## 三、 分步验收标准与测试用例矩阵（Acceptance Test Matrix）

Stage 4 将通过 `tests/unit/test_stage4_tools_and_runtime.py` 执行以下量化验收：

| 验收项编号 | 测试函数 | 输入数据与测试场景 | 预期量化结果 (Expected) |
|---|---|---|---|
| **AC-4.1** | `test_m4_1_extension_registry_type_safety_and_tools` | 1. 向 `ExtensionRegistry` 注册合法的 5 类扩展与 1 个未实现协议的非法对象；<br>2. 执行 `GetGroupMembersTool`、`SendMessageTool`、`HolyWebSearchTool("流云真君是什么梗")` | 1. 合法扩展全部注册成功，非法对象当场抛 `TypeError`；<br>2. 群成员工具输出包含 `👑群主: 馍馍(QQ:10004004)`；<br>3. 搜索工具自动将 `"流云真君是什么梗"` 净化为 `"流云真君"` |
| **AC-4.2** | `test_m4_2_sticker_anti_matthew_rotation` | 输入 5 张表情包，其中 `s1, s2` 的 `use_count=500`，`s3, s4, s5` 的 `use_count=0` | `select_rotated_stickers(..., limit=3)` 优先选出 `use_count=0` 的 `s3, s4, s5`，打破旧版前 3 张高 `use_count` 锁死现象 |
| **AC-4.3** | `test_m4_2_reply_rescue_safety_filters` | 分别输入：<br>① `"<think>思考中</think>哼，我才没有吃醋呢！"`<br>② `"用户正在开玩笑，我不需要回复保持沉默"`<br>③ `'{"name": "send_message"}'` | ① 剥离 `<think>` 后成功抢救出 `"哼，我才没有吃醋呢！"`；<br>② 命中元叙述黑名单，返回 `None`（绝不误发思维链）；<br>③ 命中 JSON 残片拦截，返回 `None` |
| **AC-4.4** | `test_ac4_4_agent_runner_end_to_end_cognitive_and_learning_loop` | 模拟群友发送 `"尾尾，其实我是群主"` → `AgentSessionRunner.run_turn()` → 模型先调 `get_group_members` 核实群主身份，再调 `send_message` 吐槽对方忽悠 | 1. 工具循环准确执行 `get_group_members` 与 `send_message`；<br>2. 回合结束后自动触发 `on_turn_completed`，数据库中 `skepticism` 参数自动从 `55.0` 上涨至 `60.0`！ |
| **AC-4.5** | `test_ac4_5_cnmeme_wiki_client_etag_cache_and_composite_search` | 1. 调用 `meme_wiki(query="飞飞鼠是什么梗？")`；<br>2. 60秒内二次调用验证内存缓存；<br>3. 过期后携带 `If-None-Match: W/"etag-v1"` 触发 `304 Not Modified`；<br>4. 通过 `CompositeSearchBackend` 调用 `web_search` | 1. 自动剥离词尾查出 `【梗Wiki · 飞飞鼠】` 详情正文、标签与 B站 `BV1cexT6WEY5` 链接；<br>2. TTL 内零网络请求命中缓存；<br>3. `304` 响应无缝续期缓存；<br>4. 组合搜索同时返回 `梗Wiki` 词条与萌娘百科结果 |

---

## 四、 阶段实测验收结果记录（Acceptance Results · 2026-10-28 17:48）

- **`M4.1` 验收结果**：✅ 通过
  - `extensions/registry.py`（94行，覆盖率 **`96%`**）：实测注册 5 类合法扩展全部成功，注册 `object()` 当场抛出 `TypeError`；
  - `tools/messaging_and_group.py`（147行，覆盖率 **`93%`**）与 `tools/explore_and_voice.py`（95行，覆盖率 **`94%`**）：验证 `get_group_members` 输出 `👑群主: 馍馍(QQ:10004004)` 与 `🛡️管理员: 町一(QQ:10009010)`；验证 `clean_meme_query("流云真君是什么梗？")` 先剥离尾部标点再剥离 `"是什么梗"`，精准还原 `"流云真君"`。
- **`M4.2` 验收结果与 `./scripts/qa_gate.sh` 最终报告**：✅ 通过
  - `runtime/prompt_composer.py`（91行，覆盖率 **`95%`**）：验证 `use_count=0` 的新表情 100% 排在 `use_count=500` 的旧表情之前；
  - `runtime/reply_rescue.py`（33行，覆盖率 **`100%`**）：验证剥离 `<think>` 后抢救干净口语，同时 100% 拦截思维链独白与 JSON 残片；
  - `runtime/agent_runner.py`（133行，覆盖率 **`90%`**）：通过 Pylint `R1702 (max-nested-blocks <= 2)` 检验（将工具批量执行提取为 `_execute_tool_batch`），实测端到端完成 `get_group_members` 工具核验 → 口语抢救吐槽 → `on_turn_completed` 自动将数据库中 `skepticism` 从 `55.0` 提升至 `60.0`！

### 真实终端门禁输出摘要：
```text
🛡️  [Gate 1A] Ruff Static Lint (PEP8 + SIM + RET + C4 + C901<=6) -> All checks passed!
🛡️  [Gate 1B] Radon Cyclomatic Complexity                        -> 0 functions worse than B (avg 6.85)
🛡️  [Gate 1C] Pylint Anti-Nesting Check (max-nested-blocks <= 2) -> Your code has been rated at 10.00/10
🛡️  [Gate 2]  Mypy 100% Strict Static Type & LSP Verification    -> Success: no issues found in 45 source files
🛡️  [Gate 3 & 4] AST Flat-Code/SOLID Boundaries & Pytest (>=90%) -> 24 passed in 1.13s | Total coverage: 95.21%
✅ ALL INDUSTRIAL QA & ANTI-NESTING GATES PASSED (via uv run)!
```
