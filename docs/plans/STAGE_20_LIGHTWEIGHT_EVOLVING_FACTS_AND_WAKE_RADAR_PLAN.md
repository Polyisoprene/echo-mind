# Stage 20 详细工程设计、零膨胀演化事实双算子与实时清醒/注意力门控雷达规范
**（Stage 20 Detailed Engineering Specification: Zero-Bloat Evolving Fact Operators & Real-Time Wakefulness/Attention Gate Radar — Status: ✅ 已验收通过）**

---

## 一、 全局问题建模与极简架构设计（Zero-Bloat Modeling）

遵循奥卡姆剃刀原则（**0 新增数据库表、0 新增认知层级、所有文件严格 $\le 300$ 行**），我们将本次升级建模为两个高内聚子系统：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│           Stage 20 「零膨胀演化事实算子 × 实时注意力门控雷达」全局模型                 │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 子系统一 (M20.1)   │ 【零新表·复用现有字段】adapters/storage/memory_repo.py & mind/    │
│ 演化事实双微算子   │  1. 候选防噪与二次印证转正：非主人首次随口提到的事实初始          │
│ Evolving Facts     │     confidence=0.58（提示词标注 `[待核实印象]`）；当被第 2 次印证 │
│ (Zero Schema Bloat)│     (`revision_count >= 2`) 时自动晋升 `confidence=0.85`（转正）；│
│                    │     睡眠修剪时自动清理 `revision_count==1 & confidence<0.65` 孤证 │
│                    │  2. 状态演变留痕：当同主题 `fact_text` 更新时，自动保留前情后缀   │
│                    │     `f"{new_text}（此前曾是：{old_text[:28]}）"`。                │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 子系统二 (M20.2/3) │ 【解决控制台“不知道她醒没醒/收到没/为什么没回”】                  │
│ 实时清醒状态与     │  1. 生理觉醒态透出：在 `/api/mind/runtime` 与 `/api/mind/snapshot`│
│ 注意力门控雷达     │     实时返回 `wake_state`（🟢 清醒活跃 / 🟡 午休慵懒 / 💤 深度睡眠│
│ Live Attention     │     + 当前生活相位 + 精力值 + 最后收信时间）；                    │
│ Gate Radar         │  2. 入站门控决策环形缓冲（最近 25 条）：在 `evaluate_incoming` 时 │
│                    │     实时记录每条收到的消息：`时间 | 群/私聊 | 发言人 | 内容 |     │
│                    │     判定结果(🟢已唤醒 / ⚪不感兴趣未达阈值 / ⚪冷却中 / ⚪非对我说│
│                    │     / 💤犯困休息 / 💢冷暴力不回) | 显著度分数`。                  │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 二、 分阶段详细工程设计（Milestone Engineering Specification）

### 里程碑 `M20.1`：零膨胀演化事实双微算子（`memory_repo.py`, `memory_consolidator.py`, `frame_renderer.py`, `scheduler.py`）
1. **变化轨迹自动留痕（`_merge_evolving_fact_text` in `src/echomind/adapters/storage/memory_repo.py`）**：
   - 当 `upsert_semantic_fact` 命中已存在的非锁定 `(chat_key, subject)` 且新旧文本不同时：
     剥离旧文本中已有的 `（此前曾是：…）` 尾巴得到 `clean_old`；若 `clean_old` 与 `new_text` 不同，自动合成为 `f"{new_text[:115]}（此前曾是：{clean_old[:28]}）"`；
   - 同时将 `revision_count` 加 1，若 `revision_count >= 2` 且 `confidence < 0.85`，自动将 `confidence` 晋升至 `0.85`（多证据印证转正）！
2. **候选印象初始置信度与孤证睡眠修剪（`memory_consolidator.py`, `frame_renderer.py`, `scheduler.py`）**：
   - `memory_consolidator.py:_extract_explicit_fact`：非主人首次随口陈述的事实初始 `confidence = 0.58`（主人陈述仍为 `0.88`）；
   - `frame_renderer.py`：渲染事实底表时，若 `f.confidence < 0.65 and not f.is_locked`，前缀标注为 `[待核实印象 {pct}%]`；
   - `scheduler.py:run_sleep_pruning`：自动清理 `is_locked = 0 AND source = 'peer' AND revision_count <= 1 AND confidence < 0.65` 的未转正孤证噪音。

