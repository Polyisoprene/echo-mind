# 🧠 EchoMind (`echomind`)

> **具备控制论「自组织核心（Order Parameter Core）」、「两级选矿智力放大器（Selection Amplifier）」、真实人性阴影面、时间感知与神经可塑性自学习的下一代认知型 QQ 智能体（Python 3.12+ / 六边形清洁架构）**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Pylint 10.00/10](https://img.shields.io/badge/Pylint-10.00%2F10-brightgreen)](scripts/qa_gate.sh)
[![Mypy Strict](https://img.shields.io/badge/Mypy-100%25_Strict-blue)](scripts/qa_gate.sh)
[![Radon CC](https://img.shields.io/badge/Radon_CC-Grade_A%2FB-success)](scripts/qa_gate.sh)
[![Coverage >90%](https://img.shields.io/badge/Coverage-91%25-brightgreen)](scripts/qa_gate.sh)

---

## 一、 项目简介与核心突破

传统的 LLM 聊天机器人往往存在四大顽疾：**① 讨好型圣母病（Sycophancy Bias，谁说都信、永远顺从）**、**② 记忆散沙化与人设污染（无结构堆积、旧设定污染新设定）**、**③ 时间与外界失明（看不见时间断层、不会自主上网冲浪调节心情）**、**④ 工具与记忆暴力检索（无自组织核心与选择放大机制）**。

**EchoMind** 基于 **控制论（Ashby 智力放大器 & Haken 协同学序参量）**、**认知心理学（CPM/OCC 情绪评估、Brehm 心理抗拒、艾宾浩斯遗忘曲线）** 以及 **2024–2026 前沿智能体记忆论文（HippoRAG、A-MEM、CraniMem）**，采用严格的 **六边形清洁架构（Ports & Adapters）** 构建了一个真正“有脑子、有脾气、有时间感、会自己刷 B 站和唱整首歌”的数字生命体：

1. **🧭 控制论三磁针自组织核心（Haken Order Parameter Core）**：
   - 将复杂的情绪、7 维性格与人际关系实时收敛为 **3 根正交的宏观序参量主磁针**：`社交姿态核 ξ_stance ∈ [-1,+1]`、`认知求真核 ξ_epistemic ∈ [0,1]`、`声情模态核 ξ_modality ∈ [0,1]`；
   - 通过协同学**役使原理（Slaving Principle）**，拨动 3 根主磁针即可自动对齐全局认知态势（如 `🎙️ 亲昵声情共鸣态`、`🛡️ 审慎防忽悠核查态`、`💢 刺头防御呛声态`）、动态采样温度与表达通道。
2. **🔬 两级选矿浮选智力放大器（Ashby Selection Amplifier × HippoRAG × A-MEM）**：
   - **第一级放大（5 类认知选矿剂动态筛选工具）**：先在小范围内选定本轮激活的“选矿剂”（`日常轻装剂` / `多模态鉴赏剂` / `百科求真剂` / `声情共鸣与点歌剂` / `社交防忽悠核查剂`），再按需挂载工具子集；
   - **第二级放大（HippoRAG 2-Hop 激活扩散记忆浮选）**：以直接命中卡片的概念锚点作为次级选矿剂种子，在情景记忆网中进行 2 跳扩散，自动浮选出字面未提及但深层关联的往事；
   - **A-MEM 卢曼卡片盒自组织图式结晶**：当多段经历围绕同一核心概念聚集时，海马体自动将其结晶为 `自组织图式:<核心概念>`。
3. **🎭 突破“讨好型圣母病”的真实人性、三吸引子人际动力学与三维动态可信度**：
   - 具备 **习得性厌恶雷点（Disgust/Aversion）**、**语义饱和厌烦与心理逆反（Reactance）**、**15 分钟冷暴力已读不回（Silent Treatment）** 以及 **四大动机冲突型嘴硬/小谎言策略（DePaulo 1996）**；
   - **三吸引子均值回归好感度引擎（Ornstein-Uhlenbeck）× 海马体慢通道关系复盘**：区分同行对手均衡点（`45.0`）、邓巴日常熟人天花板（`85.0`）与深度共鸣挚友区，叠加信任度三次方天花板 $A_{\max}(\text{trust}) = 35 + 465 \cdot \text{trust}^3$，杜绝字数打卡刷好感与甜言蜜语洗白失信；
   - **🧠 潜意识 6 维情感和弦探针（`SubconsciousChordProbe`）× 连续人格关系张量合成（Stage 24–25）**：采用 Goffman 多方对话语用五分类与 6 维锚定和弦（`joy, hurt, jealousy, shyness, annoyance, curiosity ∈ 0..3`），融合独立人格普适在乎度 $w_{\text{care}}(u)$、HRRL 稳态重聚安抚、跨人情绪迁延余波（Affective Spillover）与入站表情包 MD5 自动视觉品味。
4. **⏱️ Borbély 双过程生物节律、七相一日生活弧与外源情绪/人格塑造**：
   - 基于 **Borbély 双过程睡眠-觉醒调节模型**（24h 正弦主节律 + `13:30` 午困高斯低谷 + `00:30–07:00` 深度睡眠态）与 **非齐次泊松过程（NHPP）随机抖动唤醒**，彻底告别机械秒表式触发；
   - 上下文逐条标注北京时间 `[HH:MM]`，相邻消息间隔 $\ge 5$ 分钟自动插入 `── ⏱️ [时间断层：旧话题已翻篇] ──`；闲暇自主刷 B 站热门榜（`bili_popular`）或查热梗（`web_search`）不仅更新知识库，还会动态提升愉悦度并微调 7 维性格参数。
5. **🧩 MemGPT 式跨轮次工作记忆延续缓冲（`WorkingScratchpad`）与主动深层记忆检索（`recall_memory`）**：
   - 自动维护 20 分钟滚动工作笔记（缓存前几轮刚调用的查群成员/搜网页/看图/刷B站/查记忆工具结果与上一轮自身话锋），结合 28 条动态相关性事实浮选、8 张海马体往事召回、`recall_memory` 主动翻找工具与 6 轮深度 ReAct 循环，彻底消除跨轮失忆与单轮机械感。
6. **🎤 飞鱼 GPU 真语音主动表达与带伴奏全曲 AI 翻唱（`feiyu_say` & `feiyu_cover`）**：
   - 情绪饱满或亲昵互动时主动开口发 QQ 真语音（CosyVoice3，且具备同轮文字/语音防重互斥锁）；
   - 点歌时自动从 B 站检索原曲提取 DASH `.m4a` 音轨，上传 GPU 节点执行 HDemucs 人声伴奏分离 + RVC 换声混音，直接发出整首带伴奏翻唱语音。
7. **📨 多层套娃合并转发递归解包、零膨胀演化事实双算子与实时清醒/门控雷达**：
   - 支持**最高 4 层套娃嵌套合并转发聊天记录**入站自动递归展开与按需调用 `read_forward` 技能展开（含提取转发内嵌图片）；
   - **零膨胀演化事实双算子**：非主人首次陈述以候选印象（`confidence=0.58`）入库、二次印证自动转正（`0.85`）、24h 孤证噪音睡眠自动清理，且同主题事实变更自动附注 `（此前曾是：…）`；
   - **📡 实时听觉与唤醒门控雷达**：控制台顶栏与总览页实时展示回音生理觉醒状态（`🟢 清醒活跃` / `🟡 犯困慵懒` / `💤 深度睡眠中`）及最近 25 条入站消息的唤醒判定与忽略原因。

---

## 二、 架构全景与目录结构（Hexagonal Clean Architecture）

项目严格遵循 **SOLID 原则** 与 **单向依赖反转（`Web/Adapters/Runtime/Tools` $\rightarrow$ `Mind` $\rightarrow$ `Domain`）**，通过 AST 架构测试强制保证 `domain/` 与 `mind/` **零基础设施导入（Zero Infrastructure Imports）**：

```text
echo-mind/
├── src/echomind/
│   ├── domain/                  # 【领域契约层】纯不可变值对象 (FrozenValueObject) 与窄接口协议 (<=5方法/Port)
│   │   ├── models.py            # Percept, AffectiveVector, DriveState, CyberneticCoreState, CognitiveFrame...
│   │   └── ports.py             # ILlmGateway, IMemoryReader/Writer, IVoiceBackend, ISongCoverBackend, IBiliClient...
│   ├── mind/                    # 【13层认知核心层】纯函数与确定性状态机（零 I/O 库依赖）
│   │   ├── cybernetics.py       # 🧭 协同学三磁针序参量核心 + HippoRAG 2跳记忆浮选 + A-MEM 自组织图式结晶
│   │   ├── perceptual_gate.py   # 第2层：丘脑四级显著性门控与 15 分钟冷暴力已读不回闸门
│   │   ├── ebbinghaus.py        # 第4层：艾宾浩斯双层记忆保持率衰减与关联浮选召回
│   │   ├── drives.py            # 第5层：情绪半衰期时间衰减、昼夜节律、吃醋检测与外源冲浪情绪更新
│   │   ├── epistemic.py         # 第6层：元认知防忽悠事实冲突检测与发言人可信度加权校准
│   │   ├── shadow_appraisal.py  # 第7~8层：OCC/CPM 厌恶雷点、Brehm 心理逆反与四大策略性撒谎决策器
│   │   ├── explorer.py          # 第9层：闲暇自主求知、刷B站与主动搭话仲裁器
│   │   ├── hippocampus.py       # 第10层：海马体批量对话归纳与记忆晋升解析
│   │   ├── memory_consolidator.py # 社交亲密度/动态信任度演化与海马体批处理巩固
│   │   ├── personality.py       # 第11层：HEXACO × Attachment 7 维性格语义锚点标尺与特征涌现
│   │   ├── plasticity.py        # 第12层：稳态边界阻尼神经可塑性自调优（群聊反馈 + 外源冲浪双驱动）
│   │   ├── persona_reconciler.py # 零硬编码的人设-记忆认识论冲突消解器（Epistemic Reconciler）
│   │   ├── frame_renderer.py    # 认知核心状态块渲染器（含实时北京时钟与主动语音/歌唱冲动）
│   │   └── facade.py            # 统一外观入口 CognitiveCoreFacade（遵循迪米特法则 LoD）
│   ├── runtime/                 # 【运行时编排层】
│   │   ├── agent_runner.py      # 多轮工具调用循环、实时 running 流式轨迹同步、未发回复抢救
│   │   ├── prompt_composer.py   # 前缀 KV-Cache 锚定、表情包冷却轮换、时间断层分割线组装
│   │   ├── scheduler.py         # 5分钟认知心跳、已看内容去重池、自主刷B站/查梗与睡眠修剪
│   │   └── qzone_scheduler.py   # 空间说说、个性签名与多目标（多群/多人/群内@某人）主动日常调度
│   ├── extensions/              # 【五槽位微内核插件注册表】
│   │   └── registry.py          # 传感器 / 工具(含选矿剂动态筛选) / 认知切面 / 主动提案器 / 监控面板
│   ├── tools/                   # 【19项运行时工具集（保持人设无关性 Persona-Agnostic）】
│   │   ├── messaging_and_group.py # send_message, send_sticker, send_poke, get_group_members
│   │   ├── voice_tools.py       # feiyu_say (TTS亲口说话), feiyu_cover (全曲AI翻唱), read_voice
│   │   ├── bili.py              # bili_search, bili_video, bili_popular (带完整可点击链接)
│   │   ├── cnmeme_wiki.py       # meme_wiki (ETag 缓存网络热梗百科)
│   │   ├── explore_and_voice.py # web_search (梗百科 + B站复合容错搜索), memory_append
│   │   ├── media_vision.py      # look_at_image (含动图2×2四格分镜+描述回写), watch_video
│   │   └── qzone_and_profile.py # qzone_publish, profile_signature (含多目标主动消息配置)
│   ├── adapters/                # 【外部基础设施适配器层】
│   │   ├── onebot/              # OneBot v11 桥接、4层套娃转发展开器(forward_expander)、防双@守卫
│   │   ├── llm/                 # 多服务商有序 N 级故障转移网关 (FailoverLlmGateway) 与前缀锚定
│   │   ├── media/               # 飞鱼 GPU 语音/全曲翻唱客户端、B站 WBI 签名与音轨提取、多模态视觉
│   │   └── storage/             # SQLite 异步 WAL 仓储 (memory_repo, working_repo, trace_repo...)
│   └── web/                     # 【FastAPI 全息心智控制台 (Port 3310)】
│       ├── app.py               # REST API 路由、NapCat 在线探测、静态资源防缓存与远程鉴权中间件
│       └── static/              # 零构建响应式控制台 (支持昼夜主题切换、流式会话、多服务商模型中心)
├── docs/                        # 架构契约、认知科学规范与 Stage 0 ~ Stage 18 全套工程设计文档
├── scripts/                     # qa_gate.sh (7道门禁) 与 service.sh (后台守护进程管理)
└── tests/                       # 66 项架构边界测试、属性模糊测试 (Hypothesis)、单元与集成测试
```

---

## 三、 快速开始与日常运维

### 1. 环境准备
本项目使用 [`uv`](https://docs.astral.sh/uv/) 管理 Python 3.12+ 虚拟环境与依赖：

```bash
# 安装依赖并同步虚拟环境
uv sync --all-extras

# 复制配置模板并填入你的 NapCat OneBot 地址与大模型网关 Key
cp data/config.example.json data/config.json
```

### 2. 启停与守护服务管理（`./scripts/service.sh`）

```bash
# 启动后台守护服务（默认监听 http://0.0.0.0:3310）
./scripts/service.sh start

# 重启服务（修改代码或配置后一键热重启）
./scripts/service.sh restart

# 查看运行状态与实时日志
./scripts/service.sh status
./scripts/service.sh logs

# 停止服务
./scripts/service.sh stop
```

### 3. 全息 Web 控制台（`http://127.0.0.1:3310`）
浏览器打开 `http://127.0.0.1:3310`（支持右上角 **☀️ 白天 / 🌙 夜间模式** 一键切换）：
- **📊 总览（Overview）**：实时查看情绪五维、内驱力四维、**🧭 控制论三磁针自组织核心与激活选矿剂**、**🔭 自主网页搜索与刷B站冲浪足迹**（可一键点击「🔭 立即去刷B站 / 探索未知新梗」）；
- **⚡ 会话（Sessions）**：支持「⚡ 轮次会话」（实时显示 `⚡ 运行中…` 流式步骤、携带上下文条数、完整 System/User Prompt 与模型推理耗时）与「💬 聊天存档」无缝切换；
- **🧠 记忆（Memory）**：管理情景记忆卡片（带艾宾浩斯实时保持率）、语义事实防忽悠锁（含 `自组织图式:*`）、条件反射规则与群友亲密度/动态可信度账本；
- **🌱 性格（Personality）**：实时编辑人设卡片、一键运行 **「🧹 扫描并清理冲突旧记忆（LLM 认识论消解器）」**、手动微调 7 维性格滑块并查看可塑性演化日志；
- **🛠️ 技能（Skills）**：探针检测飞鱼 GPU 语音服务状态、开关任意技能、使用**可视化多目标编辑器**配置空间说说与多群/多人主动发消息目标；
- **🤖 模型（Models）**：管理**多家大模型服务商注册表（Providers Registry）**与**有序多级故障转移备用模型链（N-Fallback Chain）**。

---

## 四、 工业级 7 道自动化质量门禁（`./scripts/qa_gate.sh`）

任何代码变更在合入前均须通过 `./scripts/qa_gate.sh` 的全套静态与动态检查：

```bash
./scripts/qa_gate.sh
```

| 门禁编号 | 检查工具 | 硬性工程标准 | 当前状态 |
|---|---|---|---|
| **Gate 1A** | `ruff check src tests` | PEP8、`line-length <= 100`、圈复杂度 `C901 <= 6`、`SIM/RET/C4/PLR` | ✅ **0 Errors** |
| **Gate 1B** | `radon cc src -nc` | 所有函数/方法 Radon 圈复杂度必须为 **Grade A 或 B**（严禁 Grade C~F） | ✅ **0 Functions > B** |
| **Gate 1C** | `pylint src/echomind` | 强制扁平化代码 `max-nested-blocks <= 2`，满分要求 | ✅ **10.00 / 10** |
| **Gate 2** | `mypy --strict src tests` | 90 个源文件与测试文件 100% 严格静态类型与协议校验 | ✅ **0 Issues** |
| **Gate 3** | `test_solid_boundaries.py` | 单文件 `<= 300` 行、单函数 `<= 40` 行、窄接口 `<= 5` 方法、零跨层依赖 | ✅ **All Passed** |
| **Gate 4** | `pytest --cov=src/echomind` | 73 项单元/属性/集成测试全绿，整体代码覆盖率 `>= 90%` | ✅ **73 Passed (>90% Cov)** |

---

## 五、 架构规范与阶段演进文档索引

- **顶层架构契约**：
  - [docs/PROJECT_CHARTER_AND_PROGRESS.md](docs/PROJECT_CHARTER_AND_PROGRESS.md) —— 项目工程宪章与 Stage 0 ~ Stage 18 全景进度追踪总表
  - [docs/ARCHITECTURE_CONTRACTS.md](docs/ARCHITECTURE_CONTRACTS.md) —— 六边形架构、SOLID 边界与零嵌套代码规范
  - [docs/COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md](docs/COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md) —— 认知核心、人性阴影面与神经可塑性自学习规范
- **各阶段详细工程设计规范（`docs/plans/`）**：
  - [Stage 7：全局 19 项缺陷建模与修复规范](docs/plans/STAGE_7_GLOBAL_REMEDIATION_PLAN.md)
  - [Stage 8：7 维性格语义标尺、全息会话可观测性与昼夜主题规范](docs/plans/STAGE_8_CONSOLE_AND_PERSONA_SEMANTICS_PLAN.md)
  - [Stage 9：零硬编码人设-记忆认识论冲突消解架构规范](docs/plans/STAGE_9_ANTI_PERSONA_POLLUTION_PLAN.md)
  - [Stage 10：三维动态可信度校准（Epistemic Trust Calibration）架构规范](docs/plans/STAGE_10_DYNAMIC_TRUST_CALIBRATION_PLAN.md)
  - [Stage 11：NapCat 在线探测、实时流式会话状态机与多服务商多级故障转移中心](docs/plans/STAGE_11_LIVE_SESSION_AND_MULTI_PROVIDER_LLM_PLAN.md)
  - [Stage 12：主动语音表达决策、飞鱼全曲 AI 翻唱与自主刷 B 站冲浪引擎](docs/plans/STAGE_12_VOICE_SINGING_AND_AUTONOMOUS_SURFING_PLAN.md)
  - [Stage 13：全链路时间流逝感知、防重复分享去重与外源情绪/人格演化引擎](docs/plans/STAGE_13_TEMPORAL_AWARENESS_AND_EXOGENOUS_AFFECT_PLAN.md)
  - [Stage 14：控制论「自组织核心（Order Parameter Core）」与「两级选矿智力放大器」架构规范](docs/plans/STAGE_14_CYBERNETIC_SELF_ORGANIZATION_AND_INTELLIGENCE_AMPLIFICATION_PLAN.md)
  - [Stage 15：CodeGraph 全图谱拓扑收敛、跨层解耦与孤岛组件并网规范](docs/plans/STAGE_15_CODEGRAPH_TOPOLOGY_REMEDIATION_PLAN.md)
  - [Stage 16：源码逐行审计与 8 项运行态逻辑 Bug 全局修复规范](docs/plans/STAGE_16_SOURCE_CODE_DEEP_AUDIT_AND_REMEDIATION_PLAN.md)
  - [Stage 17：Web 与运行时配置热重载闭环与启动状态同步规范](docs/plans/STAGE_17_FULL_SOURCE_DEEP_REMEDIATION_PLAN.md)
  - [Stage 18：多层套娃转发递归展开、动态情敌解耦与性格词条新陈代谢规范](docs/plans/STAGE_18_FORWARD_MESSAGES_DYNAMIC_RIVALS_AND_TRAIT_METABOLISM_PLAN.md)
  - [Stage 19：Borbély 双过程生物节律、跨轮次工作记忆延续缓冲与深层主动记忆检索规范](docs/plans/STAGE_19_BIOLOGICAL_CIRCADIAN_AND_CONTINUOUS_MEMORY_PLAN.md)
  - [Stage 20：零膨胀演化事实双算子与实时清醒/注意力门控雷达规范](docs/plans/STAGE_20_LIGHTWEIGHT_EVOLVING_FACTS_AND_WAKE_RADAR_PLAN.md)
  - [Stage 21：群聊生态感知门控、二人转免打扰、余音共鸣、洛伦兹水箱回落与可塑性防漂移规范](docs/plans/STAGE_21_ECOLOGICAL_ATTENTION_GATE_AND_DRIFT_GUARD_PLAN.md)
  - [Stage 22：三吸引子均值回归人际动力学、海马体慢通道关系复盘与回放缺陷根治规范](docs/plans/STAGE_22_CALIBRATED_RELATIONAL_DYNAMICS_AND_TRACE_REPLAY_FIXES_PLAN.md)
  - [Stage 23：群聊跟聊窗口无限续杯与路人防抖误开窗根治规范](docs/plans/STAGE_23_GROUP_FOLLOWUP_AND_BYSTANDER_INTERCEPTION_FIX_PLAN.md)
  - [Stage 24：全认知状态空间（24维变量）专项审计、文献调研与全耦合动力学重构规范](docs/plans/STAGE_24_AFFECTIVE_AND_DRIVE_AUDIT_AND_LITERATURE_SURVEY.md)
  - [Stage 25：潜意识6维情感和弦探针、连续张量合成、跨人情绪迁延与表情包自动品味规范](docs/plans/STAGE_25_SUBCONSCIOUS_CHORD_PROBE_AND_ZERO_HARDCODING_PLAN.md)
  - [Stage 26：全链路100%潜意识6维和弦驱动与全库硬编码词表清零规范](docs/plans/STAGE_26_PURE_SUBCONSCIOUS_CHORD_ENGINE_AND_ZERO_LEXICON_PLAN.md)
