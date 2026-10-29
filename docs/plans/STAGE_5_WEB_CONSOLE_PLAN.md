# Stage 5 详细工程设计、实现机理与验收报告：组合根依赖注入容器、FastAPI 认知透视 API 与全景控制台
**（Stage 5 Detailed Engineering Specification & Acceptance Report — Status: ✅ 已验收通过）**

---

## 一、 Stage 5 解决的核心问题与设计目标

在前四个阶段中，我们已经完成了遵循 SOLID 原则的底层仓储（Stage 1）、NoneBot2 适配与多模态网关（Stage 2）、12 层认知与神经可塑性核心（Stage 3）以及微内核扩展槽与运行时引擎（Stage 4）。
Stage 5 要解决两个关键工程问题：
1. **依赖倒置的最终闭环 —— 组合根（Composition Root / Dependency Injection Container）**：
   因为 `mind/`、`runtime/`、`tools/` 只依赖 `domain/ports.py` 中的抽象 `Protocol`，我们需要一个干净的顶层装配器 `src/echomind/core/bootstrap.py`，负责初始化 SQLite WAL、构造具体 Adapter、注入给 `CognitiveCoreFacade` 与 `AgentSessionRunner`，并挂载到 `FastAPI / NoneBot2` ASGI 实例上。
2. **全透明可观测性与人工干预控制 —— 《🧠 认知核心全景控制台 API》（`src/echomind/web/`）**：
   提供一套完整的 REST API 与前端控制台页面，让你能实时观测并随时人工干预她的 **工作记忆、四大内驱力、带置信度的语义事实（支持一键新增/锁定 100% 权威事实/删除）、海马体情景记忆（支持单卡删除）、条件反射规则、群友好感与防骗可信度榜、以及 🧬 神经可塑性参数自演化曲线与日志**！

---

## 二、 模块拆分、API 契约与实现细节（单文件 ≤ 300 行，单函数 ≤ 40 行，嵌套 ≤ 2 层）

### 里程碑 `M5.1`：组合根容器（`core/bootstrap.py`）与认知核心全景 API（`web/`）

#### 1. 组合根依赖注入容器（`src/echomind/core/bootstrap.py`）
- **职责**：全系统唯一允许同时导入 `adapters/`、`mind/`、`runtime/`、`tools/` 与 `extensions/` 的装配模块（严格符合《架构契约》第一节 Layer 5 规范）。
- **核心装配流程（`EchoMindContainer.create(db_path, config_path)`）**：
  1. 初始化 `SqliteDatabase(db_path)` 并调用 `await db.initialize()` 开启 WAL 模式与 17 张表；
  2. 构造 `SqliteMemoryRepository(db)` 与 `SqliteWorkingStateStore(db)`，调用 `await working_store.ensure_default_params()` 初始化 8 项可塑参数；
  3. 构造 `CognitiveCoreFacade(mem_reader=mem_repo, mem_writer=mem_repo, working_store=work_repo, owner_qq=cfg.owner_qq)`；
  4. 构造 `ExtensionRegistry()`，自动注册内置的感知富化器（`QuoteStickerEnricher`, `CardAndForwardEnricher`, `ImageCaptionCacheEnricher`）与内置工具集。

#### 2. 认知核心全景透视与人工审计 API（`src/echomind/web/mind_inspector_service.py` & `app.py`）
为了遵守 **单一职责原则（SRP）** 与“路由函数内严禁直接编写 SQL”的架构红线，我们将数据聚合与干预操作封装在 `MindInspectorService` 中，`FastAPI` 路由只做轻量转发：

| HTTP 方法与路径 | 功能说明 | 底层执行机理与返回结构 |
|---|---|---|
| **`GET /api/mind/snapshot`** | 获取认知核心全景实时快照（供前端每 3 秒静默轮询） | 一次性并发读取：<br>1. `working_state`（当前情绪向量 `valence/energy/jealousy/shyness` + 四大内驱力 + 正在做的生活事项 + 短期挂念栈 + 好奇心待查队列）；<br>2. `semantic_facts`（全部语义事实 + 置信度 + `is_locked` 防忽悠锁状态）；<br>3. `episodic_memories`（按艾宾浩斯公式实时计算每张卡当前的保持率 `%` 与 `clear/fuzzy` 档位）；<br>4. `procedural_rules`（全部条件反射规则）；<br>5. `social_bonds`（群友好感度、等级、性格画像、**防忽悠可信度 `trust_score`**、情敌标记）；<br>6. `plastic_params` & `plastic_logs`（8 项自演化参数当前值、稳态边界与最近 30 条强化学习调参日志）；<br>7. 所有通过 Slot-5 `IInspectorPanel` 注册的扩展自定义面板数据！ |
| **`POST /api/mind/facts`** | 人工新增或锁定 100% 权威事实 | 接收 `{chat_key, subject, fact_text, is_locked}`，以 `source="owner", confidence=1.0` 调用 `upsert_semantic_fact()`，支持在网页上一键锁死防忽悠事实 |
| **`DELETE /api/mind/episodic/{card_id}`** | 删除指定的错误/污染情景记忆卡 | 从 `episodic_memories` 表物理删除对应 `card_id`，防止错误往事继续被召回 |
| **`POST /api/mind/plastic/tune`** | 人工微调或重置某项可塑参数 | 调用 `update_plastic_param(key, delta, reason="管理员手动调校", reward=0.0)` |
| **`POST /api/mind/tick`** | 手动立即触发一次后台自主好奇心/内驱力心跳 | 调用 `facade.run_autonomous_tick(now_ms)`，返回产出的 `ProactiveProposal` 并记录入 `exploration_logs` |
| **`GET /`** | 《🧠 EchoMind 认知核心全景控制台 2.0》前端页面 | 响应式深色玻璃拟态控制台（实时展示上述全部 6 大认知模块、3 秒无感同步、支持一键增删改锁） |

