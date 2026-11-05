# EchoMind 交接文档（HANDOFF）

> 面向：接手本项目的工程师
> 最后更新：2026-11-05
> 阅读顺序：本文 → [`status/CURRENT_STATE.md`](status/CURRENT_STATE.md) → [`architecture/ARCHITECTURE_CONTRACTS.md`](architecture/ARCHITECTURE_CONTRACTS.md)

本文回答四个问题：**怎么跑起来**、**怎么运维**、**代码从哪看起**、**有哪些坑**。

---

## 0. 一页速览

| 项目 | 值 |
|---|---|
| 语言 / 运行 | Python 3.12+，包管理器 `uv` |
| 框架 | NoneBot2 + OneBot v11（NapCat） |
| 架构 | 六边形清洁架构，7 个顶层包，依赖由外向内单向 |
| 代码规模 | 203 个 Python 文件 / 约 20.6k 行 |
| 测试 | 444 个测试 / 约 12.2k 行 / 覆盖率 92% |
| 主要依赖服务 | LLM 网关、embedding（本机 8010）、语音合成（远端） |
| 启动入口 | `echomind.main:build_live_asgi_app`（ASGI 工厂） |
| 默认端口 | 3310（Web 控制台 + API） |
| 数据目录 | `data/`，主库 `data/echomind.db`（SQLite WAL） |
| 启停脚本 | `./scripts/service.sh {start\|stop\|restart\|status\|log}` |
| 门禁脚本 | `./scripts/qa_gate.sh` |

**五个包一句话职责**：

- `domain/` — 纯数据与接口，**零第三方依赖**，改这里要想清楚影响面
- `mind/` — 认知逻辑，最复杂但最"纯"，不允许碰数据库和网络
- `runtime/` — 一次对话回合的编排（工具循环、Prompt 装配、并发调度）
- `tools/` — LLM 可调用的工具，必须无状态、无人设
- `adapters/` — 所有 I/O 都在这里（SQLite、HTTP、OneBot、媒体）

---

## 1. 本地开发环境

### 1.1 从零跑起来

```bash
# 1) 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2) 获取代码与依赖
git clone https://github.com/Polyisoprene/echo-mind.git
cd echo-mind
uv sync                       # 创建 .venv 并安装运行时+开发依赖

# 3) 配置
cp .env.example .env
# 编辑 data/config.json（结构见 1.2）

# 4) 初始化数据库（首次会自动建表，也可手动触发）
uv run python -c "import asyncio;from pathlib import Path;from echomind.adapters.storage.database import SqliteDatabase;asyncio.run(SqliteDatabase(Path('data/echomind.db')).initialize())"

# 5) 本地起服务
./scripts/service.sh start
./scripts/service.sh status
```

### 1.2 `data/config.json` 关键字段

配置是**单文件 JSON**，由 `core/config.py` 解析为冻结的 `AppConfig`。常用字段：

| 字段 | 说明 | 注意 |
|---|---|---|
| `api.baseUrl` / `api.apiKey` / `api.model` | 主 LLM 网关（OpenAI 兼容） | 必填 |
| `api.fallbackModels` / `api.fallbackBaseUrl` | 故障转移链 | 主端点失败自动切换 |
| `api.embeddingBaseUrl` | 向量服务地址 | 留空则语义检索降级 |
| `api.visionModel` | 看图模型 | 空则图像能力关闭 |
| `feiyuVoice.baseUrl` | 语音合成服务 | 不可达时语音工具自动失效 |
| `selfQq` / `allowedGroups` / `operatorIds` | 账号与准入白名单 | 群号不带 `group:` 前缀 |
| `server.port` / `server.token` | 控制台端口与令牌 | **token 为空时仅 loopback 可访问**（fail-closed） |
| `snowluma.wsUrl` / `httpUrl` | OneBot 连接地址 | 指向 NapCat |

### 1.3 运行期开关（`.env`）

```bash
ECHOMIND_SATIATION=shadow        # 社交习惯化：off | shadow | on
ECHOMIND_THINKING=on             # 模型思考通道
ECHOMIND_REASONING_EFFORT=low    # low | high | max
FACTS_V2_WRITE=1                 # 事实双写（claims/evidence 影子库）
```

