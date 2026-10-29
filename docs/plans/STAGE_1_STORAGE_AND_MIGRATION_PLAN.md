# Stage 1 详细工程设计、实现机理与验收报告：核心基础层与 SQLite WAL 仓储引擎
**（Stage 1 Detailed Engineering Specification & Acceptance Report — Status: ✅ 已验收通过）**

---

## 一、 Stage 1 解决的核心问题与设计目标

在旧版 Node.js `qq-agent` 中，配置、事件通知与状态存储存在三个致命的工程缺陷：
1. **散装 JSON 与内存覆写灾难**：好感度（`affinity.json`）、占有欲（`possessive-heart.json`）、生活状态（`her-life.json`）、人设生长（`persona-grow/state.json`）、海马体记忆（`ebbinghaus-memory/*.json`）各自维护内存变量 `let db = null` 并用异步 `setTimeout` 刷盘，一旦并发读写或手工修正磁盘文件，内存旧快照会直接把磁盘新数据覆盖丢失。
2. **事实库无权限锁**：群友随口一句“我是群主”，后台总结器就会把旧的正确记忆覆盖成错误事实，没有任何数据库级的防篡改机制。
3. **参数无稳态边界与审计日志**：静态配置无法在运行时随反馈安全演化，也没有任何历史变更轨迹可查。

**Stage 1 的工程目标**：构建 `core/`（不可变强类型配置中心 + 异常隔离事件总线）与 `adapters/storage/`（单文件 SQLite WAL 高并发数据库 + 17 张规范化表 + 防忽悠事实锁 + 稳态边界可塑参数仓储）。

---

## 二、 里程碑级详细实现机理与算法设计

### 里程碑 `M1.1`：不可变配置中心（`core/config.py`）与异常隔离事件总线（`core/events.py`）

#### 1. 怎么做（实现细节）
- **配置中心（`src/echomind/core/config.py`）**：
  - 定义三个继承自 `FrozenValueObject`（`ConfigDict(frozen=True, extra="forbid")`）的强类型配置模型：`GatewayEndpointConfig`、`OneBotConnConfig`、`AppConfig`。
  - 采用纯函数提取器 `_sub_dict()`、`_get_str()`、`_get_int()`、`_extract_str_tuple()` 替代嵌套 `if/else` 与长链 `or`，将单函数圈复杂度严格控制在 **Radon Grade A（`CC ≤ 3`）**。
  - **安全红线落地**：代码默认值中**不包含任何硬编码 Token、密码或个人 QQ 号/群号**（通过 `Ruff S104/S105` 静态安全扫描验证），全部由外部 `config.json` 或环境变量注入。
- **异步事件总线（`src/echomind/core/events.py`）**：
  - 采用泛型 `TEvent = TypeVar("TEvent", bound=FrozenValueObject)`，强制所有在总线上传输的事件必须是不可变值对象（防止订阅者A修改事件对象污染订阅者B，严格守护迪米特法则）。
  - **故障隔离机制（Fault Isolation）**：在 `_invoke_safe(handler, event)` 中对每个订阅者独立捕获异常并写入环形错误缓冲区 `_error_log`（保留最近 50 条供后台监控读取），确保任何一个扩展或监听器的崩溃**绝不会中断主流程或阻塞其他订阅者**。

---

### 里程碑 `M1.2`：SQLite WAL 高并发引擎与 17 表全量 Schema（`adapters/storage/database.py`）

#### 1. 怎么做（实现细节）
- 在 `SqliteDatabase.initialize()` 中，每次建连强制执行 4 条核心内核级 Pragma：
  ```sql
  PRAGMA journal_mode = WAL;      -- 开启预写日志模式：读不阻塞写、写不阻塞读
  PRAGMA synchronous = NORMAL;    -- 兼顾崩溃安全性与高吞吐落盘性能
  PRAGMA busy_timeout = 5000;     -- 并发写冲突时自动自旋等待最多 5000ms，消灭 database is locked
  PRAGMA foreign_keys = ON;
  ```
