# EchoMind 项目立项书与全局工程进度总表
**（Project Charter & Master Progress Tracker）**

---

## 一、 项目立项书（Project Charter）

| 立项要素 | 详细内容 |
|---|---|
| **项目代号** | `ECHO-MIND-2026` |
| **项目名称** | 回音（EchoMind）生产级类人认知智能体系统重构工程 |
| **部署宿主机** | `polyisoprene@192.168.3.114`（工程路径：`/home/polyisoprene/Documents/echo-mind`） |
| **协同算力节点** | `192.168.3.2:8080`（飞鱼语音 GPU 服务：TTS 合成与 `POST /v1/cover` 全曲 AI 翻唱） |
| **立项背景** | 原 Node.js 版 `qq-agent`（21,562 行代码 + 22 个外挂插件）存在巨型上帝文件、无类型契约、20+ 个散乱 JSON 状态互相覆盖、4 套定时器抢话筒、6 处提示词拼贴冲突、以及静态死参数无学习能力等严重架构腐化问题。 |
| **立项核心目标** | 使用 **Python 3.12+ / NoneBot2 (`nonebot-adapter-onebot`) / FastAPI / Pydantic v2 / SQLite WAL (FTS5)** 从零重建：打造一套严格符合 **SOLID 五大原则 + 迪米特法则**、具备 **微内核五大扩展槽**、内建 **12 层认知核心（注意路由 + 工作记忆 + 五维记忆 + 元认知防忽悠 + 好奇心主动探索 + 海马体睡眠重放 + 神经可塑性参数自演化）** 的工业级生产系统。 |
| **工程治理铁律** | 1. **先规划后编码**：每一阶段动工前必须先编写 `docs/plans/STAGE_X_PLAN.md` 详细规划书，明确模块拆分、行数上限（`≤300行`）、里程碑与量化验收标准；<br>2. **自动化门禁准出**：每完成一个里程碑必须实跑 `./scripts/qa_gate.sh`（`ruff C901≤10` + `mypy --strict` + `AST SOLID边界` + `pytest 覆盖率≥90%` + `hypothesis 模糊测试`），并将真实终端验收结果回填至规划文档与本进度总表。 |

---

## 二、 全局阶段与里程碑进度总表（Master Progress Tracker）

> **状态图例**：`✅ 已验收通过` ｜ `📋 已出规划待施工` ｜ `⏳ 待规划`