改 `.env` 后必须 `./scripts/service.sh restart`。

### 1.4 日常开发循环

```bash
uv run pytest -q                              # 快速跑全量测试（约 45s）
uv run pytest tests/unit/test_xxx.py -k name  # 单个测试
uv run ruff check src tests --fix              # 自动修 lint
./scripts/qa_gate.sh                          # 提交前跑全门禁（约 3–5 分钟）
```

---

## 2. 生产运维

### 2.1 启停（务必用脚本，不要手工 kill）

```bash
./scripts/service.sh start     # 启动，内部用 screen -dmS qqagent2 守护
./scripts/service.sh status    # 会 curl /api/mind/snapshot 验活
./scripts/service.sh restart
./scripts/service.sh stop
./scripts/service.sh log 200   # 追日志
```

**为什么必须用脚本**：服务以 `screen` + `while true; do uvicorn ...; sleep 3; done` 方式守护，子进程被 kill 后 3 秒自动复活。`service.sh` 的 `do_stop` 只精确匹配 `/.venv/bin/uvicorn ... --port <PORT>`，不会误杀 screen 包装层。

> ⚠️ **不要用 `pkill -f uvicorn`**：会留下孤儿 screen 会话反复重启，也会误伤其他实例。
> 如果已经在别处手工启动了带 `while true` 的 screen 会话，正确停止方式是 `screen -S <会话名> -X quit`（退出整个会话），而不是 kill 子进程。

### 2.2 多实例

项目支持多机器人共存：

```bash
ECHOMIND_INSTANCE=xiaomo ./scripts/service.sh start
```

会读取 `.env.xiaomo`，使用 `data-xiaomo/` 数据目录、独立端口、独立 screen 会话名（`qqagent2-xiaomo`）。主实例与副实例的数据库文件完全隔离。

### 2.3 外部依赖服务

| 服务 | 默认地址 | 谁在用 | 挂了会怎样 |
|---|---|---|---|
| **NapCat**（OneBot） | `snowluma.wsUrl` | 全部收发链路 | 完全无法收发消息（通常跑在 docker 里） |
| **Embedding**（bge-m3） | `127.0.0.1:8010` | 语义记忆检索 | 降级为关键词检索，不崩溃 |
| **语音合成**（CosyVoice3） | `feiyuVoice.baseUrl`（远端） | `feiyu_say` / `feiyu_cover` | 语音工具报错，文字链路正常 |
| **LLM 网关** | `api.baseUrl` | 全部推理 | 自动切 fallback；全挂则整轮失败 |

**排查顺序**：先 `./scripts/service.sh status` 看进程，再看 `data/console.log` 尾部，最后逐个验证外部服务端口。

外部服务的部署细节见 [`operations/README.md`](operations/README.md)。

### 2.4 数据与备份

- 主库：`data/echomind.db`（SQLite WAL，约 80 MB）
- 日志：`data/console.log`
- 控制台审计：库内 `admin_audit` 表（只记 method/path/status，**不记录 query**，避免 token 落盘）
- 备份：直接拷贝 `.db` 即可（WAL 模式下建议先 `sqlite3 data/echomind.db "PRAGMA wal_checkpoint(TRUNCATE)"` 或停服后拷贝）

`data/` 下已有历史备份如 `backup_pre_d4_*.db`，可清理但建议保留最近一份。

---

## 3. 代码地图：从哪开始读

### 3.1 推荐阅读顺序

```
1. domain/models.py          值对象：理解系统里流动的是什么数据
2. domain/ports.py           29 个 Protocol：理解所有能力边界
3. core/bootstrap.py         组合根：看到所有东西怎么装配起来
4. runtime/agent_runner.py   一次对话回合的完整生命周期
5. mind/facade.py            认知核心门面：5 个方法，runtime 只看这个
6. mind/cybernetics.py       序参量核心：决定本轮用什么工具、什么温度
7. adapters/storage/*.py     17 个仓储：所有 SQL 都在这里
```

