# EchoMind 文档索引（Docs Index）

> 最后更新：2026-10-30（Stage 30 完成后）
> 本文件是文档的**唯一入口**。历史阶段规划书是记录，不再修改；"现行契约"以标注 ✅ 的文档为准。

---

## 一、 先读这四份（现行有效）

| 文档 | 作用 | 何时更新 |
|---|---|---|
| [`MASTER_BACKLOG.md`](MASTER_BACKLOG.md) | **单一事实源**：硬编码清单、待办、分支状态、变更日志 | 每次改动后 |
| [`ARCHITECTURE_CONTRACTS.md`](ARCHITECTURE_CONTRACTS.md) | 分层边界、SOLID 硬约束、领域契约、7 道门禁、**人格模型契约（§八）** | 架构或契约变化时 |
| [`CONTRACT_RED_GREEN_AND_AB_LANES.md`](CONTRACT_RED_GREEN_AND_AB_LANES.md) | 红绿交付 RGR-01~10、A/B 双线 AB-01~11 | 交付纪律变化时 |
| [`PROJECT_CHARTER_AND_PROGRESS.md`](PROJECT_CHARTER_AND_PROGRESS.md) | 立项书 + 全阶段进度总表 + 当前工程状态 | 每阶段验收后 |
| [`params/ledger.json`](params/ledger.json) + [`params/README.md`](params/README.md) | **参数溯源台账**：每个可调常数的 src/data/convention/fit_pending 分类与证据 | 每次改常数时（门禁强制） |
| [`capabilities.json`](capabilities.json) + [`CAPABILITY_STATUS.md`](CAPABILITY_STATUS.md) | **能力台账**：每个功能声明的实现状态、缺口与验收测试（状态表自动生成） | 每次功能变更时 |

## 二、 设计与专项说明（按主题）

| 文档 | 内容 |
|---|---|
| [`COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md`](COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md) | 12 层认知核心、7 维人格、记忆与门控的算法说明 |
| [`DATA_MIGRATION_GUIDE.md`](DATA_MIGRATION_GUIDE.md) | 外部数据导入、表结构契约、**Stage 29–30 新增表/列** |
| [`plans/STAGE_30_PERSONALITY_MODEL_REMEDIATION_PLAN.md`](plans/STAGE_30_PERSONALITY_MODEL_REMEDIATION_PLAN.md) | 人格模型全局重构：不变量、目标模型、分阶段与验收（含 §9 落地记录） |
| [`plans/STAGE_29_IDENTITY_DECOUPLING_AND_BOND_DEPTH_PLAN.md`](plans/STAGE_29_IDENTITY_DECOUPLING_AND_BOND_DEPTH_PLAN.md) | 关系深度六项模型、身份解耦、参数溯源 |
| [`plans/STAGE_28_AB_LANE_REMEDIATION_AND_EVALUATION_PLAN.md`](plans/STAGE_28_AB_LANE_REMEDIATION_AND_EVALUATION_PLAN.md) | 缺陷影响建模、修复后评估判据、A/B 双线 |
| [`plans/STAGE_31_BOT_AWARENESS_AND_SOCIAL_SATIATION_PLAN.md`](plans/STAGE_31_BOT_AWARENESS_AND_SOCIAL_SATIATION_PLAN.md) | 机器人互刷抑制：社交习惯化 + 印象模型（含文献与参数依据） |
| [`plans/STAGE_39_CLAIM_EVIDENCE_BITEMPORAL_FACTS_PLAN.md`](plans/STAGE_39_CLAIM_EVIDENCE_BITEMPORAL_FACTS_PLAN.md) | 事实层重构：主张/证据/双时态（替代“锁定事实 + 时间补丁”） |

## 二·五、 证据台账（E0）

"不拍脑门"的执行基础设施：每个常数必须有来源，每个功能声明必须有验收。

- 参数台账 [`params/ledger.json`](params/ledger.json)：45 条，`scripts/param_gate.py` 强制；
- 能力台账 [`capabilities.json`](capabilities.json)：20 条，`scripts/capability_gate.py` 强制；
- 状态表 [`CAPABILITY_STATUS.md`](CAPABILITY_STATUS.md)：**自动生成，不要手改**；
- 使用方式见 [`params/README.md`](params/README.md)。

## 三、 历史阶段规划（`plans/STAGE_0` ~ `STAGE_27`）

这些是**过程记录**，描述当时的决策与验收结果，**不作为现行契约**。若与现行文档冲突，以第一节的四份为准。

## 四、 交付纪律（务必遵守）

```text
1. 代码只在 A 线（../echo-mind-a，lane/a-stage29）修改；
2. 提交前在 A 线跑 ./scripts/qa_gate.sh；
3. 准出只在 A 线跑 ./scripts/promote.sh（门禁 + 回放 + 证据）；
4. B 线（本仓库 main）只接受 promote 的 cherry-pick，不直接改代码；
5. 未经确认不重启生产服务（:3310）；
6. 测试不得写生产 data/config.json（tests/conftest.py 守卫）。
```

## 五、 阅读顺序建议

```text
新人上手：README → MASTER_BACKLOG → ARCHITECTURE_CONTRACTS → 最近的 STAGE_30 计划
改人格：  CONTRACT（红绿）→ STAGE_30 计划 §二/§四 → 不变量测试
改关系：  STAGE_29 计划 → bond_depth 参数溯源表 → DATA_MIGRATION_GUIDE
```
