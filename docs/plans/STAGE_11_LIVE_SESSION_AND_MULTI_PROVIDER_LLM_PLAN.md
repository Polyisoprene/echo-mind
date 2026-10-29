# Stage 11 详细工程设计、全局建模与架构升级规范：NapCat 在线探测与路由守卫、实时流式会话状态机、多服务商多级故障转移模型中心
**（Stage 11 Detailed Engineering Specification: NapCat Online Telemetry, Real-Time Session Lifecycle & Multi-Provider N-Way Failover LLM Hub — Status: ✅ 已验收通过）**

---

## 一、 全局问题建模与根因溯源（Global Root-Cause Analysis）

针对用户提出的 4 个现象（① 收不到消息；② 感觉群聊发消息发到了别的地方；③ 会话要等完全结束后才显示；④ 模型配置只能配单主单备，不支持多家服务商与多级备用链），经排查容器日志（`docker logs napcat2`）、数据库轨迹与前后端代码，定位出以下架构根因：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               Stage 11 四大核心问题全局架构建模 (Global Root-Cause Model)              │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 问题一 & 四 (M11.1)│ 1. NapCat 容器内 QQ 账号 (10003003) 在 11:19:13 触发腾讯下线通知│
│ 协议掉线盲区与     │    [KickedOffLine]，/get_status 返回 online:false，但控制台顶栏只 │
│ 发信目标错觉       │    探活了 FastAPI，谎报「服务在线」；                             │
│                    │ 2. 11:20:47 QzoneScheduler 定时向私聊发了问候，导致 /api/mind/    │
│                    │    sessions 将 private:10001001 排第一，前端把会话页默认切到了  │
│                    │    私聊，把群聊会话全过滤隐藏了，造成“群聊消息回到了私聊”的错觉； │
│                    │ 3. SendMessageTool 未区分 #消息ID 与 QQ号，模型把 QQ号传进        │
│                    │    reply_to 导致 NapCat 报「回复消息不存在 10001001」。         │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 问题二 (M11.2)     │ 【根因】AgentSessionRunner 仅在整轮所有 LLM/Tool 循环全部跑完后的 │
│ 会话结束后才显示   │  on_turn_completed 中才调用一次 save_turn；运行期间无任何状态落库 │
│                    │ 【方案】引入实时会话生命周期：回合启动即落库 status="running"，每 │
│                    │  完成一步 LLM 或 Tool 立即增量刷新 steps，支持全群/私聊混排时间线 │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 问题三 (M11.3)     │ 【根因】FailoverLlmGateway 与 LlmConfigService 仅支持 2 个固定端  │
│ 多服务商与多级备用 │  点 (primary + 1 fallback)，忽略了 config.json 中的 providers[]   │
│                    │  与 fallbackModels[] 列表                                         │
│                    │ 【方案】升级为 Multi-Provider 注册表 + 有序 N 级备用链 (Ordered   │
│                    │  Fallback Chain)，支持增删多家服务商、挂载任意数量备用模型顺序降级│
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 二、 分步工程设计与实现机理（Milestone Engineering Specification）

### 里程碑 `M11.1`：NapCat 真实在线状态探测、`reply_to / at_user` 智能纠错守卫与全会话混排视图
1. **NapCat 协议端真实在线探测（`src/echomind/web/mind_inspector_service.py`）**：
   - 在 `MindInspectorService.runtime_info()` 中探测 NapCat OneBot HTTP `/get_status` 接口，返回 `qq_online: bool` 与 `qq_status_text: str`（如 `"QQ在线 (10003003)"` 或 `"⚠️ QQ已掉线(KickedOffLine)，请去NapCat重登"`）；
   - 前端顶栏状态灯根据 `qq_online` 真实反映 QQ 协议连接状态，掉线时立刻红灯告警。
2. **`SendMessageTool` 与 `OneBotV11Bridge` 的 `reply_to` 误传 QQ 号自动纠错守卫（`src/echomind/tools/messaging_and_group.py`）**：
   - 在 `SendMessageTool.parameters_schema` 中补充明确描述：`reply_to` 为引用消息的 `#消息ID`（去掉 `#`），`at_user` 为要艾特的群友 `QQ号`；
   - 在 `SendMessageTool.execute` 中增加智能守卫：若模型传入的 `reply_to` 等于某位已知群友/主人的 QQ 号（或不在近期 `chat_messages.mid` 中但存在于 `social_bonds.user_id`），自动将其纠正为 `at_user = reply_to, reply_to = None`，彻底杜绝 `回复消息不存在 10001001`。
3. **「⚡ 轮次会话」支持全会话跨群/私聊统一时间线（`src/echomind/adapters/storage/trace_repo.py` & `app.js`）**：
   - `SqliteTurnTraceStore.list_turns(chat_key="", limit=40)`：当 `chat_key` 为空或 `"all"` 时，直接按 `ORDER BY ts DESC LIMIT ?` 返回所有群聊与私聊的最新轮次会话，绝不因某次私聊主动消息而把群聊会话隐藏！

---