### 3.2 一次对话回合的数据流

```
OneBot WS 事件
  └─ adapters/onebot/live_client.py   接收、去抖、按 chat_key 加锁
      └─ runtime/scheduler.py          会话级调度
          └─ mind/facade.evaluate_incoming()      决定要不要醒（AttentionDecision）
          └─ mind/facade.build_cognitive_frame()  组装认知帧（序参量、记忆、人格）
              └─ runtime/prompt_composer.py       渲染 system + 历史
                  └─ runtime/agent_runner.py      6 轮 ReAct 工具循环
                      └─ extensions/registry.py   工具分发
                  └─ adapters/onebot/...          发送
          └─ mind/facade.on_turn_completed()      回合后：人格更新、记忆巩固、关系结算
```

### 3.3 常用定位手段

项目自带 CodeGraph 索引（`.codegraph/codegraph.db`，6356 节点 / 16535 边）：

```bash
codegraph explore "记忆召回与重排"          # 语义检索相关符号
codegraph node hippocampus                  # 看单个符号/文件
codegraph callers CognitiveCoreFacade       # 谁调用了它
codegraph impact SqliteDatabase             # 改它会波及哪些符号
codegraph sync                              # 与代码同步
```

---

## 4. 代码改动规范（硬约束）

改代码前**必须**读 [`architecture/ARCHITECTURE_CONTRACTS.md`](architecture/ARCHITECTURE_CONTRACTS.md)。以下几条由 CI 强制，违反直接失败：

| 约束 | 上限 | 由谁强制 |
|---|---|---|
| 单文件行数 | ≤ 300 | `test_solid_boundaries.py` |
| 单函数行数 | ≤ 40 | `test_solid_boundaries.py` |
| 控制流嵌套深度 | ≤ 2 | `test_solid_boundaries.py` |
| 函数圈复杂度 | ≤ 6 | `ruff C901` |
| 单个 Protocol 方法数 | ≤ 5 | `test_solid_boundaries.py` |
| `domain/` `mind/` 基础设施导入 | 禁止 | `test_solid_boundaries.py` |
| 领域模型 | 必须 `frozen=True, extra="forbid"` | `test_solid_boundaries.py` |
| 类型注解 | 100% strict | `mypy --strict` |

**嵌套深度 ≤ 2 是最容易踩的**：不要写 `if` 套 `for` 套 `if`，直接用卫语句提前 return，或把内层逻辑抽成私有函数。

**新增端口**：如果一个能力需要跨层调用，先在 `domain/ports.py`（或 `domain/*_ports.py`）定义窄 Protocol，再在 `adapters/` 实现。不要直接 import 具体实现类。

---

## 5. 质量门禁

```bash
./scripts/qa_gate.sh
```

| 门禁 | 命令 | 当前状态 |
|---|---|---|
| 1A 静态检查 | `ruff check src tests` | ✅ 0 |
| 1B 复杂度 | `radon cc src -nc` | ✅ 0 |
| 1C 反嵌套 | `pylint src/echomind` | ✅ 10.00/10 |
| 2 类型 | `mypy --strict src` | ✅ 0 |
| 2B 参数台账 | `scripts/param_gate.py` | ✅ 62/62 |
| 2C 能力台账 | `scripts/capability_gate.py --check` | ✅ 27 |
| 3 架构边界 | `tests/architecture/` | ✅ |
| 4 测试覆盖率 | `pytest --cov --cov-fail-under=90` | ✅ 92% |

### 两道台账怎么用

- **参数台账**（`docs/params/ledger.json`）：每个可调常数都要声明来源（`fit` / `convention` / `fit_pending`）。新增魔数会失败。
- **能力台账**（`docs/capabilities.json`）：声明"已实现"必须给出存在的验收测试，否则失败。改完请跑 `python scripts/capability_gate.py` 重新生成 `docs/status/CAPABILITY_STATUS.md`。

### 文档门禁（本次新增）

`tests/architecture/test_docs_integrity.py` 强制：

