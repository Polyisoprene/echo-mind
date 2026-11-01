# EchoMind 工程架构契约、SOLID 边界与质量门禁宪法
**（Architecture Contracts & Engineering Constraints Specification v1.0）**

> **效力声明**：本文档是 `EchoMind` 项目的最高工程契约。库内所有模块、扩展与测试代码均须严格遵守本文档定义的接口契约与架构约束。本文档中的每一条硬性约束均对应 `tests/architecture/test_solid_boundaries.py`、`mypy --strict` 与 `ruff` 中的自动化门禁断言，任何违反契约的代码均无法通过 `./scripts/qa_gate.sh`。

---

## 一、 分层架构边界与单向依赖矩阵（Hexagonal Layer Boundaries）

系统采用六边形整洁架构（Hexagonal Clean Architecture），代码树划分为以下 7 个顶层包，**依赖方向严格由外向内（基础设施依赖领域核心，领域核心零外部依赖）**：

| 包路径 (`src/echomind/`) | 架构层级 | 核心职责 | 允许依赖的内部包 | **严禁导入的黑名单（AST 门禁拦截）** |
|---|---|---|---|---|
| **`domain/`** | Layer 0 · 领域契约层 | 不可变领域值对象 (`models.py`) 与隔离抽象端口 (`ports.py`) | 仅 Python 标准库与 `pydantic` | 严禁导入任何其它 `echomind.*` 包、严禁导入 `aiosqlite / httpx / nonebot / fastapi` |
| **`mind/`** | Layer 1 · 认知核心层 | 12层认知逻辑（注意路由、工作记忆、五维记忆、防忽悠校准、内驱力、海马体、神经可塑性） | 仅 `domain/` | **严禁导入 `adapters/`、`web/`、`tools/`、`aiosqlite`、`httpx`、`nonebot`、`fastapi`** |
| **`runtime/`** | Layer 2 · 会话运行时层 | 会话并发调度、Agent 工具循环、Prompt 装配器 | `domain/` | **严禁导入 `mind/` 内部私有实现（只能调 `ICognitiveCoreFacade`）、严禁导入 `aiosqlite`、`nonebot`** |
| **`tools/`** | Layer 3 · 效应器工具层 | 无状态工具实现（发消息、查群员、看图/视频、搜索、B站、语音/翻唱） | `domain/` | 严禁直接修改 `mind/` 内部状态、严禁私自启动后台定时器 |
| **`extensions/`** | Layer 3 · 微内核扩展槽 | 未来新增的感官、工具、认知维度、主动提议与监控面板 | `domain/` | **严禁调用 `asyncio.create_task` 私起常驻循环、严禁跨扩展直接互相 import** |
| **`adapters/`** | Layer 4 · 基础设施适配层 | `NoneBot2 (OneBot v11)` 桥接器、`SQLite WAL` 仓储实现、多网关 `LLM` 客户端 | `domain/`, `core/` | 严禁包含任何业务人设或情绪推理逻辑 |
| **`web/` & `core/`** | Layer 5 · 表现与组合根层 | FastAPI 路由、SSE 推送、依赖注入装配 (`bootstrap.py`) | 全部包（作为 Composition Root 组合根） | 路由函数内严禁直接编写 SQL 或复杂业务逻辑 |

---

## 二、 六大设计原则（SOLID + 迪米特法则）代码级硬性约束

### 1. 单一职责原则（SRP — Single Responsibility Principle）
- **[SRP-01] 文件体积上限**：任何 `.py` 源码文件总行数 **不得超过 300 行**（含注释与空行）。
- **[SRP-02] 函数圈复杂度上限**：任何函数/方法的 McCabe 圈复杂度 **不得超过 10**（由 `ruff C901` 强制拦截）。
- **[SRP-03] 职责正交切分**：
  - 数学策略计算（如艾宾浩斯遗忘计算、显著性打分、参数边界裁剪）必须为**纯函数或无状态策略类（Pure Strategy）**，严禁混入 I/O 操作；
  - 状态持久化必须全部收归 `adapters/storage/` 下的 Repository 实现类。

### 2. 开闭原则（OCP — Open/Closed Principle）
- **[OCP-01] 扩展零修改内核**：新增感官预处理、新增工具、新增内心状态维度、新增主动说话规则、新增后台监控卡片，必须通过 `domain/ports.py` 定义的 **5 大标准扩展接口** 挂载，严禁在 `mind/` 或 `runtime/` 中写死针对特定扩展的 `if/elif` 分支。

