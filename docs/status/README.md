# 状态与路标（Status）— 活文档

⭐ **这一目录是系统"现在真实是什么样"的唯一权威**。其他目录描述设计与评测方法，这里记录**实际交付到哪一步**。

> 阅读顺序建议：先 `CURRENT_STATE`（全局现状）→ 再按需读专门的 status。

| 文档 | 作用 |
|---|---|
| [`CURRENT_STATE.md`](CURRENT_STATE.md) | ⭐ **当前真实状态**：active trait、support、评测数字、能力边界 |
| [`CAPABILITY_STATUS.md`](CAPABILITY_STATUS.md) | 能力台账（**自动生成**，请勿手改；源头是 [`../capabilities.json`](../capabilities.json)） |
| [`CLOSURE_MATRIX.md`](CLOSURE_MATRIX.md) | 闭环矩阵：已完成 / 已验证 / 被外部资源阻塞 |
| [`MASTER_BACKLOG.md`](MASTER_BACKLOG.md) | 总账：硬编码、身份解耦、关系模型、变更日志 |
| [`PROJECT_CHARTER.md`](PROJECT_CHARTER.md) | 立项书与全局工程进度 |
| [`PARAMETER_SCORECARD.md`](PARAMETER_SCORECARD.md) | 参数红绿灯（人话版） |
| [`PERSONA_STATUS.md`](PERSONA_STATUS.md) | 人格模型现在到哪一步（人话版） |
| [`PERSONA_SELF_EVOLUTION_STATUS.md`](PERSONA_SELF_EVOLUTION_STATUS.md) | 人格自演化现在到哪一步 |
| [`MEMORY_REFACTOR_STATUS.md`](MEMORY_REFACTOR_STATUS.md) | 记忆模块重构状态与路线（部分内容已被 CURRENT_STATE 取代） |

> ⚠️ `CAPABILITY_STATUS.md` 由 `scripts/capability_gate.py` 生成。修改能力状态请编辑 [`../capabilities.json`](../capabilities.json) 后重新生成，否则门禁 2C 会失败。

<div align="right"><a href="../README.md">← 返回文档索引</a></div>