| 阶段 | 里程碑编号 | 里程碑名称 | 关联规划与验收文档 | 核心交付物 | 门禁与覆盖率结果 | 当前状态 |
|---|---|---|---|---|---|---|
| **Stage 0**<br>立项与契约基座 | `M0.1` | 项目脚手架与工业 QA 工具链搭建 | `STAGE_0_CONTRACTS_PLAN.md` | `pyproject.toml`, `.venv`, `scripts/qa_gate.sh` | Ruff: 0 err / Mypy: Pass | ✅ 已验收通过 |
| **Stage 0** | `M0.2` | 架构宪法、不可变领域模型与隔离端口定义 | `STAGE_0_CONTRACTS_PLAN.md` | `ARCHITECTURE_CONTRACTS.md`, `domain/models.py`, `domain/ports.py` | 14 DTOs (`frozen=True`), 12 Narrow Protocols (`≤5` methods) | ✅ 已验收通过 |
| **Stage 0** | `M0.3` | AST 架构边界守护与契约模糊测试 | `STAGE_0_CONTRACTS_PLAN.md` | `test_solid_boundaries.py`, `test_domain_contracts.py` | 7/7 Tests Passed, **Coverage: 100.00%** | ✅ 已验收通过 |
| **Stage 1**<br>存储层与数据迁移 | `M1.1` | 核心配置中心与进程内类型化事件总线 | `STAGE_1_STORAGE_AND_MIGRATION_PLAN.md` | `core/config.py`, `core/events.py` | Ruff: 0 / Mypy: Pass / Cov: 99% | ✅ 已验收通过 |
| **Stage 1** | `M1.2` | SQLite WAL + FTS5 异步连接池与 8 表 Schema | `STAGE_1_STORAGE_AND_MIGRATION_PLAN.md` | `adapters/storage/database.py` | WAL verified / Cov: 100% | ✅ 已验收通过 |
| **Stage 1** | `M1.3` | 实现 `IMemoryReader/Writer` 与 `IWorkingStateStore` 仓储适配器 | `STAGE_1_STORAGE_AND_MIGRATION_PLAN.md` | `adapters/storage/memory_repo.py`, `working_repo.py` | LSP + Hypothesis Fuzz Pass / Cov: 99% | ✅ 已验收通过 |
| **Stage 1** | `M1.4` | 旧版 `data-2/` 存量数据无损迁移与幂等对账校验器 | `STAGE_1_STORAGE_AND_MIGRATION_PLAN.md` | `migrator.py`, `migrate_from_legacy.py` | 33人好感/74张记忆卡/36表情 幂等入库 (Total Cov: **97.54%**) | ✅ 已验收通过 |
| **Stage 2**<br>协议与模型网关层 | `M2.1` | `NoneBot2` (`onebot.v11`) 桥接器与防双 `@` 发信守卫 | `STAGE_2_ADAPTERS_PLAN.md` | `adapters/onebot/send_guard.py`, `bot_bridge.py` | Hypothesis Fuzz Pass / Cov: 98% | ✅ 已验收通过 |
| **Stage 2** | `M2.2` | 多模态感知富化责任链（引用表情描述关联、卡片解析、MD5缓存、GIF 2×2分镜） | `STAGE_2_ADAPTERS_PLAN.md` | `adapters/onebot/enrichers.py`, `media_codec.py` | Storyboard + Enrichers Pass / Cov: 93% | ✅ 已验收通过 |
| **Stage 2** | `M2.3` | 主备高可用 LLM 网关客户端与前缀缓存锚点引擎 | `STAGE_2_ADAPTERS_PLAN.md` | `adapters/llm/client.py`, `anchor.py` | Failover + Anchor Pass (Total Cov: **97.12%**) | ✅ 已验收通过 |
| **Stage 3**<br>12层认知核心与自学习引擎 | `M3.1` | 感知显著性路由闸门与未知新词好奇检测器 | `STAGE_3_MIND_CORE_PLAN.md`<br>`COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md` | `mind/perceptual_gate.py` | Salience + Followup Pass / Cov: 92% | ✅ 已验收通过 |
| **Stage 3** | `M3.2` | 五维长期记忆检索、艾宾浩斯双层衰减与元认知防忽悠校准器 | `STAGE_3_MIND_CORE_PLAN.md` | `mind/ebbinghaus.py`, `mind/epistemic.py` | Hypothesis Fuzz + Anti-Spoof Pass / Cov: 97% | ✅ 已验收通过 |
| **Stage 3** | `M3.3` | 四大内驱力状态机与后台自主调用搜索/B站好奇探索器 | `STAGE_3_MIND_CORE_PLAN.md` | `mind/drives.py`, `mind/explorer.py` | Jealousy + Arbiter Pass / Cov: 88% | ✅ 已验收通过 |
| **Stage 3** | `M3.4` | 🌱 人格自生长、海马体小憩/睡眠重放、🧬 神经可塑性参数自学习与统一门面 | `STAGE_3_MIND_CORE_PLAN.md`<br>`COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md` | `mind/hippocampus.py`, `mind/plasticity.py`, `mind/facade.py` | DIP Verified / Facade Cov: 98% (Total Cov: **95.56%**) | ✅ 已验收通过 |
| **Stage 4**<br>效应器与运行时层 | `M4.1` | 微内核五大扩展槽注册器与全套内置无状态工具集 | `STAGE_4_TOOLS_RUNTIME_PLAN.md` | `extensions/registry.py`, `tools/{messaging_and_group,explore_and_voice}.py` | 5-Slot Protocol Guard + Tools Pass / Cov: 94% | ✅ 已验收通过 |
| **Stage 4** | `M4.2` | 提示词装配、去马太效应表情轮换、5重口语抢救与 Agent 运行时 | `STAGE_4_TOOLS_RUNTIME_PLAN.md` | `runtime/{prompt_composer,reply_rescue,agent_runner}.py` | E2E Cognitive Loop Pass (Total Cov: **95.21%**) | ✅ 已验收通过 |
| **Stage 5**<br>全景控制台与API | `M5.1` | 组合根依赖注入容器、FastAPI 认知透视 API 与《🧠 认知核心全景控制台 2.0》 | `STAGE_5_WEB_CONSOLE_PLAN.md` | `core/bootstrap.py`, `web/{mind_inspector_service,app,ui_html}.py` | Web & Bootstrap 100% Cov (Total Cov: **94.70%**) | ✅ 已验收通过 |
| **Stage 6**<br>全链路压测与切换 | `M6.1` | 后台认知心跳、闹钟触发、`CraniMem` 睡眠修剪与全链路总验收 | `STAGE_6_CUTOVER_ACCEPTANCE_PLAN.md` | `runtime/scheduler.py`, `main.py`, `test_stage6_full_system.py` | 29/29 Tests Pass / Pylint 10.00/10 / **Total Cov: 95.43%** | ✅ 已验收通过 |
| **Stage 7**<br>全局缺陷建模与架构修复 | `M7.1` | 安全边界鉴权、完整配置映射、SQLite连接级PRAGMA与无损幂等迁移 | `STAGE_7_GLOBAL_REMEDIATION_PLAN.md` | `core/config.py`, `web/app.py`, `database.py`, `working_repo.py`, `migrate_qq_agent.py` | 401 Guard + Pragma + Idempotent Migration Pass / Cov: 98%~100% | ✅ 已验收通过 |
| **Stage 7** | `M7.2` | 认知核心状态一致性、程序规则短路修复、零副作用探针与稳态回归 | `STAGE_7_GLOBAL_REMEDIATION_PLAN.md` | `mind/{frame_renderer,perceptual_gate,facade,plasticity}.py`, `web/probe_service.py` | Dry-Run Probe + Rule Keyword + Homeostatic Pull Pass / Cov: 97% | ✅ 已验收通过 |
| **Stage 7** | `M7.3` | 运行时闭环（表情轮换计数、长句合并、抢救禁令过滤、工具异常兜底、心跳落库） | `STAGE_7_GLOBAL_REMEDIATION_PLAN.md` | `runtime/{agent_runner,scheduler}.py`, `tools/{messaging_and_group,member_memory}.py`, `bot_bridge.py` | Sticker Bump + Ban Purge + Fault Isolation Pass / Cov: 91%~98% | ✅ 已验收通过 |
| **Stage 7** | `M7.4` | 多模态临时目录清理、GIF分镜接入、B站WBI守卫、DIP纯化与QA门禁`>=90%` | `STAGE_7_GLOBAL_REMEDIATION_PLAN.md` | `adapters/{onebot/media_gateway,onebot/live_client,media/bili}.py`, `domain/ports.py`, `qa_gate.sh` | 56/56 Tests Pass / Pylint 10.00/10 / **Total Cov: 92.69% (93%)** | ✅ 已验收通过 |
| **Stage 8**<br>性格语义与全息控制台 | `M8.1` | 7维性格逐维双极量表与分档行为语义解释器、情绪量表注释 | `STAGE_8_CONSOLE_AND_PERSONA_SEMANTICS_PLAN.md` | `mind/personality.py`, `mind/frame_renderer.py` | 7D Rubrics + Affect Scale Verified / Cov: 90%~100% | ✅ 已验收通过 |
| **Stage 8** | `M8.2` | 全息会话可观测性契约（携带上下文条数、真实System/User提示词持久化） | `STAGE_8_CONSOLE_AND_PERSONA_SEMANTICS_PLAN.md` | `domain/models.py`, `database.py`, `trace_repo.py`, `agent_runner.py`, `chat_service.py` | Context Count + Prompts Trace Pass / Cov: 97%~100% | ✅ 已验收通过 |
| **Stage 8** | `M8.3` | Web控制台白天/夜间双主题切换、对齐qq-agent会话检查器与折叠状态防重置修复 | `STAGE_8_CONSOLE_AND_PERSONA_SEMANTICS_PLAN.md` | `web/static/{index.html,style.css,app.js}` | 57/57 Tests Pass / Live Service Restarted / **Total Cov: 92.72% (93%)** | ✅ 已验收通过 |
| **Stage 9**<br>人设与记忆冲突消解架构 | `M9.1` | 提示词宪法优先级三定律与海马体感知 `role_text` 防串味巩固（零硬编码） | `STAGE_9_ANTI_PERSONA_POLLUTION_PLAN.md` | `runtime/prompt_composer.py`, `mind/{hippocampus,memory_consolidator}.py` | Epistemic Hierarchy + Activity Metabolism Pass | ✅ 已验收通过 |
| **Stage 9** | `M9.2` | 通用 LLM 驱动「人设-记忆冲突校准引擎」与控制台一键校准/细粒度删除 | `STAGE_9_ANTI_PERSONA_POLLUTION_PLAN.md` | `mind/persona_reconciler.py`, `web/{llm_config_service,ext_routers,app}.py` | 58/58 Tests Pass / Live Reconciled / **Total Cov: 92.55% (93%)** | ✅ 已验收通过 |
| **Stage 10**<br>动态可信度双向校准 | `M10.1` | 单轮多信号可信度演化、识破忽悠扣分、海马体复盘联动与控制台微调 | `STAGE_10_DYNAMIC_TRUST_CALIBRATION_PLAN.md` | `mind/memory_consolidator.py`, `web/{ext_routers,mind_inspector_service,static/app.js}` | 59/59 Tests Pass / Pylint 10.00/10 / **Total Cov: 92.66% (93%)** | ✅ 已验收通过 |
| **Stage 11**<br>实时会话与多服务商模型中心 | `M11.1` | NapCat真实在线探测、`reply_to`防误传QQ号守卫与全会话混排时间线 | `STAGE_11_LIVE_SESSION_AND_MULTI_PROVIDER_LLM_PLAN.md` | `web/mind_inspector_service.py`, `tools/messaging_and_group.py`, `trace_repo.py` | QQ Online Probe + Reply/At Guard Pass / Cov: 93%~100% | ✅ 已验收通过 |
| **Stage 11** | `M11.2` | 会话全生命周期实时流式状态机（`running` → 逐轮增量更新 → `done`） | `STAGE_11_LIVE_SESSION_AND_MULTI_PROVIDER_LLM_PLAN.md` | `runtime/agent_runner.py`, `main.py`, `web/static/app.js` | Live Running Stream Verified / Cov: 87% | ✅ 已验收通过 |
| **Stage 11** | `M11.3` | 多服务商注册表（Multi-Provider）与有序 N 级备用模型故障转移链 | `STAGE_11_LIVE_SESSION_AND_MULTI_PROVIDER_LLM_PLAN.md` | `adapters/llm/client.py`, `core/config.py`, `web/llm_config_service.py`, `index.html`, `app.js` | 60/60 Tests Pass / Pylint 10.00/10 / **Total Cov: 92.43% (92%)** | ✅ 已验收通过 |
| **Stage 12**<br>主动语音、AI翻唱与自主冲浪 | `M12.1` | 主动发语音表达引导、B站原曲音轨提取与飞鱼全曲 AI 翻唱（`feiyu_cover`） | `STAGE_12_VOICE_SINGING_AND_AUTONOMOUS_SURFING_PLAN.md` | `adapters/media/{bili,feiyu}.py`, `tools/voice_tools.py`, `prompt_composer.py`, `frame_renderer.py` | Proactive Voice + Full-Song Cover Pass / Cov: 85%~100% | ✅ 已验收通过 |
| **Stage 12** | `M12.2` | 全网+B站复合搜索后端、后台自主搜梗/刷B站执行闭环与控制台冲浪足迹面板 | `STAGE_12_VOICE_SINGING_AND_AUTONOMOUS_SURFING_PLAN.md` | `tools/explore_and_voice.py`, `mind/explorer.py`, `runtime/scheduler.py`, `web/` | 61/61 Tests Pass / Live Bili Surf Verified / **Total Cov: 90.94% (91%)** | ✅ 已验收通过 |
| **Stage 12** | `M12.3` | 空间心情橱窗「多目标主动发消息」（支持多群、多个人私聊、群内`@`某人）及可视化编辑器 | `STAGE_12_VOICE_SINGING_AND_AUTONOMOUS_SURFING_PLAN.md` | `tools/qzone_and_profile.py`, `runtime/qzone_scheduler.py`, `web/static/app.js` | Multi-Target Parse + Dispatch Pass / **Total Cov: 90.91% (91%)** | ✅ 已验收通过 |
| **Stage 13**<br>时间感知、去重与外源情感演化 | `M13.1` | 消息时间戳、`>=5分钟`时间断层自动分割线与旧话题自动翻篇机制 | `STAGE_13_TEMPORAL_AWARENESS_AND_EXOGENOUS_AFFECT_PLAN.md` | `runtime/prompt_composer.py`, `mind/frame_renderer.py` | Temporal Gap Divider Verified / Cov: 97%~99% | ✅ 已验收通过 |
| **Stage 13** | `M13.2` | 冲浪/分享内容去重池、内驱力满足回落（Satiation）与活动状态阅后即焚 | `STAGE_13_TEMPORAL_AWARENESS_AND_EXOGENOUS_AFFECT_PLAN.md` | `runtime/{scheduler,qzone_scheduler}.py`, `mind/facade.py` | Seen-BV Dedup + Drive Satiation Pass / Cov: 82%~97% | ✅ 已验收通过 |
| **Stage 13** | `M13.3` | 真实时间流逝情绪半衰期平复 + 外界冲浪信息对情绪与7维人格动态塑造引擎 | `STAGE_13_TEMPORAL_AWARENESS_AND_EXOGENOUS_AFFECT_PLAN.md` | `mind/{drives,plasticity}.py`, `runtime/scheduler.py` | 62/62 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.63% (91%)** | ✅ 已验收通过 |
| **Stage 14**<br>控制论自组织核心与智力放大 | `M14.1` | 协同学三磁针自组织核心（`OrderParameterCore`）与役使映射算子 | `STAGE_14_CYBERNETIC_SELF_ORGANIZATION_AND_INTELLIGENCE_AMPLIFICATION_PLAN.md` | `domain/models.py`, `mind/cybernetics.py`, `mind/frame_renderer.py` | 3-Needle Order Core Verified / Cov: 99%~100% | ✅ 已验收通过 |
| **Stage 14** | `M14.2` | Ashby 两级选矿智力放大器（5类认知选矿剂工具筛选 + HippoRAG 2跳记忆浮选） | `STAGE_14_CYBERNETIC_SELF_ORGANIZATION_AND_INTELLIGENCE_AMPLIFICATION_PLAN.md` | `mind/{cybernetics,ebbinghaus}.py`, `extensions/registry.py`, `runtime/agent_runner.py` | 2-Hop Flotation + Reagent Tool Filter Pass / Cov: 90%~99% | ✅ 已验收通过 |
| **Stage 14** | `M14.3` | A-MEM 卢曼卡片盒自组织记忆图式结晶器与控制台自组织核心仪表盘 | `STAGE_14_CYBERNETIC_SELF_ORGANIZATION_AND_INTELLIGENCE_AMPLIFICATION_PLAN.md` | `mind/{cybernetics,memory_consolidator}.py`, `web/mind_inspector_service.py`, `index.html`, `app.js` | 63/63 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.83% (91%)** | ✅ 已验收通过 |
| **Stage 15**<br>CodeGraph全图谱拓扑收敛 | `M15.1` | 消除 `runtime <---> adapters` 包级循环依赖并新增 AST 跨层门禁 | `STAGE_15_CODEGRAPH_TOPOLOGY_REMEDIATION_PLAN.md` | `domain/ports.py`, `runtime/scheduler.py`, `adapters/onebot/live_client.py`, `test_solid_boundaries.py` | `runtime -> adapters` Imports = 0 / AST Gate Pass | ✅ 已验收通过 |
| **Stage 15** | `M15.2` | 激活孤岛组件并网（`PrefixAnchorEngine`、`AsyncEventBus`、`Registry.facets/proposers`） | `STAGE_15_CODEGRAPH_TOPOLOGY_REMEDIATION_PLAN.md` | `adapters/onebot/live_client.py`, `core/bootstrap.py`, `runtime/{agent_runner,scheduler}.py` | All Orphan Nodes Connected in CodeGraph | ✅ 已验收通过 |
| **Stage 15** | `M15.3` | 统一 `_build_registry` 复合搜索、修复 `default_chat_key` 调用并忽略 `.codegraph/` | `STAGE_15_CODEGRAPH_TOPOLOGY_REMEDIATION_PLAN.md` | `core/bootstrap.py`, `web/mind_inspector_service.py`, `.gitignore` | 63/63 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.52% (91%)** | ✅ 已验收通过 |
| **Stage 16**<br>源码深层逻辑缺陷修复 | `M16.1` | 修复引用A同时`@B`被吞（`S16-01`）与同轮文字+语音双发重复回复（`S16-02`） | `STAGE_16_SOURCE_CODE_DEEP_AUDIT_AND_REMEDIATION_PLAN.md` | `adapters/onebot/{send_guard,bot_bridge}.py`, `runtime/agent_runner.py` | 3rd-Party `@` + Voice/Text Mutex Pass / Cov: 87%~100% | ✅ 已验收通过 |
| **Stage 16** | `M16.2` | 修复入站媒体 `message_id` 丢失（`S16-03`）与看图/看视频描述回写历史及缓存（`S16-04`） | `STAGE_16_SOURCE_CODE_DEEP_AUDIT_AND_REMEDIATION_PLAN.md` | `adapters/onebot/{event_parser,media_gateway}.py`, `tools/media_vision.py` | Media `message_id` + Caption Cache Writeback Pass | ✅ 已验收通过 |
| **Stage 16** | `M16.3` | 修复白名单私聊放行（`S16-05`）、引用他人防误唤醒（`S16-06`）、恒定前缀锚点（`S16-07`）与北京零点统计（`S16-08`） | `STAGE_16_SOURCE_CODE_DEEP_AUDIT_AND_REMEDIATION_PLAN.md` | `event_parser.py`, `enrichers.py`, `perceptual_gate.py`, `live_client.py`, `chat_service.py` | 64/64 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.61% (91%)** | ✅ 已验收通过 |
| **Stage 17**<br>热重载与启动状态同步闭环 | `M17.1` | 启动/查询时自动同步技能持久化状态（`S17-01`）与飞鱼语音配置实时热更新（`S17-02`） | `STAGE_17_FULL_SOURCE_DEEP_REMEDIATION_PLAN.md` | `web/{skill_config_service,app}.py`, `adapters/media/feiyu.py`, `main.py` | Skill State + Feiyu Hot-Reload Pass / Cov: 94%~98% | ✅ 已验收通过 |
| **Stage 17** | `M17.2` | 人设改名唤醒词热同步（`S17-05`）、视觉网关热重载（`S17-06`）与探针自组织核心补齐（`S17-03/04/07`） | `STAGE_17_FULL_SOURCE_DEEP_REMEDIATION_PLAN.md` | `enrichers.py`, `vision.py`, `llm_config_service.py`, `probe_service.py` | 65/65 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.63% (91%)** | ✅ 已验收通过 |
| **Stage 18**<br>多层转发、动态情敌与词条代谢 | `M18.1` | 合并转发与多层套娃转发聊天记录递归展开器（`forward_expander.py` + `read_forward`） | `STAGE_18_FORWARD_MESSAGES_DYNAMIC_RIVALS_AND_TRAIT_METABOLISM_PLAN.md` | `adapters/onebot/{forward_expander,event_parser,live_client}.py`, `tools/` | Multi-Level Forward Unpack Pass / Cov: 80%~88% | ✅ 已验收通过 |
| **Stage 18** | `M18.2` | 移除硬编码 `RIVALS`，改为从 `social_bonds (is_rival=1)` 动态读取情敌名单 | `STAGE_18_FORWARD_MESSAGES_DYNAMIC_RIVALS_AND_TRAIT_METABOLISM_PLAN.md` | `domain/ports.py`, `adapters/storage/memory_repo.py`, `mind/facade.py` | Zero Hardcoded Rivals / Dynamic `is_rival` Pass / Cov: 100% | ✅ 已验收通过 |
| **Stage 18** | `M18.3` | 性格词条（`persona_traits`）时间衰减、新陈代谢淘汰与控制台布局对齐 | `STAGE_18_FORWARD_MESSAGES_DYNAMIC_RIVALS_AND_TRAIT_METABOLISM_PLAN.md` | `adapters/storage/working_repo.py`, `runtime/scheduler.py`, `index.html` | 66/66 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.33% (90%)** | ✅ 已验收通过 |
| **Stage 19**<br>生物节律与连续深层记忆 | `M19.1` | Borbély 双过程连续生物节律、七相一日生活弧与 NHPP 随机抖动唤醒引擎 | `STAGE_19_BIOLOGICAL_CIRCADIAN_AND_CONTINUOUS_MEMORY_PLAN.md` | `mind/{circadian,drives,explorer}.py`, `adapters/onebot/live_client.py` | 7-Phase Circadian + NHPP Jitter Pass / Cov: 92%~100% | ✅ 已验收通过 |
| **Stage 19** | `M19.2` | 全息上下文记忆扩容与动态相关性事实浮选（28条事实 + 8张往事卡 + 提及群友档案） | `STAGE_19_BIOLOGICAL_CIRCADIAN_AND_CONTINUOUS_MEMORY_PLAN.md` | `mind/{ebbinghaus,frame_renderer,facade}.py` | Relevant Fact Flotation + Mentioned Bonds Pass / Cov: 97%~98% | ✅ 已验收通过 |
| **Stage 19** | `M19.3` | 跨轮次工作记忆延续缓冲池（`WorkingScratchpad`）、`recall_memory` 工具与 6 轮深度 ReAct | `STAGE_19_BIOLOGICAL_CIRCADIAN_AND_CONTINUOUS_MEMORY_PLAN.md` | `runtime/{working_scratchpad,agent_runner,prompt_composer}.py`, `tools/member_memory.py` | 67/67 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.55% (91%)** | ✅ 已验收通过 |
| **Stage 20**<br>零膨胀演化事实与唤醒雷达 | `M20.1` | 零新表演化事实双算子（候选印象二次印证转正 + 事实变更保留“此前曾是…” + 孤证睡眠清理） | `STAGE_20_LIGHTWEIGHT_EVOLVING_FACTS_AND_WAKE_RADAR_PLAN.md` | `adapters/storage/memory_repo.py`, `mind/{memory_consolidator,frame_renderer}.py`, `runtime/scheduler.py` | Candidate Promotion + Change History Pass / Cov: 92%~99% | ✅ 已验收通过 |
| **Stage 20** | `M20.2` | 实时生理清醒状态（清醒/犯困/深睡）与入站消息唤醒门控雷达（收到但未感兴趣/冷却/非对我说） | `STAGE_20_LIGHTWEIGHT_EVOLVING_FACTS_AND_WAKE_RADAR_PLAN.md` | `mind/{circadian,facade}.py`, `web/mind_inspector_service.py`, `index.html`, `app.js` | 68/68 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.57% (91%)** | ✅ 已验收通过 |
| **Stage 21**<br>群聊生态门控与水箱防漂移 | `M21.1` | 二人转60s免打扰、余音共鸣接话茬(带防双AI乒乓锁)、7维人格条件增益与雷达透明算式 | `STAGE_21_ECOLOGICAL_ATTENTION_GATE_AND_DRIFT_GUARD_PLAN.md` | `mind/{salience_hydraulics,perceptual_gate}.py` | Dyadic DND + Resonance Cap + Formula Radar Pass / Cov: 97% | ✅ 已验收通过 |
| **Stage 21** | `M21.2` | 洛伦兹水箱开口宣泄回落(-22)、非必回优雅闭嘴权与可塑性话痨度防漂移 | `STAGE_21_ECOLOGICAL_ATTENTION_GATE_AND_DRIFT_GUARD_PLAN.md` | `mind/{facade,plasticity}.py`, `runtime/{reply_rescue,agent_runner}.py` | 69/69 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.21% (90%)** | ✅ 已验收通过 |
| **Stage 22**<br>三吸引子好感动力学与回放根治 | `M22.1` | 三吸引子均值回归好感度引擎、主语指向消解、信任立方封顶与海马体慢通道关系复盘 | `STAGE_22_CALIBRATED_RELATIONAL_DYNAMICS_AND_TRACE_REPLAY_FIXES_PLAN.md` | `mind/{memory_consolidator,hippocampus,plasticity}.py` | Three-Attractor + Trust Cap + Hippocampus Bond Pass / Cov: 84%~95% | ✅ 已验收通过 |
| **Stage 22** | `M22.2` | 根治同行Bot 5分钟跟聊死循环、URL 域名污染与 3,235 条历史记录全量重放校准 | `STAGE_22_CALIBRATED_RELATIONAL_DYNAMICS_AND_TRACE_REPLAY_FIXES_PLAN.md` | `mind/{perceptual_gate,explorer,plasticity,memory_consolidator}.py` | 3,235-Msg Full Replay + Zero Benign False-Positives | ✅ 已验收通过 |
| **Stage 23**<br>跟聊无限续杯与二人转拦截根治 | `M23.1` | 根治日志 `#3450-#3480` 群聊跟聊窗口无限续杯、路人防抖误开窗、第三人插话熔断与二人转提权 | `STAGE_23_GROUP_FOLLOWUP_AND_BYSTANDER_INTERCEPTION_FIX_PLAN.md` | `mind/{perceptual_gate,salience_hydraulics,facade}.py`, `runtime/prompt_composer.py` | 71/71 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.37% (90%)** | ✅ 已验收通过 |
| **Stage 24**<br>HRRL稳态与DynAffect耦合情感 | `M24.1` | 独立人格普适权重（$w_{\text{care}} / w_{\text{aversion}}$）、HRRL 依恋重聚安抚、自由能 RPE 效价与普适三角吃醋 | `STAGE_24_AFFECTIVE_AND_DRIVE_AUDIT_AND_LITERATURE_SURVEY.md` | `mind/{drives,shadow_appraisal}.py` | HRRL Soothing + Triadic Jealousy + RPE Pass / Cov: 95%~96% | ✅ 已验收通过 |
| **Stage 24** | `M24.2` | `5×5` 情绪-驱力交叉耦合网络与 8 大下游子系统联动（在意好友门控偏爱、好友免冷暴力保护、表情包主导情绪） | `STAGE_24_AFFECTIVE_AND_DRIVE_AUDIT_AND_LITERATURE_SURVEY.md` | `mind/{salience_hydraulics,perceptual_gate,explorer,facade}.py`, `runtime/prompt_composer.py` | 72/72 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.37% (90%)** | ✅ 已验收通过 |
| **Stage 25**<br>潜意识6维和弦与去硬编码 | `M25.1` | 潜意识 6 维锚定和弦微探针（`SubconsciousChordProbe`）、微情绪染色、弦外之音與连续张量合成 | `STAGE_25_SUBCONSCIOUS_CHORD_PROBE_AND_ZERO_HARDCODING_PLAN.md` | `mind/subconscious_probe.py`, `mind/facade.py` | 64-Batch Replay + Chord Tensor Pass / Cov: 86%~98% | ✅ 已验收通过 |
| **Stage 25** | `M25.2` | 跨人情绪迁延余波、`“有回音”` 声学消歧、入站图片/表情包 MD5 缓存与自动视觉品味闭环 | `STAGE_25_SUBCONSCIOUS_CHORD_PROBE_AND_ZERO_HARDCODING_PLAN.md` | `adapters/onebot/enrichers.py`, `mind/frame_renderer.py`, `main.py` | 73/73 Tests Pass / Pylint 10.00/10 / **Total Cov: 90.18% (90%)** | ✅ 已验收通过 |

---

## 三、 变更与审计日志（Audit Trail）

- **`2026-10-28 15:39`**：完成立项与 **Stage 0 (`M0.1` ~ `M0.3`)** 全部契约定义及自动化门禁验收（Ruff 0 错误、Mypy Strict 15 文件全过、Pytest 7 项测试 100% 覆盖率通过）。输出 **Stage 1 (`M1.1` ~ `M1.4`)** 详细规划书待审阅。