### 3. 里氏替换原则（LSP — Liskov Substitution Principle）
- **[LSP-01] 契约完全等价**：所有实现同一 `Protocol` 的具体类（例如 `SqliteMemoryRepo` 与 `InMemoryRepo`、`FailoverLlmGateway` 与 `MockLlmGateway`），其方法签名、前置条件、后置条件必须 100% 满足 `mypy --strict` 静态协变/逆变检查。
- **[LSP-02] 异常边界契约**：Port 接口实现方法禁止向外泄漏底层库私有异常（如 `aiosqlite.OperationalError` 或 `httpx.ConnectError`），必须捕获并转化为领域层定义的标准结果或 `DomainError`。

### 4. 接口隔离原则（ISP — Interface Segregation Principle）
- **[ISP-01] 禁止胖接口与万能上下文**：严禁向函数传递包含无关组件的万能 `ctx: dict[str, Any]`。
- **[ISP-02] 读写职责与角色分离（CQRS-lite Role Interfaces）**：
  - 单个 Port `Protocol` 定义的方法数 **不得超过 5 个**；
  - 记忆读取端只注入 `IMemoryReader`（只读），记忆巩固端才注入 `IMemoryWriter`；
  - 消息发送只注入 `IMessageSender`，群成员查询只注入 `IGroupRosterReader`。

### 5. 依赖倒置原则（DIP — Dependency Inversion Principle）
- **[DIP-01] 面向抽象编程**：`mind/`、`runtime/`、`tools/`、`extensions/` 中的所有类构造函数（`__init__`），其外部依赖参数类型声明**必须全部为 `echomind.domain.ports` 中的 `Protocol` 抽象接口**，严禁声明为具体实现类。

### 6. 迪米特法则（LoD — Law of Demeter / 最少知识原则）
- **[LoD-01] 门面隔离（Facade Isolation）**：`runtime/` 层与认知核心交互时，**只允许调用 `ICognitiveCoreFacade` 门面的 4 个顶层方法**，严禁绕过门面直接访问内部的子存储或计算器。
- **[LoD-02] 不可变数据传输对象（Frozen Value Objects）**：`echomind/domain/models.py` 中定义的所有跨层传递模型，**必须声明 `model_config = ConfigDict(frozen=True, extra="forbid")`**，所有集合字段必须使用不可变 `tuple[T, ...]` 而非可变 `list[T]`，从语言层面禁止任何中间环节私自篡改共享对象。

### 7. 扁平化整洁代码与反嵌套四原则（Flat Code & Anti-Nesting Standards）
为了消灭“箭头型代码（Arrow Anti-Pattern）”与深层缩进，全库强制执行以下 4 条编码铁律，并由 `Ruff (SIM/RET/C4/PLR)`、`Pylint (max-nested-blocks=2)`、`Radon (Grade A)` 与 `AST 嵌套深度检测器` 实时强制拦截：

1. **[FLAT-01] 卫语句优先（Guard Clauses First）**：
   - 函数入口处必须优先处理空值、边界条件与异常分支并尽早 `return` / `raise`，循环内部优先使用 `if not valid: continue`，确保主干业务逻辑始终处于函数最左侧（第 1 层缩进）。
   - **禁止**在 `return` 或 `raise` 之后写冗余的 `else:` / `elif:` 分支（由 `Ruff RET505/RET506` 强制拦截）。
2. **[FLAT-02] 反转条件消除包裹（Invert Conditions）**：
   - 严禁使用 `if condition:` 包裹整个函数体或循环体；必须反转条件写为 `if not condition: return`（由 `Ruff SIM` 规则集与 AST 检查器强制保障）。
3. **[FLAT-03] 提取语义化小函数（Extract Function · 最大控制流嵌套深度 ≤ 2）**：
   - 任何函数内部的控制流块（`if / for / while / try / with`）**最大嵌套深度严格限制为 `≤ 2 层`**（比标准 `max_depth: 3` 更严苛！）。
   - 一旦循环内部包含复杂分支或子循环，必须将其提取为独立命名的私有辅助函数（如 `_ parse_single_card()`），且单个函数总行数不得超过 `40 行`。
   - **禁止深层嵌套函数调用**（如 `f(g(h(k(x))))`，函数调用嵌套深度 `≤ 3`，由 AST 调用深度检查器强制拦截）。