### 里程碑 `M11.2`：会话全生命周期实时流式状态机（`running` → 增量 `steps` → `done / error`）
1. **回合启动即建档 & 逐轮增量更新（`src/echomind/runtime/agent_runner.py`）**：
   - 為 `AgentSessionRunner` 注入可选 `trace_store: ITurnTraceStore | None = None`；
   - **Phase 1（Turn Start）**：在 `build_cognitive_frame` 与 `compose` 完成后、发起第 1 次 LLM 请求前，立即向 `trace_store` 写入 `status="running"` 的初始 `TurnRecord`（包含 `turn_id`、`trigger`、`context_count`、`system_prompt`、`user_prompt`）；
   - **Phase 2（Step-by-Step Progress）**：在 `_run_tool_loop` 中，每完成一轮 LLM 推理或一次工具执行，立即更新 `TurnRecord(status="running", rounds=..., steps=tuple(steps), total_ms=...)`；
   - **Phase 3（Turn Finish / Error）**：回合结束时由 `on_turn_completed` 写入最终 `status="done"`；若发生未预期异常则写入 `status="error"`。
2. **前端「⚡ 轮次会话」实时运行态展示（`src/echomind/web/static/app.js`）**：
   - 当 `turn.status === 'running'` 时，在左侧会话列表与右侧详情头部显示醒目的蓝色脉冲徽标 `<span class="badge accent">⚡ 运行中…</span>`，并实时流式追加已完成的推理轮次与工具步骤！

---

### 里程碑 `M11.3`：多服务商注册表（Multi-Provider）与有序 N 级备用模型链（Ordered Fallback Chain）
1. **`FailoverLlmGateway` 支持任意长度有序故障转移链（`src/echomind/adapters/llm/client.py`）**：
   - 在保持原有 `(primary, fallback)` 构造函数 100% 向下兼容的基础上，新增支持 `chain: tuple[GatewayEndpointConfig, ...]`（`reload_chain(chain: tuple[GatewayEndpointConfig, ...])`）：
   - 请求 `complete()` 时，按顺序遍历 `chain[0] (Primary) -> chain[1] (Fallback #1) -> chain[2] (Fallback #2) -> ...`：一旦当前节点成功立即记录 `is_failover = (idx > 0)` 并返回；若当前节点超时或报错则自动尝试下一节点，直至最后一个节点。
2. **`LlmConfigService` 支持完整 `providers[]` 与 `fallbackModels[]` 管理（`src/echomind/web/llm_config_service.py`）**：
   - `read()` 返回：
     - `providers`: `config.json` 中的全部服务商列表（`id`, `displayName`, `baseURL`, `apiKeyMasked`, `models: list[str]`）；
     - `active`: `{ provider, model, base_url, timeout_ms, temperature }`；
     - `fallbacks`: 有序备用模型列表 `[ { provider, model, base_url, name }, ... ]`；
   - 新增/扩展配置保存接口（兼容原有 `PUT /api/mind/llm` 单主单备字段，同时支持保存完整 `providers` 列表与 `fallback_models` 数组），保存后立即构建完整 `chain: tuple[GatewayEndpointConfig, ...]` 并热切换至运行中的 `FailoverLlmGateway`！
3. **控制台「模型」页升级为「多服务商 + 多级备用链」工作台（`index.html`, `app.js`）**：
   - **卡片一：🎯 当前主模型与推理参数**：下拉选择主服务商（Provider）+ 主模型（Model）+ 温度 + 超时；
   - **卡片二：🛡️ 多级故障转移备用模型链（Ordered Fallback Chain）**：可添加任意多个「服务商 + 模型」作为第 1、第 2、第 N 顺位备用模型，支持上移/下移调整顺位与移除；
   - **卡片三：🏢 大模型服务商管理（Providers Registry）**：可视化展示所有已接入的服务商（如 `WorkBuddy Gateway`、`dsh-ntr 免费网关`、`api.deepseek.com` 等），支持**新增服务商**、编辑服务商地址/密钥/模型列表（逗号或换行分隔）及删除服务商。

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M11.1` ~ `M11.3` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M11.1`（NapCat 在线探测、`reply_to` 防误传 QQ 号守卫与全会话混排）**：
    - `web/mind_inspector_service.py`（覆盖率 **`93%`**）：`/api/mind/runtime` 实时调用 NapCat `get_status` 探测 `online` 状态，QQ 掉线时顶栏红灯告警；
    - `adapters/onebot/bot_bridge.py`（覆盖率 **`95%`**）：`_normalize_reply_and_at` 自动拦截模型误将群友 QQ 号填入 `reply_to` 的情况并转为 `at_user_id`；
    - `adapters/storage/trace_repo.py`（覆盖率 **`100%`**）：`list_turns(chat_key="")` 返回跨群聊/私聊的统一时间线，彻底消除主动私聊导致群聊会话被隐藏的错觉。
  - **`M11.2`（会话全生命周期实时流式状态机 `running -> steps -> done`）**：
    - `runtime/agent_runner.py`（覆盖率 **`87%`**）：回合启动即落库 `status="running"`，每完成一步 LLM 推理或工具调用立即增量刷新 `steps`，前端「⚡ 轮次会话」实时展示蓝色 `⚡ 运行中…` 徽标与流式步骤。
  - **`M11.3`（多服务商注册表与有序 N 级备用模型故障转移链）**：
    - `core/config.py`（覆盖率 **`94%`**）、`adapters/llm/client.py`（覆盖率 **`88%`**）、`web/llm_config_service.py`（覆盖率 **`94%`**）：支持管理多家服务商（Providers Registry）与任意长度的有序备用模型链（`fallback_chain`），主模型失败时按顺位依次自动降级。
  - 全库 60 项测试 100% 通过，总覆盖率 **`92.43% (92%)`**，Pylint **`10.00/10`**，Mypy Strict **84 个源文件 0 错误**。