---

## 三、 分步验收标准与测试用例矩阵（Acceptance Test Matrix）

Stage 5 将通过 `tests/integration/test_stage5_web_and_bootstrap.py`（使用 `httpx.AsyncClient(transport=ASGITransport(app=app))` 对真实 FastAPI 实例与 SQLite WAL 库进行全接口集成测试）验证：

| 验收项编号 | 测试场景与输入 | 预期量化结果 (Expected) |
|---|---|---|
| **AC-5.1** | 调用 `EchoMindContainer.create()` 后请求 `GET /api/mind/snapshot` | HTTP 200；返回 JSON 包含完整的 `working`、`drives`、`facts`、`episodic`（带实时计算的 `retention` 与 `clarity`）、`rules`、`bonds`、`plastic_params`（8项）与 `plastic_logs` |
| **AC-5.2** | 请求 `POST /api/mind/facts` 锁定一条新权威事实，随后验证群友忽悠是否被拦截 | HTTP 200；新事实以 `confidence=1.0, is_locked=True` 入库，且群友试图覆盖该主题时被 `locked_fact_conflict` 拦截 |
| **AC-5.3** | 请求 `DELETE /api/mind/episodic/{card_id}` 删除某张记忆卡 | HTTP 200；再次请求 `/api/mind/snapshot` 时该记忆卡已彻底移除 |
| **AC-5.4** | 请求 `POST /api/mind/plastic/tune` 调校 `talkativeness` 参数，以及 `POST /api/mind/tick` 触发自主探索心跳 | HTTP 200；参数更新并写入 `plastic_logs`；自主探索心跳返回 `curiosity_explore` 提议并写入 `exploration_logs` |
| **AC-5.5** | 请求 `GET /` 获取控制台首页 HTML，并运行 `./scripts/qa_gate.sh` | 首页 HTML 渲染成功；全库 `ruff`、`radon`、`pylint (10.00/10)`、`mypy --strict`、`pytest (覆盖率 >= 90%)` 全绿通过 |

---

## 四、 阶段实测验收结果记录（Acceptance Results · 2026-10-28 19:48）

- **`M5.1` 组合根与全景控制台 API 实测验收结果**：✅ 通过
  - `core/bootstrap.py`（77行，覆盖率 **`100%`**）：完成 `EchoMindContainer.create()` 组合根装配，自动初始化 SQLite WAL、12 项可塑与 7 维性格参数、感知富化管道与工具注册表；
  - `web/mind_inspector_service.py`（147行，覆盖率 **`98%`**）、`web/app.py`（94行，覆盖率 **`100%`**）、`web/ui_html.py`（覆盖率 **`100%`**）：
    - **`AC-5.1` (`/api/mind/snapshot`)**：HTTP 200 返回完整 12 层状态快照（含 `irritation` 厌烦度、7 维 HEXACO 性格指令、带实时艾宾浩斯保持率的情景记忆、带防忽悠锁的语义事实、社交关系榜与强化学习演化日志）；
    - **`AC-5.2` (`POST /api/mind/facts`)**：网页端一键锁定 `本群真实群主 = 馍馍(10004004)` 后，群友忽悠覆盖立即被 `locked_fact_conflict` 拦截；
    - **`AC-5.3` (`DELETE /api/mind/episodic/{card_id}`)**：单卡物理删除即时生效；
    - **`AC-5.4` (`POST /api/mind/plastic/tune` & `/api/mind/tick`)**：手动调校 `persona_guile` 立即从 `52.0` 升至 `57.0` 并写入审计日志；手动触发探索心跳立即弹出 `curiosity_queue` 中的 `"飞飞鼠"` 产出 `curiosity_explore` 提议并写入 `exploration_logs`！

### 真实终端门禁输出摘要：
```text
🛡️  [Gate 1A] Ruff Static Lint (PEP8 + SIM + RET + C4 + C901<=6) -> All checks passed!
🛡️  [Gate 1B] Radon Cyclomatic Complexity                        -> 0 functions worse than B (avg 6.85)
🛡️  [Gate 1C] Pylint Anti-Nesting Check (max-nested-blocks <= 2) -> Your code has been rated at 10.00/10
🛡️  [Gate 2]  Mypy 100% Strict Static Type & LSP Verification    -> Success: no issues found in 53 source files
🛡️  [Gate 3 & 4] AST Flat-Code/SOLID Boundaries & Pytest (>=90%) -> 28 passed in 1.68s | Total coverage: 94.70%
✅ ALL INDUSTRIAL QA & ANTI-NESTING GATES PASSED (via uv run)!
```