4. **[FLAT-04] 善用单行推导式（Comprehensions over Loops）**：
   - 对于简单的列表、字典、集合映射与过滤，必须优先使用推导式（List/Dict/Set Comprehension）或生成器表达式替代显式的 `for + append` 循环（由 `Ruff C4` `flake8-comprehensions` 强制检查）；若转换逻辑超过一行，则提取为独立小函数后在推导式中调用。

---

## 三、 核心领域不可变值对象契约（`echomind/domain/models.py`）

所有跨层传递的数据结构均定义为 `frozen=True` 的 Pydantic 强类型值对象：

### 1. 感知与注意路由值对象
- **`MediaAttachment`**：`kind ('image'|'gif_storyboard'|'video_frames'|'voice'|'forward')`, `url: str`, `local_path: str`, `data_url: str`, `description: str`, `message_id: str`
- **`Percept`（标准感知帧）**：
  - `chat_key: str`（格式：`group:<id>` 或 `private:<id>`）
  - `scene: Literal["group", "private"]`
  - `message_id: str`, `timestamp_ms: int`
  - `sender_id: str`, `sender_name: str`, `sender_role: Literal["owner", "admin", "member", "self"]`
  - `text: str`（已关联引用描述与语音转写后的标准化文本）
  - `is_at_me: bool`, `is_called_by_name: bool`, `is_quoted_me: bool`, `is_poke_me: bool`
  - `quoted_message_id: str`, `quoted_text: str`
  - `media: tuple[MediaAttachment, ...]`
- **`AttentionDecision`（注意路由决策）**：
  - `should_wake: bool`
  - `salience_score: float`（约束范围 `0.0 ~ 1.0`）
  - `tier: int`（`0=忽略, 1=直接召唤必回, 2=焦点/挂念唤醒, 3=好奇/上下文插话, 4=主动内驱唤醒`）
  - `reason: str`
  - `detected_unknown_terms: tuple[str, ...]`（触发好奇心求知的未知新词）
  - `has_unseen_media: bool`（是否包含值得主动调工具查看的图片/视频）

### 2. 前额叶工作记忆、内驱力与心智理论值对象
- **`AffectiveVector`（连续情绪向量）**：
  - `valence: float` (`-100.0 ~ 100.0`, 愉悦度)
  - `energy: float` (`0.0 ~ 100.0`, 精力值)
  - `jealousy: float` (`0.0 ~ 100.0`, 吃醋/酸意值)
  - `shyness: float` (`0.0 ~ 100.0`, 害羞/别扭值)
- **`DriveState`（四大内驱力向量）**：
  - `curiosity: float` (`0.0 ~ 100.0`, 好奇求知欲)
  - `attachment: float` (`0.0 ~ 100.0`, 对在意之人的依恋/独占渴望，由关系深度驱动而非固定对象)
  - `jealousy_drive: float` (`0.0 ~ 100.0`, 吃醋发作冲动)
  - `social_expression: float` (`0.0 ~ 100.0`, 群聊社交表达欲)
- **`IntentionItem`（短期挂念栈条目）**：
  - `summary: str`, `created_at_ms: int`, `expires_at_ms: int`, `target_user_id: str`
- **`TheoryOfMindFrame`（心智理论推断）**：
  - `target_user_id: str`, `inferred_mood: str`, `inferred_intent: str`, `is_teasing_or_baiting: bool`

### 3. 五维长期记忆与神经可塑性值对象
- **`EpisodicCard`（海马体情景记忆卡）**：
  - `card_id: int`, `chat_key: str`, `timestamp_ms: int`, `msg_seq: int`
  - `summary: str`（完整前因后果总结，20~100字）
  - `key_detail: str`（不可丢失的数字/QQ号/暗号/进度锚点）
  - `participants: tuple[str, ...]`
  - `importance: float` (`1.0 ~ 5.0`), `pinned: bool`, `rehearsals: int`, `last_recalled_ms: int`
- **`RecalledMemoryItem`（带实时艾宾浩斯保持率与清晰度的召回项）**：
  - `card: EpisodicCard`, `retention: float` (`0.0 ~ 1.0`), `clarity: Literal["clear", "fuzzy"]`