- **17 张核心业务表全景映射**：
  1. `chat_messages`：存储群聊/私聊消息、引用关系、自发表情与多模态附件 JSON（建有 `(chat_key, ts)` 与 `(chat_key, mid)` 复合索引）；
  2. `working_state`：跨会话持久化的前额叶工作记忆（含 `valence / energy / jealousy / shyness` 情绪向量、`inferiority / express_index / burst_until_ms` 占有欲压抑与终局爆发状态、四大内驱力、当前活动与 `story_arc_json` 连续剧进度、短期挂念栈 `intentions_json`、未知新词队列 `curiosity_queue_json`）；
  3. `episodic_memories`：海马体情景记忆事件卡（含 `summary`、`key_detail` 硬细节锚点、`importance`、`pinned`、`rehearsals` 复习次数、`last_recalled_ms`）；
  4. `semantic_facts`：语义事实图谱（`UNIQUE(chat_key, subject)`，含 `confidence`、`is_locked` 防忽悠硬锁、`source` 来源、`revision_count` 版本号）；
  5. `procedural_rules`：程序性条件反射默契表（`UNIQUE(chat_key, trigger_keyword, trigger_user_id)`）；
  6. `social_bonds`：群友社交关系账本（`PRIMARY KEY(chat_key, user_id)`，含好感分/等级、每日上限 `day_key / day_gain`、`trust_score` 元认知防忽悠可信度、`is_rival` 情敌标记、`traits_json` 性格画像）；
  7. `persona_traits` / `group_jargon` / `topic_interests` / `banned_phrases`：人格自生长词条、群黑话词库、领域兴趣偏科权重、自省拉黑禁用词表；
  8. `plastic_params` & `plastic_logs`：神经可塑性自演化参数当前值/上下界表 + 每次参数变动的完整强化学习审计日志表；
  9. `stickers` / `image_caption_cache` / `reminders` / `exploration_logs` / `llm_traces`：表情库、图片 MD5 视觉描述缓存、定时闹钟、后台好奇心探索足迹、大模型网关调用轨迹。

---

### 里程碑 `M1.3`：防忽悠事实锁与稳态可塑参数仓储（`memory_repo.py` & `working_repo.py`）

#### 1. 核心机制一：数据库级「权威事实防忽悠锁」（`SqliteMemoryRepository.upsert_semantic_fact`）
- **设计原理**：将“群友能不能改写某条事实”从脆弱的提示词劝导下沉为**存储层硬性守卫**。
- **执行流程与代码逻辑**：
  1. 当调用 `upsert_semantic_fact(fact: SemanticFact)` 时，先调用 `_check_fact_lock(conn, fact)` 查询数据库中同 `(chat_key, subject)` 的现有记录；
  2. 若现有记录 `is_locked == 1`（例如系统或主人锁定的 `本群真实群主 = kirakiraの馍馍(10004004)`），则检查新写入请求的权限：
     $$\text{can\_override} = (\text{fact.source} \in \{\text{"system"}, \text{"owner"}\}) \land (\text{fact.is\_locked} == \text{True})$$
  3. 若 `can_override == False`（例如来自群友日常聊天的 `source="peer"` 或后台未锁定的普通提取），**仓储层直接拒绝执行 SQL `UPDATE`，立即返回 `(False, "locked_fact_conflict")`**！
  4. 若允许更新，则执行 `ON CONFLICT(chat_key, subject) DO UPDATE` 并将版本号 `revision_count` 自动 `+1`。
- **实际达到的效果**：哪怕大模型在后台总结时偶发幻觉，把群友开玩笑说的“我是群主”当成了新事实试图写入数据库，仓储层也会 100% 物理拦截，保证权威事实永远不可能被群友污染！