1. 所有 markdown 相对链接必须指向真实文件
2. `capabilities.json` 里的 `docs` 路径必须存在
3. `docs/` 根目录只允许 `README.md` 与 `HANDOFF.md`
4. 归档文档必须带「已归档」横幅

**移动文档后忘了改引用 → 测试直接失败**，不会静默腐化。

---

## 6. 已知缺陷与技术债

> 以下问题在 2026-11-03 的代码评审中经**真实链路复现**确认（详见 [`archive/reviews/`](archive/reviews/)）。按优先级排列，**建议优先处理 P1**。

### P1-A：trace 写库失败会丢弃已计费的 LLM 调用

**位置**：`adapters/llm/client.py:175-191`

```python
try:
    resp = await self._call_endpoint(...)     # HTTP 成功，已计费
    await self._record_trace(...)             # 写 SQLite，无 try/except
    return resp
except Exception as exc:                      # trace 写失败也落进这里
    last_exc = exc
```

**后果**：trace 写入与业务返回共用一个 try，SQLite 锁冲突会导致**成功响应被丢弃**，并在 failover 链上**对每个端点重新调用一次**（实测 2 个端点 = 2 次计费）。

**修法**：把 `_record_trace` 移出故障判定路径，单独包 try/except 并只记 warning。

同类问题：`web/app.py:246-258` 的 `write_audit` 无异常保护，写库失败会让业务请求直接 500。

### P1-B：试剂表引用了未注册的工具名

**位置**：`mind/cybernetics.py:42-43`

`REAGENT_TOOLS["社交防忽悠核查剂"]` 里有 `qzone_publish`、`profile_signature`，但**这两个工具从未注册**（全仓库仅此一处出现）。实际注册的是 `qzone_showcase`，而它不被任何试剂选中。

**后果**：
- "社交防忽悠核查剂"实际只能下发 3 个工具而非 5 个
- `qzone_showcase` 永远不会通过 LLM 工具通道被调用（只能由 `qzone_scheduler` 直接调 API）

**修法**：修正名字，并加一条测试断言"试剂引用的每个工具名都必须在注册表中"。注意 `tests/unit/test_cross_session_tool_visibility.py:10` 现有断言方向是反的，覆盖不到这个问题。

### P2-A：架构门禁漏检 `core/` 包

**位置**：`tests/architecture/test_solid_boundaries.py:22-31`

黑名单只有 `echomind.adapters / web / tools`，**没有 `echomind.core`**，且扫描列表不含 `core/`。而 `ARCHITECTURE_CONTRACTS.md:15` 明确规定 `mind/` **"仅依赖 domain/"**。

**已验证**：在 `mind/naming.py` 加入 `from echomind.core.config import AppConfig`，架构门禁 12 项全部通过；进一步可经 `core.bootstrap` 连带载入 31 个 adapters 子模块。即**一行 import 就能让认知核心反向依赖全部基础设施而不报警**。

**修法**：把 `echomind.core` 加入 `domain`/`mind`/`tools`/`extensions`/`runtime` 的黑名单（`core → adapters` 合法，`mind → core` 禁止，方向要分开写）。

### P2-B：海马体提示词在导入期冻结

**位置**：`mind/hippocampus.py:19-38`

`HIPPOCAMPUS_INSTRUCTIONS` 是模块级常量，`bot_naming()` 在 import 时求值并固化为字符串；而 `set_bot_naming()` 要到 `core/bootstrap.py` 才调用。

**后果**：改人格名后，其他提示词都更新，**唯独记忆巩固提示词继续自称旧名**，并按错误身份提炼长期记忆。实测已确认该常量注入到真实 system 消息。

**修法**：改为函数 `def _instructions() -> tuple[str, ...]`，调用时求值。`mind/` 内其余 9 处 `bot_naming()` 都是函数内调用，只有这一处有问题。

### P2-C：GIF 解码阻塞事件循环

**位置**：`adapters/onebot/media_gateway.py:118`

