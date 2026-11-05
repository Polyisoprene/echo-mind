# EchoMind 文档索引（Docs Index）

> 最后更新：2026-11-05 · 文档已按用途重组为 8 个目录，共 96 份文档
>
> **阅读本文前请先明确一点**：项目里"设计了什么"与"实际做到了什么"是两件不同的事。
> 前者在 `models/`、`architecture/`，后者**只在 [`status/`](status/README.md)**。不要把设计文档当成已实现能力。

---

## 一、按角色选路径

| 我是谁 | 读这些 |
|---|---|
| **刚接手这个项目** | [`HANDOFF.md`](HANDOFF.md) → [`status/CURRENT_STATE.md`](status/CURRENT_STATE.md) → [`architecture/ARCHITECTURE_CONTRACTS.md`](architecture/ARCHITECTURE_CONTRACTS.md) |
| **要改业务代码** | [`architecture/ARCHITECTURE_CONTRACTS.md`](architecture/ARCHITECTURE_CONTRACTS.md) → 对应 `models/` 机制文档 → `tests/architecture/` |
| **要跑评测** | [`evaluation/README.md`](evaluation/README.md) → [`evaluation/EVALUATION_STANDARD.md`](evaluation/EVALUATION_STANDARD.md) |
| **要部署运维** | [`HANDOFF.md`](HANDOFF.md) 的运维章节 → [`operations/README.md`](operations/README.md) |
| **要查历史决策** | [`decisions/README.md`](decisions/README.md) → [`archive/plans/`](archive/plans/) |

---

## 二、目录总览

```text
docs/
├── HANDOFF.md          交接文档（环境/运维/代码地图/技术债）
├── architecture/       架构契约与工程流程          3 份
├── models/             认知核心与机制设计         12 份
├── evaluation/         评测标准与基准结果         22 份
├── research/           外部调研                    1 份
├── operations/         部署与运维                  1 份
├── status/             状态路标（活文档）          9 份
├── decisions/          技术决策记录                7 份
├── archive/            历史归档                   37 份
│   ├── plans/            STAGE 0–43 阶段计划      35 份
│   └── reviews/          代码评审报告              2 份
├── params/             参数溯源台账
└── capabilities.json   能力台账源数据
```

---

## 三、核心文档（最常被引用）

| 文档 | 作用 | 更新方式 |
|---|---|---|
| [`status/CURRENT_STATE.md`](status/CURRENT_STATE.md) | ⭐ 当前真实状态的**唯一权威** | 人工维护 |
| [`status/CAPABILITY_STATUS.md`](status/CAPABILITY_STATUS.md) | 能力台账（实现/部分/缺失/矛盾） | **自动生成**，改 [`capabilities.json`](capabilities.json) |
| [`architecture/ARCHITECTURE_CONTRACTS.md`](architecture/ARCHITECTURE_CONTRACTS.md) | 最高工程契约，由 AST 门禁强制 | 人工维护 |
| [`models/COGNITIVE_CORE_SPEC.md`](models/COGNITIVE_CORE_SPEC.md) | 12 层认知核心总规范 | 人工维护 |
| [`status/MASTER_BACKLOG.md`](status/MASTER_BACKLOG.md) | 总账：硬编码、待办、变更日志 | 人工维护 |
| [`params/README.md`](params/README.md) | 参数溯源台账（62 条常数） | 由 `param_gate.py` 校验 |

---

## 四、状态类文档怎么分工

`status/` 下文档较多，容易混淆。分工如下：

| 文档 | 回答的问题 |
|---|---|
| `CURRENT_STATE.md` | **现在系统是什么样**（数字、边界、已知问题） |
| `CAPABILITY_STATUS.md` | **每项能力达到什么程度**（机器生成，最客观） |
| `CLOSURE_MATRIX.md` | **哪些闭环了，哪些被外部资源卡住** |
| `MASTER_BACKLOG.md` | **还欠什么**（硬编码清单、技术债、变更日志） |
| `PROJECT_CHARTER.md` | **项目目标与全局进度** |
| `PERSONA_STATUS.md` / `PERSONA_SELF_EVOLUTION_STATUS.md` | **人格相关做到哪一步**（人话版） |
| `PARAMETER_SCORECARD.md` | **参数可信度**（哪些有依据、哪些是拍的） |
| `MEMORY_REFACTOR_STATUS.md` | **记忆模块重构进度**（部分已过时，以 CURRENT_STATE 为准） |

---

## 五、文档维护规范

1. **新增文档必须放进对应子目录**，`docs/` 根目录只允许 `README.md` 与 `HANDOFF.md`（由 `tests/architecture/test_docs_integrity.py` 强制）。
2. **移动或重命名文档后必须修正引用**，否则门禁会失败——这是有意的设计，防止链接静默腐化。
3. **归档而非删除**：过时的计划移入 `archive/` 并加「📦 已归档」横幅，保留可追溯性。
4. **状态类内容只写进 `status/`**，设计文档里不要写"当前已完成 XX"，避免两处数字打架。
5. **能力声明必须进台账**：新增能力请编辑 [`capabilities.json`](capabilities.json)，写明状态、缺口与验收测试，再跑 `python scripts/capability_gate.py` 重新生成。

---

## 六、本次重组说明（2026-11-05）

原 `docs/` 根目录平铺 56 份文档、`plans/` 平铺 35 份，命名混用 `_MODEL` / `_SPEC` / `_CN` / `D15_` / 日期后缀等多种风格，难以按用途查找。本次重组做了四件事：

1. **按用途分目录**：architecture / models / evaluation / research / operations / status / decisions / archive。
2. **统一命名**：去掉冗余后缀（如 `*_MODEL.md` → 主题名），`_CN` 后缀移除（全项目本就以中文为主），日期从文件名移入正文。
3. **归档历史**：35 份 STAGE 计划 + 2 份评审报告移入 `archive/`，每份加「已归档」横幅。
4. **加门禁防复发**：新增 `tests/architecture/test_docs_integrity.py`，强制链接有效、目录规范、归档有标注。

<div align="right"><a href="../README.md">← 返回项目主页</a></div>