#### 2. 核心机制二：神经可塑性参数的「稳态边界裁剪与演化审计」（`SqliteWorkingStateStore.update_plastic_param`）
- **设计原理**：生物神经可塑性必须伴随**稳态调节（Homeostatic Plasticity）**——如果参数无限单向增长，机器人要么变成每句话都插嘴的刷屏狂魔（`talkativeness -> 100`），要么变成彻底自闭的木头（`talkativeness -> 0`）。
- **数学约束公式**：
  每个可塑参数 $k$ 在初始化时绑定硬性上下界 $[\text{min\_bound}_k, \text{max\_bound}_k]$。每次收到学习增量 $\Delta$ 与反馈信号 $R$ 时：
  $$V_{\text{new}} = \text{round}\Big(\max\big(\text{min\_bound}_k,\ \min(\text{max\_bound}_k,\ V_{\text{old}} + \Delta)\big),\ 3\Big)$$
- **原子事务双写**：在同一个 SQLite 事务中，既更新 `plastic_params.value = V_new`，又向 `plastic_logs` 插入一条包含 `(ts, param_key, old_val, new_val, reward, reason)` 的永久审计记录。

---

## 三、 验收方法、测试用例矩阵与实测结果（Acceptance Verification）

Stage 1 的验收全部由自动化测试套件 `tests/integration/test_storage_repositories.py` 与外部迁移工具 `tools_migration/migrate_qq_agent.py` 执行：

| 验收项编号 | 测试函数 / 验证手段 | 输入数据与测试场景 | 预期结果 (Expected) | 实测结果 (Actual) |
|---|---|---|---|---|
| **AC-1.1** | `test_m1_1_config_and_event_bus_fault_isolation` | 向 `AsyncEventBus` 同时注册一个抛 `RuntimeError("boom")` 的坏处理器和一个正常处理器，发布 `AffectiveVector(valence=42.0)` | 正常处理器成功收到 `42.0`；坏处理器异常被捕获记入 `recent_errors`；主协程不崩溃 | ✅ `received == [42.0]`，`len(recent_errors) == 1` |
| **AC-1.2** | `test_m1_2_and_m1_3_sqlite_wal_lsp_and_anti_spoofing_lock` | 1. 调用 `db.initialize()`；<br>2. 先写入锁定事实 `subject="群主是谁", fact_text="Alice(11111)", is_locked=True, source="system"`；<br>3. 再模拟群友忽悠写入 `fact_text="Bob(22222)", source="peer"` | 1. 返回 `"wal"` 模式；<br>2. 第一次写入返回 `(True, "ok")`；<br>3. 第二次忽悠写入返回 `(False, "locked_fact_conflict")`，重查数据库仍为 `"Alice(11111)"` | ✅ 100% 拦截忽悠，原事实分毫无损 |
| **AC-1.3** | `test_m1_3_plastic_param_homeostatic_bounds_fuzz` (`Hypothesis`) | 使用 `hypothesis` 随机生成 25 组极端浮点数 `delta` $\in [-10000.0, +10000.0]$ 调用 `update_plastic_param("skepticism", delta)` | 无论输入多大或多小的 `delta`，更新后的 `skepticism` 恒满足 $10.0 \le V \le 95.0$ | ✅ 25 组极端随机冲击 100% 保持在 `[10.0, 95.0]` 内 |
| **AC-1.4** | `tools_migration/migrate_qq_agent.py` 实盘迁移对账 | 读取线上 `data-2/` 目录导入 `data/echomind.db` | 导入全部群友好感、海马体卡片、锁定权威事实、条件反射、表情包与 8 项可塑参数 | ✅ 成功导入：33条社交关系、69张记忆卡、3条权威事实、2条默契、36张表情、8项可塑参数 |

### Stage 1 门禁实跑成绩单：
- **代码覆盖率**：`database.py (100%)`、`memory_repo.py (100%)`、`working_repo.py (100%)`、`events.py (100%)`、`config.py (98%)`；
- **复杂度与反嵌套**：Radon 全员 Grade A，Pylint `10.00/10`，Mypy `--strict` 0 Error。