- **`SemanticFact`（语义事实与元认知置信度条目）**：
  - `fact_id: int`, `chat_key: str`, `subject: str`, `fact_text: str`
  - `confidence: float` (`0.0 ~ 1.0`), `is_locked: bool`
  - `source: Literal["system", "owner", "explored", "peer"]`
  - `revision_count: int`
- **`ProceduralRule`（程序性条件反射默契）**：
  - `rule_id: int`, `chat_key: str`, `trigger_keyword: str`, `trigger_user_id: str`
  - `action_instruction: str`, `strength: int` (`1 ~ 10`)
- **`SocialBondProfile`（群友好感、画像与防骗可信度档案）**：
  - `chat_key: str`, `user_id: str`, `user_name: str`, `group_role: Literal["owner", "admin", "member"]`
  - `affinity_score: float`, `affinity_level: int` (`0 ~ 5`), `msg_count: int`
  - `trust_score: float` (`0.0 ~ 1.0`, 元认知防忽悠可信度)
  - `is_rival: bool`, `rival_reason: str`, `traits: tuple[str, ...]`
- **`PlasticParamSpec`（可自演化神经可塑性参数）**：
  - `key: str`, `value: float`, `min_bound: float`, `max_bound: float`, `description: str`

### 4. 认知核心输出与回合结算值对象
- **`CognitiveFrame`（注入给 Runtime 的唯一不可变认知状态帧）**：
  - `chat_key: str`, `scene: Literal["group", "private"]`, `Must_reply: bool`
  - `affect: AffectiveVector`, `drives: DriveState`
  - `rendered_mind_block: str`（统一排版好的《🧠 {bot_name}此刻的认知与内心状态》文本块）
  - `epistemic_warnings: tuple[str, ...]`（元认知防忽悠警报）
  - `curiosity_prompts: tuple[str, ...]`（主动调工具看视频/搜新词的引导）
- **`TurnOutcome`（单轮对话结束后的反馈载荷）**：
  - `session_id: str`, `chat_key: str`, `triggers: tuple[Percept, ...]`, `sent_texts: tuple[str, ...]`
  - `tools_used: tuple[str, ...]`, `social_reward: float` (`-1.0 ~ 1.0`), `epistemic_conflict_detected: bool`

---

## 四、 隔离端口契约规范（`echomind/domain/ports.py` · ISP & DIP）

所有跨层依赖均通过以下窄接口（每个接口 `<= 5` 个方法）进行解耦：

1. **`IMemoryReader`（只读记忆检索端口）**：
   - `get_episodic_cards(chat_key: str) -> tuple[EpisodicCard, ...]`
   - `get_semantic_facts(chat_key: str, min_confidence: float = 0.0) -> tuple[SemanticFact, ...]`
   - `get_procedural_rules(chat_key: str) -> tuple[ProceduralRule, ...]`
   - `get_social_bond(chat_key: str, user_id: str) -> SocialBondProfile | None`
2. **`IMemoryWriter`（记忆巩固与更新端口）**：
   - `save_episodic_card(card: EpisodicCard) -> int`
   - `reinforce_episodic_card(card_id: int, recalled_ms: int) -> None`
   - `upsert_semantic_fact(fact: SemanticFact) -> tuple[bool, str]`（若撞上 `is_locked=True` 的权威事实则拒绝覆写并返回冲突原因！）
   - `upsert_procedural_rule(rule: ProceduralRule) -> int`
   - `upsert_social_bond(bond: SocialBondProfile) -> None`
3. **`IWorkingStateStore`（工作记忆与可塑参数端口）**：
   - `load_working_state(scope_key: str) -> tuple[AffectiveVector, DriveState, str, tuple[IntentionItem, ...], tuple[str, ...]]`
   - `save_working_state(...) -> None`
   - `get_plastic_params() -> dict[str, PlasticParamSpec]`
   - `update_plastic_param(key: str, delta: float, reason: str, reward: float) -> PlasticParamSpec`
4. **`IMessageSender`（发信效应器端口）**：
   - `send_text(chat_key: str, messages: tuple[str, ...], reply_to_mid: str | None = None, at_user_id: str | None = None) -> tuple[str, ...]`
   - `send_sticker(chat_key: str, sticker_id: str, reply_to_mid: str | None = None) -> str | None`
   - `send_voice(chat_key: str, audio_b64: str, summary_text: str) -> str | None`
   - `send_poke(chat_key: str, target_user_id: str) -> bool`