`gif_to_storyboard_data_url()` 是同步 Pillow 解码，直接在协程里调用。实测 60 帧 GIF 耗时 **105 ms**，期间事件循环完全阻塞。同文件的视频路径（`:155,158`）却正确使用了 `asyncio.to_thread`。

**修法**：`await asyncio.to_thread(gif_to_storyboard_data_url, raw)`。

### P2-D：WebSocket 事件无并发上界

**位置**：`adapters/onebot/live_client.py:264`

每条 WS 事件直接 `asyncio.create_task(self.handle_raw_event(ev))`，不保存引用、无信号量。实测 800 条事件 → 峰值并发 800。

**已缓解的部分**：`_drain_chat_batches` 有 per-chat `asyncio.Lock`（同会话不并发），`_wake_scheduled` 有去抖——但去抖在 `evaluate_incoming`（含 LLM 调用）**之后**，前面那串 I/O 仍是全量并发。

**修法**：加 `asyncio.Semaphore` 限流，并把去抖提前到任何 I/O 之前；同时持有 task 引用集合以支持优雅停机。

### P3：其他

| 问题 | 位置 | 说明 |
|---|---|---|
| `Any` 软逃逸 | `mind/relation_persist.py:10` | `writer: Any` + `getattr` 探测，mypy 完全失效；传错对象静默返回 0，**关系数据丢失且无日志** |
| 其余 `getattr` 兜底 | `tools/member_memory.py:123`、`mind/frame_renderer.py:49-51` | 绕过类型系统探测能力，建议改为窄端口 |
| token 非恒定时间比较 | `web/auth.py:59` | 应改 `hmac.compare_digest` |
| httpx client 不复用 | `adapters/llm/client.py:29` | 每次请求新建 `AsyncClient`，低效 |
| 文档数字漂移 | `ARCHITECTURE_CONTRACTS.md:51` | 文档称门面"4 个方法"，实际 5 个 |
| 文档描述的 `service.sh logs` | 已修正 | 实际参数是 `log`，README 已改正 |

### 有意保留的"矛盾"项

`docs/capabilities.json` 中 3 项标为 `contradicted`，是**已知且有意保留**的：

- `CAP-HEXACO`：7 维人格与 HEXACO 无映射
- `CAP-ZERO-LEXICON`：`mind/` 仍有中文词表
- `CAP-OPERATOR-NO-PRIVILEGE`：群主在关系计算中确有特权

建议**改能力声明而不是改代码**，或明确写出"这是产品选择"。

---

## 7. 常见问题排查

| 现象 | 排查 |
|---|---|
| 控制台打不开 | `./scripts/service.sh status`；看 `data/console.log` 尾部 |
| 401 unauthorized | `server.token` 有值但浏览器没带；loopback 访问可免 |
| 机器人不回复 | 检查 NapCat 是否在线、`allowedGroups` 是否包含该群、唤醒门控日志 |
| 记忆召回差 / 无语义结果 | embedding 服务是否在 `127.0.0.1:8010` 存活 |
| 语音工具报错 | `feiyuVoice.baseUrl` 对应的远端服务是否在线 |
| 分数/参数异常 | 看 [`status/PARAMETER_SCORECARD.md`](status/PARAMETER_SCORECARD.md) 哪些参数尚未标定 |
| 改完文档测试挂了 | 有新链接失效或目录不合规，看 `test_docs_integrity.py` 的报错列表 |

---

## 8. 交接检查清单

接手时建议按顺序确认：

- [ ] `uv sync` 成功，`.venv` 建好
- [ ] `./scripts/qa_gate.sh` 全绿（444 passed / 92%）
- [ ] `data/config.json` 填好，`./scripts/service.sh start` 能起
- [ ] NapCat 在线，发一条消息机器人有反应
- [ ] Web 控制台能打开并看到唤醒日志
- [ ] `codegraph sync` 后能用 `codegraph explore` 定位代码
- [ ] 读过 [`status/CURRENT_STATE.md`](status/CURRENT_STATE.md)，清楚系统边界
- [ ] 看过第 6 节已知缺陷，评估是否先修 P1

---

<div align="right"><a href="README.md">← 返回文档索引</a></div>
