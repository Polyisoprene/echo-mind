# Stage 10 详细工程设计、动态可信度双向校准建模与验收规范
**（Stage 10 Dynamic Epistemic Trust Calibration Specification & Acceptance Report — Status: ✅ 已验收通过）**

---

## 一、 问题背景与原有可信度机制失效建模

在 `SocialBondProfile` 领域模型中，每位群友均拥有 `trust_score ∈ [0.0, 1.0]`（元认知防忽悠可信度，默认初始值 `0.75 ~ 0.80`，主人恒为 `1.0`）。该分值直接决定：
1. **`EpistemicCalibrator`（`mind/epistemic.py`）**：当 `trust_score < 0.50 + skepticism / 250.0` 时，自动点亮 `💡 [元认知谨慎提醒]`；
2. **`ShadowAppraisal`（`mind/shadow_appraisal.py`）**：当 `trust_score < 0.65` 且 `persona_guile >= 50.0` 时，自动激活 `🎭 [反忽悠捉弄撒谎本能 (Counter-Deception)]`。

然而对线上 `social_bonds` 表的实测审计表明，除迁移脚本硬编码的初始值外，几乎所有群友的 `trust_score` 均长期冻结在 `0.80`。其架构级根因如下：

| 失效点 | 原代码位置 | 根因机理 |
|---|---|---|
| **1. 正向增长阈值断档** | `memory_consolidator.py:84`<br>`plasticity.py:169` | 原逻辑要求 `reward >= 0.5` 才 `+0.01`，但非主人群友单句含 1 个夸奖/感谢词时 `reward = 0.45 < 0.5`，导致日常友善互动增量为 `0` |
| **2. 负向惩罚仅限 3 类死词** | `epistemic.py:7-11` | 原逻辑仅当触发 `ROLE_CLAIM_KEYWORDS`（冒充群主/管理/主人）时才扣 `-0.08`；群友用其它话题忽悠被回音当场识破吐槽、或恶意凶人时，可信度完全不扣 |
| **3. 缺少诚实稳态慢速恢复** | `memory_consolidator.py:84` | 一旦某人可信度跌至 `0.55`，即使后续连续几十轮诚实正常交流（`reward = 0.08`），可信度也无法缓慢回升至基准 `0.80` |
| **4. 批次多发言人漏算 & 海马体未联动** | `memory_consolidator.py:129, 168` | 仅更新了批次最后一条消息的发送者；且海马体总结出“某人开玩笑忽悠回音”时未联动下调该参与者可信度 |

---

## 二、 三层动态可信度校准架构设计（3-Layer Trust Calibration Model）

### 1. 第一层：单轮多信号双向校准纯函数（`compute_trust_delta` in `mind/memory_consolidator.py`）
对于非主人群友（主人恒锁定 `1.0`），单轮可信度增量 $\Delta T$ 由以下优先级阶梯决定（裁剪区间 `[0.10, 0.98]`）：
1. **权威事实直接冲突（`conflict == True`）**：$\Delta T = -0.08$（严厉惩罚冒充身份/篡改铁律）；
2. **回音在当轮回复中当场识破忽悠（`called_out_spoof == True`）**：
   - 检测回音本轮发出的 `outcome.sent_texts` 是否命中防忽悠拆穿语义正则 `SPOOF_CALLOUT_RE`（`忽悠|骗我|骗人|少骗|哄我|才不信|少来这套|蒙我|编瞎话|逗我玩|挖坑`）；
   - 若命中，说明模型通过上下文或工具核验识破了对方挖坑：$\Delta T = -0.04$；
3. **恶意攻击或明显负向互动（`reward <= -0.40`）**：$\Delta T = -0.03$；
4. **真诚友善与正向夸奖互动（`reward >= 0.40`）**：$\Delta T = +0.02$（修复原 `0.45 < 0.50` 断档，单句道谢/夸奖即可累积信任）；
5. **日常诚实平稳交流的稳态恢复（`reward >= 0.0` 且 `base_trust < 0.80`）**：$\Delta T = +0.005$（体现“洗心革面好好说话可逐步修复信任”）。

同时，`consolidate_turn_memory` 遍历 `outcome.triggers` 中的全部去重发送人，确保合批消息中的每位参与者均得到好感度与可信度更新。

### 2. 第二层：海马体睡眠复盘可信度联动（`run_hippocampal_batch_consolidation`）
- 当海马体提炼出的 `EpisodicCard` 的 `summary` 或 `key_detail` 中明确记录了欺骗/忽悠事件（匹配 `忽悠|挖坑|骗了|冒充|假称`）且包含 `card.participants`（群友 QQ 号）时，自动对涉事非主人群友追加 `-0.05` 的复盘可信度惩罚。

### 3. 第三层：Web 控制台「社交」页可信度可视化微调（`web/ext_routers.py`, `mind_inspector_service.py`, `app.js`）
- `PUT /api/mind/bonds/{user_id}` 的 `BondTunePayload` 新增可选字段 `trust_score: float | None = None`；
- 控制台「社交」页表格中的「可信度」列新增颜色分级徽标（`≥0.75` 绿色高信、`0.60~0.75` 黄色观察、`<0.60` 红色防忽悠警戒）以及 `-0.05` / `+0.05` 快捷微调按钮。

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M10.1` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 通过
  - `mind/memory_consolidator.py`（覆盖率 **`92%`**）：
    1. `compute_trust_delta` 实现 5 级双向校准（权威事实冲突 `-0.08`、当轮回复拆穿忽悠 `-0.04`、负向攻击 `-0.03`、正向友善夸奖 `+0.02`、低于 `0.80` 时的诚实交流慢速恢复 `+0.005`）；
    2. `consolidate_turn_memory` 遍历合批消息中的所有去重发言人，不再漏算前序发言人；
    3. `_penalize_card_spoofers` 在海马体总结出某人忽悠/挖坑事件卡时自动对涉事群友追加 `-0.05` 可信度惩罚。
  - `web/ext_routers.py`（覆盖率 **`100%`**）& `web/mind_inspector_service.py`（覆盖率 **`98%`**）& `web/static/app.js`：支持在「社交」页实时查看红/黄/绿三级可信度徽标并一键 `±5%` 手动微调。
  - 全库 59 项测试全过，总覆盖率 **`92.66% (93%)`**，Pylint **`10.00/10`**，Mypy Strict **`0 错误`**。
