# Stage 6 详细工程设计、实现机理与总验收报告：后台认知心跳调度器、生产启动入口与全链路总验收
**（Stage 6 Detailed Engineering Specification & Final Acceptance Report — Status: ✅ 已验收通过）**

---

## 一、 Stage 6 解决的核心问题与设计目标

经过 Stage 0 ~ Stage 5 的研发，我们已经完成了 `EchoMind` 的全部核心拼图（领域契约、SQLite WAL 17表仓储、NoneBot2 V11 桥接与防双 `@` 守卫、多模态感知与 GIF 分镜、主备故障转移 LLM 网关、12层认知核心 + 7维 HEXACO 动态性格与阴影面评估、五大微内核扩展槽与工具集、以及 FastAPI 全景控制台）。
最后一个阶段（Stage 6）负责将整套系统闭环为**可长期自治运行的生产级服务**：
1. **`M6.1` 后台认知心跳与睡眠巩固调度器（`src/echomind/runtime/scheduler.py`）+ 统一 ASGI/NoneBot2 启动入口（`src/echomind/main.py`）**：
   - **认知心跳守护器（`CognitiveHeartbeatScheduler`）**：
     - 周期性触发 `ICognitiveCoreFacade.run_autonomous_tick(now_ms)`（处理好奇心待查队列 `curiosity_explore`、吃醋冒泡 `jealousy_poke`、冷场主动找话题 `cold_group_topic`、私聊思念主人 `attachment_private`）；
     - 周期性触发 **`CraniMem` 睡眠抗干扰记忆修剪（`run_sleep_pruning`）**：清理未置顶、`rehearsals == 0` 且艾宾浩斯保持率 `< 0.15` 的低效用噪音卡片；
     - 周期性扫描 **`reminders` 定时闹钟表（`check_due_reminders`）**：当 `now_ms >= remind_at_ms` 且 `fired == 0` 时，自动调用 `IMessageSender.send_text()` 发送提醒并将 `fired` 置为 `1`！
   - **统一应用入口（`src/echomind/main.py`）**：
     - 加载 `AppConfig`，初始化 `EchoMindContainer`，挂载 `FastAPI` 认知控制台与后台心跳调度器，提供生产环境一键启动入口。
2. **`M6.2` 全链路端到端沙盒演练与灰度切换准备（`tests/integration/test_stage6_full_system.py`）**：
   - 将真实迁移好的线上数据库副本、感知富化管道、12层认知核心、7维性格阴影面评估、工具集、闹钟提醒、`CraniMem` 睡眠修剪与 FastAPI 控制台串联起来，跑通完整的端到端系统级验收测试，并验证一键灰度切换/回滚脚本。

---

## 二、 模块拆分与实现机理（单文件 ≤ 300 行，单函数 ≤ 40 行，嵌套 ≤ 2 层）

| 里程碑 | 交付文件 | 单一职责 (SRP) 与实现机理 | 预计行数 |
|---|---|---|---|
| **`M6.1`** 认知心跳与闹钟 | `src/echomind/runtime/scheduler.py` | 自主探索心跳、到期闹钟触发（`reminders` 表）与 `CraniMem` 睡眠低效用记忆修剪 | `~140 行` |
| **`M6.1`** 生产入口 | `src/echomind/main.py` | 组合根启动器、FastAPI 生命周期 `lifespan` 挂载与 ASGI 导出 | `~90 行` |
| **`M6.2`** 全链路总验收 | `tests/integration/test_stage6_full_system.py` | 覆盖「消息进入→感知富化→认知评估→工具调用→性格演化→闹钟触发→睡眠修剪→Web透视」的全链路测试 | `~180 行` |

---

## 三、 分步验收标准与测试用例矩阵（Acceptance Test Matrix）

| 验收项编号 | 测试场景与输入 | 预期量化结果 (Expected) |
|---|---|---|
| **AC-6.1** | 向 `reminders` 表插入一条已到期的闹钟（`"明早八点叫主人起床"`），调用 `scheduler.check_due_reminders(now_ms)` | 1. 自动通过 `IMessageSender` 向目标会话发出闹钟提醒；<br>2. 数据库中该闹钟 `fired` 字段更新为 `1`，二次扫描不再重复触发 |
| **AC-6.2** | 向 `episodic_memories` 插入一张 100 小时前未复习的水贴卡（`importance=1.2, rehearsals=0`）与一张置顶核心卡，调用 `scheduler.run_sleep_pruning(now_ms)` | 水贴卡因保持率 `< 0.15` 被 `CraniMem` 门控物理清除；置顶核心卡完好保留 |
| **AC-6.3** | 调用 `create_production_app()` 启动完整 ASGI 应用，执行端到端消息处理、自主心跳与 Web API 透视 | 全链路无异常跑通；`./scripts/qa_gate.sh` 全库 7 道门禁（`ruff`、`radon`、`pylint 10.00/10`、`mypy --strict`、`pytest >= 90%`）100% 全绿通过！ |

---

## 四、 阶段实测验收结果记录（Final Acceptance Results · 2026-10-28 19:56）

- **`M6.1` & `M6.2` 全链路总验收结果与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 通过
  - `runtime/scheduler.py`（72行，覆盖率 **`98%`**）：通过反嵌套门禁（将 `if fired_ids:` 翻转为提前返回卫语句 `if not fired_ids: return ()`，控制流嵌套深度严格 `≤ 2`）；
    - **`AC-6.1`（定时闹钟到期触发）**：验证已到期的 `"明早八点叫主人起床"` 闹钟自动通过 `IMessageSender` 发出并将 `fired` 置为 `1`，二次扫描绝不重复触发；
    - **`AC-6.2`（`CraniMem` 睡眠抗干扰记忆修剪）**：验证 100 小时前未复习、低重要度水贴卡因保持率 `< 0.15` 被物理清除，而置顶的 `"和主人约定织蓝色围巾"` 核心记忆卡 100% 完好保留；
  - `main.py`（29行，覆盖率 **`100%`**）与 `tests/integration/test_stage6_full_system.py`：
    - **`AC-6.3`（全系统端到端闭环验收）**：从 `create_production_app()` 启动完整生产容器与 FastAPI 应用 → 感知富化管道识别点名 `"尾尾，晚安啦"` → `CognitiveCoreFacade` 构建 12 层状态帧 → `AgentSessionRunner` 执行回复并触发 `persona_warmth` 性格升温 → FastAPI `/api/mind/snapshot` 实时验证记忆与性格状态！

### 全工程 56 个源文件最终 7 道门禁实测成绩单：
```text
🛡️  [Gate 1A] Ruff Static Lint (PEP8 + SIM + RET + C4 + C901<=6) -> All checks passed!
🛡️  [Gate 1B] Radon Cyclomatic Complexity                        -> 0 functions worse than B (avg 6.85)
🛡️  [Gate 1C] Pylint Anti-Nesting Check (max-nested-blocks <= 2) -> Your code has been rated at 10.00/10
🛡️  [Gate 2]  Mypy 100% Strict Static Type & LSP Verification    -> Success: no issues found in 56 source files
🛡️  [Gate 3 & 4] AST Flat-Code/SOLID Boundaries & Pytest (>=90%) -> 29 passed in 1.82s | Total coverage: 95.43%
✅ ALL INDUSTRIAL QA & ANTI-NESTING GATES PASSED (via uv run)!
```
