# EchoMind 文档索引（Docs Index）

> 最后更新：2026-11-01（Stage 41 收口后）
> 本文件是文档入口。**当前真实状态以 [`CURRENT_STATE_2026-11-01.md`](CURRENT_STATE_2026-11-01.md) 为唯一权威**；历史阶段规划是记录，不再修改。

---

## 一、先读这几份

| 文档 | 作用 |
|---|---|
| [`CURRENT_STATE_2026-11-01.md`](CURRENT_STATE_2026-11-01.md) | **当前真实状态**：active trait、support、评测、能力边界 |
| [`plans/STAGE_41_UNFINISHED_REMEDIATION_AND_SELF_EVOLUTION_PLAN.md`](plans/STAGE_41_UNFINISHED_REMEDIATION_AND_SELF_EVOLUTION_PLAN.md) | Stage 41 全景：证据账本、生命周期、trait→记忆、support、ranker、闭环矩阵 |
| [`PERSONA_STATUS_CN.md`](PERSONA_STATUS_CN.md) | 人格模型现在到哪一步（人话版） |
| [`PERSONA_SELF_EVOLUTION_STATUS_CN.md`](PERSONA_SELF_EVOLUTION_STATUS_CN.md) | 自演化现在到哪一步 |
| [`MASTER_BACKLOG.md`](MASTER_BACKLOG.md) | 单一事实源：硬编码、待办、变更日志 |
| [`ARCHITECTURE_CONTRACTS.md`](ARCHITECTURE_CONTRACTS.md) | 分层边界、SOLID 硬约束、7 道门禁、人格模型契约 |
| [`params/ledger.json`](params/ledger.json) + [`params/README.md`](params/README.md) | 参数溯源台账：59 条常数与证据 |
| [`capabilities.json`](capabilities.json) + [`CAPABILITY_STATUS.md`](CAPABILITY_STATUS.md) | 能力台账：实现/部分/缺失/矛盾 |

---

## 二、当前能力与设计

| 文档 | 内容 |
|---|---|
| [`PERSONA_SELF_EVOLUTION_MODEL.md`](PERSONA_SELF_EVOLUTION_MODEL.md) | 自演化理论模型：Beta 证据、CAPS、CLS、叙事身份 |
| [`PERSONA_SELF_EVOLUTION_DESIGN_CN.md`](PERSONA_SELF_EVOLUTION_DESIGN_CN.md) | 工程落地设计；顶部有当前实现状态说明 |
| [`PERSONA_MODEL_PORTRAIT.md`](PERSONA_MODEL_PORTRAIT.md) | 人格模型画像 |
| [`PERSONA_DISCLOSURE_MODEL.md`](PERSONA_DISCLOSURE_MODEL.md) | 隐私/披露模型与 audience 硬门 |
| [`PERSONA_STYLE_MONITORING.md`](PERSONA_STYLE_MONITORING.md) | 确定性风格监控：长度、长句、解释词、括号动作 |
| [`COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md`](COGNITIVE_CORE_AND_SELF_LEARNING_SPEC.md) | 认知核心、7 维人格、记忆与门控算法 |
| [`MEMORY_SOURCE_AND_DISCLOSURE.md`](MEMORY_SOURCE_AND_DISCLOSURE.md) | 记忆来源、claim/evidence、双时态 |
| [`DATA_MIGRATION_GUIDE.md`](DATA_MIGRATION_GUIDE.md) | 数据导入、表结构、迁移 |
| [`EVALUATION_STANDARD.md`](EVALUATION_STANDARD.md) | 评测协议与判据 |

---

## 三、Stage 41 相关专项

| 文档 | 内容 |
|---|---|
| [`plans/STAGE_41_UNFINISHED_REMEDIATION_AND_SELF_EVOLUTION_PLAN.md`](plans/STAGE_41_UNFINISHED_REMEDIATION_AND_SELF_EVOLUTION_PLAN.md) | 14.1–14.71：证据、生命周期、signature、backfill、support、ranker、词法门控、active-only、action eligibility、B4/B5/B6、G1/G2 |
| [`PERSONA_SELF_EVOLUTION_STATUS_CN.md`](PERSONA_SELF_EVOLUTION_STATUS_CN.md) | 当前自演化状态与未完成边界 |
| [`PERSONA_STATUS_CN.md`](PERSONA_STATUS_CN.md) | 当前人格状态与真人感水平 |

关键工程入口：

- 手动 support 向导：`scripts/manual_trait_support_wizard.py`
- 手动 support CLI：`scripts/manual_trait_support.py`
- 自动晋升器：`scripts/auto_promote_trait_candidates.py`（默认 dry-run）
- 叙事投影：`scripts/trait_narrative.py`（只读，不接 prompt）
- 健康/证据/风格 API：`/api/mind/trait-health`、`/api/mind/traits/{id}/evidence`、`/api/mind/style-health`

---

## 四、历史阶段规划（Stage 0–40）

这些是过程记录，描述当时的决策与验收，**不作为现行契约**。

- 历史规划目录：`docs/plans/`
- 项目宪章与阶段总表：[`PROJECT_CHARTER_AND_PROGRESS.md`](PROJECT_CHARTER_AND_PROGRESS.md)（当前状态看第一节）
- Stage 28 A/B 双线交付纪律是历史工作流；当前仓库以 `main` 的实际代码与门禁结果为准。

---

## 五、交付纪律（当前）

```text
1. 代码修改后必须跑 ./scripts/qa_gate.sh；
2. 测试不得写生产 data/config.json（tests/conftest.py 守卫）；
3. 生产服务重启前确认 3310/3312 状态；
4. 任何数值参数必须有 ledger 依据，fit_pending 不得伪装成 fit；
5. CURRENT_STATE 与 CAPABILITY_STATUS 必须随功能变化更新。
```

## 六、阅读顺序

```text
新人上手：CURRENT_STATE → MASTER_BACKLOG → ARCHITECTURE_CONTRACTS → Stage 41
改人格：  PERSONA_STATUS_CN → Stage 41 14.x → 不变量测试
改记忆：  MEMORY_SOURCE_AND_DISCLOSURE → Stage 41 B4/B5/B6 → 隐私/validity 测试
改评测：  EVALUATION_STANDARD → capabilities.json → LEDGER
```