---

### 里程碑 `M20.2` & `M20.3`：实时清醒状态与注意力门控雷达（`circadian.py`, `facade.py`, `mind_inspector_service.py`, `index.html`, `app.js`）
1. **生理清醒度与门控环形缓冲（`src/echomind/mind/circadian.py` & `facade.py`）**：
   - 在 `circadian.py` 新增 `summarize_wakefulness(energy: float, now_ms: int | None = None) -> dict[str, Any]`：
     返回 `{"status": "asleep" | "drowsy" | "awake", "badge": "💤 深度睡眠中" | "🟡 犯困慵懒" | "🟢 清醒活跃", "phase_label": phase.label, "energy": energy}`；
   - 在 `CognitiveCoreFacade.evaluate_incoming(percept, dry_run=...)` 中（当 `not dry_run` 时）：
     将本次入站消息及 `AttentionDecision` 记录进 `self._recent_gate_log`（最多保留最新 25 条，含 `ts`, `chat_key`, `sender_name`, `text`, `should_wake`, `tier`, `salience`, `reason`）。
2. **控制台顶栏与「总览」页实时门控雷达（`web/static/index.html` & `app.js`）**：
   - **顶栏状态栏**：除显示 `QQ在线` 外，实时显示回音当前的清醒状态徽标（如 `🟢 清醒活跃 · 🌃 晚间黄金共鸣相 (精力 82)` 或 `💤 深度睡眠中`）；
   - **总览页新增《📡 实时听觉与唤醒门控雷达（为什么回 / 为什么没回）》卡片**：
     实时列出她收到的每一条群聊/私聊消息，并用醒目徽标区分：
     - `🟢 已唤醒回应`（如 `点名叫我(必回)`、`被艾特(@我)`、`5分钟对话延续窗口`、`好奇心触发`）
     - `⚪ 收到但未感兴趣`（`环境闲聊·未达插话阈值 (显著度 0.35)`）
     - `⏳ 收到但冷却中`（`群聊非点名冷却期内`）
     - `🔇 非对我说话`（`艾特或引用其他群友(非对我说话)`）
     - `💤 犯困休息未插话`（`精力过低·犯困休息不插话`）
     - `💢 冷暴力已读不回`（`烦透了·冷暴力已读不回`）

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M20.1` ~ `M20.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M20.1`（零新表演化事实双算子）**：
    - `adapters/storage/memory_repo.py`（覆盖率 **`99%`**）、`mind/memory_consolidator.py`（覆盖率 **`92%`**）、`mind/frame_renderer.py`（覆盖率 **`97%`**）：非主人首次随口陈述的事实以 `confidence=0.58`（`[待核实印象]`）入库，第 2 次印证（`revision_count >= 2`）自动晋升 `0.85`；同主题更新时自动保留 `（此前曾是：…）` 变化轨迹；睡眠修剪自动清理 24 小时未转正孤证噪音。
  - **`M20.2` & `M20.3`（实时清醒状态与注意力门控雷达）**：
    - `mind/circadian.py`（覆盖率 **`97%`**）、`mind/facade.py`（覆盖率 **`97%`**）、`web/mind_inspector_service.py`（覆盖率 **`91%`**）：在顶栏与总览页实时展示回音生理清醒态（`🟢 清醒活跃` / `🟡 犯困慵懒` / `💤 深度睡眠中`）及最近 25 条入站消息的门控判定结果（`🟢 已唤醒回应`、`⚪ 收到·不感兴趣(未达阈值)`、`⏳ 收到·冷却期未插话`、`🔇 收到·非对我说话`、`💤 收到·犯困休息`、`💢 收到·冷暴力已读不回`）。
  - 全库 68 项测试 100% 通过，总覆盖率 **`90.57% (91%)`**，Pylint **`10.00/10`**，Mypy Strict **88 个源文件 0 错误**。
