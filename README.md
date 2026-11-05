# EchoMind (`echomind`)

<p align="center">
  <img src="Ecomind.png" alt="EchoMind 看板娘" width="360">
</p>
<p align="center"><sub>EchoMind 看板娘</sub></p>

> **具备控制论「自组织核心（Order Parameter Core）」「两级选矿智力放大器（Selection Amplifier）」、真实人性阴影面、时间感知与神经可塑性自学习的认知型 QQ 智能体。**
> Python 3.12+ · 六边形清洁架构（Ports & Adapters）· NoneBot2 / OneBot v11

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Pylint 10.00/10](https://img.shields.io/badge/Pylint-10.00%2F10-brightgreen)](scripts/qa_gate.sh)
[![Mypy Strict](https://img.shields.io/badge/Mypy-100%25_Strict-blue)](scripts/qa_gate.sh)
[![Radon CC](https://img.shields.io/badge/Radon_CC-Grade_A%2FB-success)](scripts/qa_gate.sh)
[![Coverage ≥90%](https://img.shields.io/badge/Coverage-92%25-brightgreen)](scripts/qa_gate.sh)

---

## 一、 项目定位

传统 LLM 聊天机器人存在四类顽疾：**① 讨好型圣母病**（谁说都信、永远顺从）、**② 记忆散沙化与人设污染**（无结构堆积、旧设定污染新设定）、**③ 时间与外界失明**（看不见时间断层、不会自主调节情绪）、**④ 工具与记忆暴力检索**（无自组织核心与选择放大机制）。

EchoMind 基于 **控制论**（Ashby 智力放大器、Haken 协同学序参量）、**认知心理学**（CPM/OCC 情绪评估、Brehm 心理抗拒、艾宾浩斯遗忘曲线）与 **2024–2026 智能体记忆论文**（HippoRAG、A-MEM、CraniMem）构建，目标是做成一个"有脑子、有脾气、有时间感"的数字生命体，而不是一个应答器。

### 核心能力

| # | 能力 | 说明 |
|---|---|---|
| 1 | **控制论三磁针自组织核心** | 情绪／7 维性格／人际关系实时收敛为 3 根正交序参量：`ξ_stance ∈ [-1,1]`、`ξ_epistemic ∈ [0,1]`、`ξ_modality ∈ [0,1]`，据役使原理（Slaving Principle）对齐全局态势、动态采样温度与表达通道 |
| 2 | **两级选矿浮选放大器** | 第一级按 5 类"选矿剂"筛选工具子集；第二级做 HippoRAG 2-Hop 激活扩散记忆浮选；A-MEM 卡片盒在概念聚集时自动结晶为自组织图式 |
| 3 | **真实人性与三吸引子人际动力学** | 习得性厌恶雷点、语义饱和厌烦与心理逆反、15 分钟冷暴力、动机冲突型嘴硬；OU 均值回归好感度 + 海马体慢通道复盘，信任度三次方天花板 `Amax(trust) = 35 + 465·trust³` |
| 4 | **生物节律与时间感知** | Borbély 双过程睡眠-觉醒模型 + 非齐次泊松随机唤醒；上下文逐条标注 `[HH:MM]`，时间断层自动插入分段标记 |
| 5 | **工作记忆与主动检索** | MemGPT 式 20 分钟滚动工作笔记、28 条动态事实浮选、8 张海马体往事召回、`recall_memory` 主动翻找、6 轮 ReAct 循环 |
| 6 | **真语音与全曲翻唱** | CosyVoice3 主动发语音（含同轮文字/语音互斥锁）；点歌时 B 站取音轨 → HDemucs 分离 → RVC 换声合成整首 |
| 7 | **合并转发与演化事实** | 4 层嵌套合并转发递归解包；零膨胀演化事实双算子（候选 0.58 → 印证转正 0.85 → 24h 孤证清理） |

> 更完整的机制设计见 [`docs/models/README.md`](docs/models/README.md)，能力边界的**唯一权威**见 [`docs/status/CURRENT_STATE.md`](docs/status/CURRENT_STATE.md) 与 [`docs/status/CAPABILITY_STATUS.md`](docs/status/CAPABILITY_STATUS.md)。

---

## 二、 架构全景

依赖方向严格**由外向内**：`web/ · adapters/ → runtime/ · tools/ · extensions/ → mind/ → domain/`

```text
src/echomind/
├── domain/          # Layer 0 领域契约：不可变值对象 + 窄接口 Protocol（≤5 方法），零第三方依赖
├── mind/            # Layer 1 认知核心：注意路由/工作记忆/五维记忆/内驱力/海马体/可塑性
├── runtime/         # Layer 2 会话运行时：并发调度、Agent 工具循环、Prompt 装配
├── tools/           # Layer 3 效应器：无状态工具（发消息/查群员/看图/搜索/B站/语音）
├── extensions/      # Layer 3 微内核扩展槽：sensor / tool / facet / proposer / panel
├── adapters/        # Layer 4 基础设施：OneBot 桥接、SQLite 仓储、LLM 网关、媒体
├── web/             # Layer 5 表现层：FastAPI 控制台 + SSE
└── core/            # Layer 5 组合根：bootstrap 依赖注入装配、配置加载
```

这些边界**不是文档承诺，而是 CI 硬门禁**：[`tests/architecture/test_solid_boundaries.py`](tests/architecture/test_solid_boundaries.py) 用 AST 强制单文件 ≤300 行、单函数 ≤40 行、控制流嵌套 ≤2 层、`domain/` 与 `mind/` 零基础设施导入、所有领域模型 `frozen=True`。

> 完整契约（SOLID、LoD、扁平化四原则、值对象清单）见 [`docs/architecture/ARCHITECTURE_CONTRACTS.md`](docs/architecture/ARCHITECTURE_CONTRACTS.md)。

---

## 三、 快速开始

### 1. 环境准备

```bash
# 需要 Python 3.12+ 与 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/Polyisoprene/echo-mind.git
cd echo-mind
uv sync                                    # 安装运行期 + 开发期依赖

cp .env.example .env                       # 运行期开关
# 编辑 data/config.json 填入 LLM 网关、QQ 账号、群号等（见下节）
```

### 2. 最小配置

| 配置项 | 位置 | 说明 |
|---|---|---|
| LLM 网关 | `data/config.json` → `api.baseUrl` / `api.apiKey` / `api.model` | OpenAI 兼容端点；可配 `fallbackModels` 实现自动故障转移 |
| 向量模型 | `data/config.json` → `api.embeddingBaseUrl` | 默认本地 `http://127.0.0.1:8010`（bge-m3, 1024 维）；留空则语义检索降级 |
| 语音服务 | `data/config.json` → `feiyuVoice.baseUrl` | 远端 CosyVoice3 服务；不可用时语音工具自动不可用，不影响文字链路 |
| QQ 账号 / 群 | `data/config.json` → `selfQq` / `allowedGroups` / `operatorIds` | OneBot 侧账号与准入白名单 |
| 控制台令牌 | `data/config.json` → `server.token` | **留空时 `/api` 仅允许 loopback 访问**（fail-closed，不会意外开放公网） |

运行期开关（`.env`）：

```bash
ECHOMIND_SATIATION=shadow       # 社交习惯化 off | shadow | on
ECHOMIND_THINKING=on            # 思考通道 on | off
ECHOMIND_REASONING_EFFORT=low   # low | high | max
FACTS_V2_WRITE=1                # 事实双写（claims/evidence 影子库）
```

### 3. 启停

```bash
./scripts/service.sh start      # 后台启动（默认 0.0.0.0:3310）
./scripts/service.sh status     # 查看状态
./scripts/service.sh restart    # 改代码/配置后重启
./scripts/service.sh stop       # 停止
./scripts/service.sh log 100    # 追最后 100 行日志
```

> **多实例**：通过 `ECHOMIND_INSTANCE=xiaomo` 可运行第二套实例，会读取 `.env.xiaomo` 并使用 `data-xiaomo/` 数据目录与独立端口，与主实例隔离。

### 4. Web 控制台

浏览器打开 `http://127.0.0.1:3310`，可查看生理觉醒状态、唤醒门控雷达、记忆检查器、人格参数、技能开关与 LLM 配置。

---

## 四、 质量门禁

一条命令跑完全部工业级门禁：

```bash
./scripts/qa_gate.sh
```

| 门禁 | 工具 | 标准 | 当前 |
|---|---|---|---|
| 1A 静态检查 | `ruff check src tests` | PEP8、行宽 ≤100、`C901 ≤ 6`、`SIM/RET/C4/PLR` | ✅ 0 errors |
| 1B 复杂度 | `radon cc src -nc` | 无 Grade C 及以下 | ✅ 0 |
| 1C 反嵌套 | `pylint src/echomind` | `max-nested-blocks ≤ 2` | ✅ 10.00/10 |
| 2 类型 | `mypy --strict src` | 203 文件 100% 严格 | ✅ 0 issues |
| 2B 参数台账 | `scripts/param_gate.py` | 每个可调常数须声明来源 | ✅ 62/62 |
| 2C 能力台账 | `scripts/capability_gate.py --check` | 能力状态与验收测试对账 | ✅ 27 项 |
| 3 架构边界 | `tests/architecture/*` | 分层/SOLID/扁平化/文档完整性 | ✅ passed |
| 4 测试 | `pytest --cov` | ≥90% 覆盖率 | ✅ 444 passed / 92% |

> 新增 `tests/architecture/test_docs_integrity.py`：**文档链接有效性**也是门禁——重命名或移动文档若不同步修正引用，测试会失败。文档重组不再能静默破坏交叉引用。

---

## 五、 文档地图

文档已按用途分目录，**入口是 [`docs/README.md`](docs/README.md)**。

```text
docs/
├── README.md            # 文档总索引（从这里开始）
├── HANDOFF.md           # 交接文档：环境、运维、代码地图、技术债
├── architecture/        # 架构契约、红绿交付、数据迁移
├── models/              # 认知核心、人格、记忆等机制设计
├── evaluation/          # 评测标准 + LongMemEval / GroupMemBench / CharacterEval 结果
├── research/            # 调研
├── operations/          # 部署与运维（embedding 等）
├── status/              # 【活文档】当前状态、能力台账、总账、路标
├── decisions/           # 技术决策记录（D11/D14/D15/P0）
├── archive/             # 历史归档：plans（35 份 STAGE 计划）、reviews（评审报告）
├── params/              # 参数溯源台账
└── capabilities.json    # 能力台账源数据
```

**先读这三份**：

1. [`docs/HANDOFF.md`](docs/HANDOFF.md) — 接手必读：怎么跑起来、怎么运维、代码从哪看、有哪些坑
2. [`docs/status/CURRENT_STATE.md`](docs/status/CURRENT_STATE.md) — 现在到底做到了什么、边界在哪
3. [`docs/architecture/ARCHITECTURE_CONTRACTS.md`](docs/architecture/ARCHITECTURE_CONTRACTS.md) — 改代码前必须遵守的硬约束

---

## 六、 已知边界

项目对自身能力边界采取**诚实标注**，不做"已完成"粉饰。[`docs/capabilities.json`](docs/capabilities.json) 中 27 项能力当前为：**12 项 implemented、12 项 partial、3 项 contradicted**。

3 项标注为矛盾（文档声称与实现不符）的能力，是已知且有意保留的已知项：

- `CAP-HEXACO`：7 维人格与 HEXACO 六轴无映射矩阵
- `CAP-ZERO-LEXICON`：`mind/` 下仍有中文词表与正则
- `CAP-OPERATOR-NO-PRIVILEGE`：群主在关系计算中确有特权

具体缺陷与技术债见 [`docs/HANDOFF.md`](docs/HANDOFF.md) 的「已知缺陷」章节。

---

## 七、 许可与致谢

本项目为个人研究与学习用途。感谢 NoneBot2、OneBot、HippoRAG、A-MEM、CosyVoice3、RVC 等开源项目。

<div align="right"><a href="#echomind-echomind">↑ 回到顶部</a></div>