5. **`IGroupRosterReader`（群组织架构权威查询端口）**：
   - `get_group_members(group_id: str) -> tuple[SocialBondProfile, ...]`
6. **`ILlmGateway`（大模型推理端口）**：
   - `complete(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, temperature: float = 0.6, max_tokens: int = 800, thinking_off: bool = False) -> dict[str, Any]`
7. **`ICognitiveCoreFacade`（认知核心对 Runtime 暴露的唯一门面 · 迪米特法则）**：
   - `evaluate_incoming(percept: Percept) -> AttentionDecision`
   - `build_cognitive_frame(chat_key: str, triggers: tuple[Percept, ...]) -> CognitiveFrame`
   - `on_turn_completed(outcome: TurnOutcome) -> None`
   - `run_autonomous_tick(now_ms: int) -> ProactiveProposal | None`

---

## 五、 微内核五大强类型扩展槽契约（5 Extension Slots）

任何位于 `src/echomind/extensions/` 下的扩展模块，只能通过实现以下 5 个 `Protocol` 之一与系统交互：

1. **`IPerceptEnricher`（感官输入富化槽）**：`enrich(percept: Percept) -> Percept`
2. **`IToolExtension`（无状态手脚工具槽）**：`name: str`, `description: str`, `parameters_schema() -> dict[str, Any]`, `execute(chat_key: str, args: dict[str, Any]) -> str`
3. **`ICognitiveFacet`（内心状态维度槽）**：`facet_id: str`, `render_prompt_line(chat_key: str) -> str`
4. **`IProactiveProposer`（主动意图提议槽）**：`propose(chat_key: str, affect: AffectiveVector, drives: DriveState) -> ProactiveProposal | None`（**严禁扩展自行建立后台定时器，统一由内核仲裁器调度**）
5. **`IInspectorPanel`（后台透视面板声明槽）**：`panel_id: str`, `panel_title: str`, `build_panel_data() -> dict[str, Any]`

---

## 六、 七道工业级自动化质量门禁（`./scripts/qa_gate.sh`）

每次提交或阶段准出，必须通过以下 7 项自动化检查（全部 Exit Code = 0）：

1. **Gate 1 (`ruff check & format` + `radon cc` + `pylint nesting`)**：
   - `Ruff`：开启 `E/F/W/I/B/UP/ASYNC/C901/S` 及 **`SIM`（条件反转简化）、`RET`（卫语句返回检查）、`C4`（推导式优化）、`PLR`（重构规范）**，0 Warning；
   - `Radon`：`radon cc src -a -nb`，强制全库所有函数圈复杂度评级达到 **A 级（平均与单函数圈复杂度 `≤ 5`）**；
   - `Pylint`：开启 `R1702 (too-many-nested-blocks)` 且配置 **`max-nested-blocks = 2`**，强制拦截任何超过 2 层嵌套的代码块。
2. **Gate 2 (`mypy --strict`)**：全库 `src/` 与 `tests/` 100% 通过严格静态类型检查。
3. **Gate 3 (`pytest tests/architecture/test_solid_boundaries.py`)**：
   - AST 扫描验证分层依赖矩阵（`domain/` 与 `mind/` 零基础设施导入）；
   - 验证单文件行数 `<= 300` 行、单函数行数 `<= 40` 行；
   - **AST 扁平化与反嵌套硬断言**：验证全库所有函数控制流最大嵌套深度 `<= 2 层`（强制使用卫语句与提取函数），验证链式/嵌套函数调用深度不过深；
   - 验证所有 `domain/models.py` 值对象均为 `frozen=True`；
   - 验证所有 `domain/ports.py` 接口均为 `Protocol` 且每个接口方法数 `<= 5`。
4. **Gate 4 (`pytest --cov=src/echomind --cov-fail-under=90`)**：单元与集成测试全绿，核心代码覆盖率 `>= 90%`。
5. **Gate 5 (`hypothesis` 属性基模糊测试)**：随机生成极端时间戳、越界参数与并发事件，验证数学不变量（保持率 `0~1`、可塑参数不越界、置信度锁不可篡改）。
6. **Gate 6 (数据迁移完整性对账)**：源数据与 SQLite WAL 库逐项对账 100% 一致且幂等。
7. **Gate 7 (并发与故障注入韧性)**：高并发读写零锁冲突，网关异常 100% 优雅降级。

