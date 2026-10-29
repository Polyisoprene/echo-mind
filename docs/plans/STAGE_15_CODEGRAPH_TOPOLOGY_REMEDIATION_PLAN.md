# Stage 15 详细工程设计、CodeGraph 全图谱建模与拓扑收敛规范：消除跨层循环依赖、激活孤岛组件与 AST 边界加固
**（Stage 15 Detailed Engineering Specification: CodeGraph Topology Remediation, Cycle Elimination & Orphan Node Integration — Status: ✅ 已验收通过）**

---

## 一、 全局拓扑建模与冲击半径分析（CodeGraph Blast-Radius Modeling）

基于 `.codegraph/codegraph.db`（1,880 节点 / 5,360 边）的静态调用图与跨层导入矩阵分析，我们将审查发现的 7 项拓扑缺陷归纳为三大架构收敛模型，并通过 `codegraph callers` 精确锁定每个符号的调用冲击半径（Blast Radius），确保 **零破坏性升级（Zero Regression）**：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│           Stage 15 CodeGraph 全局拓扑缺陷建模与冲击半径矩阵 (Blast-Radius Model)       │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 模型一 (M15.1)     │ 【缺陷 CG-06】runtime/scheduler.py 导入 adapters/storage/database │
│ 跨层循环依赖解耦   │  而 adapters/onebot/live_client.py 导入 runtime/* 与 mind/facade  │
│ Cycle Elimination  │  形成 runtime <---> adapters 双向包级循环依赖。                   │
│                    │ 【零破坏解耦方案】在 domain/ports.py 定义单方法结构化协议          │
│                    │  IAsyncSqlStore(connect)，scheduler.py 仅依赖 domain/ports；      │
│                    │  live_client.py 改为依赖抽象接口 ICognitiveCoreFacade。            │
│                    │  冲击半径：9 个调用点全兼容（SqliteDatabase 天然满足结构化协议）。 │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 模型二 (M15.2)     │ 【缺陷 CG-01 ~ CG-03】单测全绿但生产入度 prod_callers == 0：      │
│ 孤岛组件并网激活   │  1. PrefixAnchorEngine::resolve (prod_callers=0, test_callers=4)  │
│ Orphan Integration │  2. AsyncEventBus::publish/subscribe/recent_errors (prod=0)       │
│                    │  3. ExtensionRegistry::facets & proposers (prod_callers=0)        │
│                    │ 【零破坏并网方案】                                                │
│                    │  - 在 FailoverLlmGateway 中挂载 PrefixAnchorEngine 追踪前缀锚点； │
│                    │  - 在 EchoMindContainer 与 AgentSessionRunner 中接入 AsyncEventBus│
│                    │    发布/订阅 turn.completed 事件并在 runtime_info 暴露总线健康度；│
│                    │  - 在 AgentSessionRunner 与 CognitiveHeartbeatScheduler 中遍历    │
│                    │    registry.facets 与 registry.proposers。                        │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 模型三 (M15.3)     │ 【缺陷 CG-04, CG-05, CG-07】                                      │
│ 入口收敛与边界固化 │  - bootstrap.py:_build_registry 统一使用 CompositeSearchBackend； │
│ Boundary Hardening │  - MindInspectorService 内部统一使用 self.default_chat_key 属性； │
│                    │  - test_solid_boundaries.py 新增 runtime 严禁导入 adapters 门禁； │
│                    │  - .gitignore 忽略 .codegraph/ 本地索引目录。                     │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 二、 分阶段详细工程设计（Milestone Engineering Specification）

### 里程碑 `M15.1`：消除 `runtime <---> adapters` 循环依赖并升级 AST 架构门禁
1. **`src/echomind/domain/ports.py`**：
   - 新增 `@runtime_checkable class IAsyncSqlStore(Protocol):`（仅含 `def connect(self) -> Any: ...`，共 1 个方法 $\le 5$）；
2. **`src/echomind/runtime/scheduler.py`**：
   - 移除 `from echomind.adapters.storage.database import SqliteDatabase`；
   - 改为导入 `IAsyncSqlStore`（来自 `echomind.domain.ports`），使 `runtime/` 对 `adapters/` 的导入边降为 **`0`**；
3. **`src/echomind/adapters/onebot/live_client.py`**：
   - 将 `from echomind.mind.facade import CognitiveCoreFacade` 替换为 `from echomind.domain.ports import ICognitiveCoreFacade`；
4. **`tests/architecture/test_solid_boundaries.py`**：
   - 新增断言：`runtime/` 层模块严禁导入 `echomind.adapters` 或 `echomind.web`，从 AST 层面永久锁死单向依赖！

---

### 里程碑 `M15.2`：将 `PrefixAnchorEngine`、`AsyncEventBus` 与微内核 `Slot-3 / Slot-4` 接入生产链路
1. **接入 `PrefixAnchorEngine`（`src/echomind/adapters/llm/client.py`）**：
   - `FailoverLlmGateway.__init__` 初始化 `self._anchor = PrefixAnchorEngine()`；
   - 在 `FailoverLlmGateway.complete` 中提取当前会话历史签名并调用 `self._anchor.resolve(chat_key, ...)` 更新会话前缀锚点状态；
2. **接入 `AsyncEventBus`（`src/echomind/core/bootstrap.py`, `runtime/agent_runner.py`, `web/mind_inspector_service.py`）**：
   - `EchoMindContainer.create` 在 `self.event_bus` 上注册 `"turn.completed"` 监听器记录最近完成回合事件；
   - `AgentSessionRunner` 接收可选 `event_bus: AsyncEventBus | None = None`，在 `run_turn` 完成时调用 `await self._event_bus.publish("turn.completed", outcome)`；
   - `MindInspectorService.runtime_info()` 读取 `len(self._c.event_bus.recent_errors)` 暴露 `event_bus_errors` 字段；
3. **接入 `ExtensionRegistry.facets` 与 `proposers`（`src/echomind/runtime/agent_runner.py`, `runtime/scheduler.py`）**：
   - `AgentSessionRunner.run_turn` 遍历 `self._registry.facets`，调用 `facet.render_prompt_line(frame)` 注入扩展认知切面；
   - `CognitiveHeartbeatScheduler.run_heartbeat_cycle` 在内置自主仲裁无提案时，遍历 `self._registry.proposers` 调用 `await proposer.propose(now_ms)`。

---

### 里程碑 `M15.3`：统一注册表复合搜索、消除死属性并更新 `.gitignore`
1. `src/echomind/core/bootstrap.py:_build_registry`：使用 `CompositeSearchBackend((meme_client,))` 包装 `HolyWebSearchTool`；
2. `src/echomind/web/mind_inspector_service.py`：内部 5 处 `self._c.default_chat_key` 统一通过 `self.default_chat_key` 属性访问；
3. `.gitignore`：加入 `.codegraph/`。

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M15.1` ~ `M15.4` CodeGraph 复测拓扑指标与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M15.1`（消除 `runtime <---> adapters` 循环依赖与 AST 门禁加固）**：
    - `codegraph sync` 后复查跨层导入边：`runtime ---> adapters` 导入边由 `2` 降为 **`0`**；
    - `adapters/onebot/live_client.py` 改为依赖抽象接口 `ICognitiveCoreFacade`；
    - `tests/architecture/test_solid_boundaries.py` 新增对 `runtime/` 禁止导入 `echomind.adapters` / `echomind.web` 的 AST 门禁。
  - **`M15.2`（孤岛组件并网激活）**：
    - `PrefixAnchorEngine::resolve` 已并入 `OneBotLiveRuntime._load_context -> _apply_prefix_anchor`（生产入度 `> 0`）；
    - `AsyncEventBus::subscribe / publish / recent_errors` 已并入 `EchoMindContainer.create`、`AgentSessionRunner.run_turn` 与 `MindInspectorService.runtime_info`（生产入度 `> 0`）；
    - `ExtensionRegistry.facets` 与 `proposers` 已并入 `AgentSessionRunner._compose_with_facets` 与 `CognitiveHeartbeatScheduler._poll_custom_proposers`。
  - **`M15.3`（注册表收敛与 `.gitignore` 完善）**：
    - `core/bootstrap.py:_build_registry` 统一采用 `CompositeSearchBackend` 容错包装；
    - `.gitignore` 已忽略 `.codegraph/` 本地索引目录。
  - 全库 63 项测试 100% 通过，总覆盖率 **`90.52% (91%)`**，Pylint **`10.00/10`**，Mypy Strict **85 个源文件 0 错误**。