---

## 七、 流程性补充契约（红绿交付与 A/B 双线）

自 `Stage 28` 起，所有**修复类**改动除满足本文档第一~六节外，还必须遵守
[`CONTRACT_RED_GREEN_AND_AB_LANES.md`](CONTRACT_RED_GREEN_AND_AB_LANES.md) 规定的
**RGR-01 ~ RGR-10（红绿交付）** 与 **AB-01 ~ AB-08（A/B 双线隔离）**：

- 任何行为变更必须先有「因目标缺陷而失败」的红测试与红证据（RGR-01/02）；
- 契约测试必须走生产同一条调用路径，禁止用显式注入绕过生产缺口（RGR-06）；
- 修复只在 A 线（`lane/a-stage<N>` + 只读快照库 + 录制探针）进行，全绿且回放达标后方可准出至 B 线 `main`（AB-03/04/05）。


---

## 八、 人格模型契约（Stage 30 · 7D Persona Contract）

| 契约 | 内容 | 守护测试 |
|---|---|---|
| **默认值单一源** | 7 维默认值与边界只能定义在 `domain/persona_specs.py`；禁止在消费者里写字面量 | `tests/architecture/test_persona_single_source.py`（含 AST 守卫） |
| **叙事连续** | 依恋腔调 = 四象限原型（安全/痴迷/疏离/恐惧）softmax 加权 top-2；禁止硬阈值分支 | `test_personality_invariants.py::test_i3*` |
| **动力学有界（E2 两层模型）** | 慢层（特质基线）：日推 ≤0.0133、年净变化 ≤4、最大偏离 12、回归 0.00111/天（半衰期≈624 天）；快层（状态）：单步 ≤4、幅度 ≤10、半衰期 45 分钟。跨层约束：`X = M(1−e^(−365D/M))`、`r = D/M` | `test_persona_two_layers.py`、`test_persona_dynamics_wiring.py` |
| **关系姿态** | `θ_eff = clamp(θ + 8·W·σ_u)`，只影响渲染与显著性，**不得写回** `plastic_params` | `test_persona_stance.py` |
| **词条作用域** | `chat_key`/`source` 溯源；类别上限 habit 8 / taste 4 / temperament 4 / taboo 3；负性只削弱 taboo/temperament | `test_trait_scope_and_caps.py` |
| **探针一致** | 潜意识 prompt 必须携带一行人格摘要 | `test_probe_persona_summary.py` |
| **参数溯源** | 新增常数必须标 `src:` / `convention:` / `fit:`；未拟合的标 `fit:pending` | `test_param_provenance.py` |

### 八·一 Stage 41 人格/记忆增补契约（2026-11-01）

以 [CURRENT_STATE_2026-11-01.md](CURRENT_STATE_2026-11-01.md) 为当前事实源。

| 契约 | 内容 | 守护测试 |
|---|---|---|
| **证据可审计** | active trait 必须有真实 `TraitEvidence`（quote/context/polarity），不能只有计数 | `test_trait_evidence_ledger.py` |
| **active-only** | prompt 只渲染 `status='active'`；candidate/retired/legacy 不进入人格 | `test_personality_invariants.py::test_only_active_traits_reach_the_prompt` |
| **生命周期** | `Beta(1+s,1+c)`；至少 2 个独立 context 才 active；反证可 retired；dormant 暂未实现 | `test_trait_lifecycle.py` |
| **trait→记忆** | support link 只对 active trait 生效；默认 presence-only；必须经 `BM25>0` 词法门控 | `test_live_trait_retrieval.py`、`ranker_fusion.py` 单测 |
| **action eligibility** | 默认 additive：只追加工具；whitelist 可选；active taboo 只授予拒绝许可，不强制拒绝 | `test_trait_tool_grants.py` |
| **隐私** | support/知识/披露一律在 private/secret 硬门之后；turn-context 不能冒充 support | `test_trait_memory_privacy.py`、`test_claim_read_path.py` |
| **B4 claims** | `FACTS_V2` 读路径带 provenance/privacy；默认仍 off | `test_claim_read_path.py` |
| **B5 knowledge** | say/hint 写 `memory_knowledge`；keep 不写 | `test_disclosure_choice.py` |
| **B6 validity** | `event_time_ms` 为有效起点，`valid_to_ms` 过滤过期/未来事实 | `test_memory_validity.py` |

