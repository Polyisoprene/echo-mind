# Stage 26 全链路 100% 潜意识 6 维和弦驱动与全库硬编码词表清零工程规范
**（Stage 26 Pure Subconscious 6D Chord Engine & 100% Lexicon Elimination Specification — Status: ✅ 已验收通过）**

---

## 一、 建模目标：彻底根除全库所有中文语义硬编码词表（Zero Hardcoded Semantic Lexicons）

在 Stage 25 验证了「潜意识 6 维情感和弦探针（`SubconsciousChordProbe`）」的基础上，Stage 26 的核心工程目标是**真正做减法**：
**将 `plasticity.py`、`drives.py`、`shadow_appraisal.py`、`personality.py`、`salience_hydraulics.py`、`memory_consolidator.py`、`cybernetics.py` 中残留的全部 24 个硬编码中文语义正则与关键词元组 100% 连根拔除，统一由 `SubconsciousChordResult` 单一潜意识感知载体驱动全系统 12 层认知动力学！**

### 🗑️ 本阶段彻底删除的硬编码词表清单（共 24 处）

| 模块文件 | 被彻底删除的硬编码词表 / 正则 | 替代它的潜意识 6 维和弦字段与数学算子 |
|---|---|---|
| `mind/plasticity.py` | `POSITIVE_CUES` (11词)<br>`NEGATIVE_CUES` (18词)<br>`SELF_DEPRECATION_RE`<br>`NEGATED_PRAISE_RE` | 由 6 维和弦线性泛函计算社交强化奖励：<br>$R(\mathbf{c}_t) = \text{clamp}(0.24 c_{\text{joy}} + 0.08 c_{\text{shy}} - 0.24 c_{\text{hurt}} - 0.28 c_{\text{ann}}, -0.85, +0.85)$ |
| `mind/drives.py` | `PRAISE_PATTERN`<br>`RIVAL_CRITIC_RE`<br>`SCOLD_OR_DOUBT_RE`<br>`QUESTION_PATTERN` | 100% 由 `chord` 的 `(joy, hurt, jealousy, shyness, annoyance, curiosity)` 经连续关系张量 $\mathbf{G}(w_{\text{care}}, w_{\text{aver}})$ 驱动 |
| `mind/shadow_appraisal.py` | `RUDE_DISGUST_RE`<br>`COERCIVE_CMD_RE`<br>`TEASE_EXPOSE_RE`<br>`MISTAKE_CALLOUT_RE`<br>`TASK_REQUEST_RE` | 由 `chord.shadow_trigger` (`"none" \| "aversion" \| "reactance" \| "tease_expose" \| "mistake_callout" \| "task_request"`) 与 `chord.annoyance` 直接驱动 |
| `mind/personality.py` | `COERCIVE_OR_RUDE_RE`<br>硬编码竞争词判断 | 由 `chord.shadow_trigger`、`chord.jealousy` 与 `outcome.social_reward` 驱动 7 维人格微调 |
| `mind/salience_hydraulics.py` | `TRIVIAL_NOISE_RE`<br>`OPEN_QUESTION_RE`<br>`RESONANCE_CUE_RE`<br>`SKILL_REQUEST_RE`<br>`SECOND_PERSON_ASK_RE` | 仅保留协议级 `@QQ` 解析（`AT_UID_RE`）与洛伦兹发言宣泄函数；所有语义唤醒 100% 交由 `chord.role` + `chord.topic_pull` + 表达欲水箱决定 |
| `mind/memory_consolidator.py` | `FACT_PATTERN`<br>`SPOOF_CALLOUT_RE`<br>`BOT_PUSHBACK_RE`<br>`HIPPOCAMPUS_SPOOF_RE` | 由 `chord.spoof_attempt`、`chord.annoyance >= 2` 与 `chord.explicit_fact` 驱动好感度/信任度更新与单轮事实提取 |
| `mind/cybernetics.py` | `BILI_OR_MEDIA_RE`<br>`SEARCH_OR_FACT_RE`<br>`VOICE_OR_SING_RE`<br>`SOCIAL_CHECK_RE` | 由 `chord.reagents`、媒体附件状态与三磁针序参量（$\xi_{\text{stance}}, \xi_{\text{epistemic}}, \xi_{\text{modality}}$）直接选出工具选矿剂 |

---

## 二、 统一数学模型：单次潜意识和弦向量 $\mathbf{c}_t$ 驱动全链路状态转移方程

### 1. 统一潜意识感知结构 `SubconsciousChordResult`
```python
class SubconsciousChordResult(FrozenValueObject):
    role: str = "ambient_daily"          # "direct_to_me" | "about_me" | "peer_dyadic" | "ambient_daily" | "noise"
    topic_pull: int = 1                  # 0..3: 话题/表情包对回音的吸引力档位
    joy: int = 0                         # 0..3: 欣喜/温暖/被逗乐
    hurt: int = 0                        # 0..3: 委屈/失落/被冷落
    jealousy: int = 0                    # -3..+3: +吃醋泛酸 / -被偏爱暗爽消醋
    shyness: int = 0                     # 0..3: 害羞脸红/心事被看穿
    annoyance: int = 0                   # 0..3: 烦躁/被冒犯/嫌弃油腻/被当工具人
    curiosity: int = 0                   # 0..3: 好奇/想看图/想探究新梗
    shadow_trigger: str = "none"         # "none" | "aversion" | "reactance" | "tease_expose" | "mistake_callout" | "task_request"
    spoof_attempt: bool = False          # 对方是否在故意忽悠/冒充身份/编造假话逗我
    explicit_fact: str = ""              # 若对方陈述了值得记住的客观个人/群内事实则提取，否则为空
    reagents: tuple[str, ...] = ()       # 建议挂载的能力选矿剂
    shade: str = "平静"                  # 复合微情绪染色词
    subtext: str = ""                    # 弦外之音
    thought: str = ""                    # 第一人称真实内心 OS
```

### 2. 全链路单次评估与缓存复用（`_chord_cache`）
为了保证每条消息最多只调用 1 次潜意识微模型：
1. 在 `CognitiveCoreFacade` 中维护近期消息的和弦缓存 `_chord_cache: dict[str, SubconsciousChordResult]`（按 `message_id` 索引，容量上限 128 条）；
2. **在 `evaluate_incoming(percept)` 时**：
   - 若命中 0ms 协议硬红灯（15分钟冷暴力、显式 `@其他群友QQ`、同行 Bot 外围发言、`A ⇄ B` 二人转免打扰期） $\longrightarrow$ 0ms 直接返回 `should_wake=False`；
   - 若命中 0ms 协议硬绿灯（私聊、显式 `@我`、引用我、拍一拍我） $\longrightarrow$ 0ms 直接返回 `should_wake=True (tier=1)`，将潜意识评估延后至 `build_cognitive_frame` 执行；
   - 其余群消息 $\longrightarrow$ 调用 `SubconsciousChordProbe.appraise`，将返回的 `chord` 存入 `_chord_cache[percept.message_id]`，并由 `evaluate_chord_wake_decision` 给出唤醒决策与门控雷达内心 OS。
3. **在 `build_cognitive_frame(chat_key, triggers)` 时**：
   - 优先从 `_chord_cache` 读取 `triggers[-1]` 的 `chord`；若尚未评估（如协议硬绿灯直通消息），则在此刻调用 1 次 `appraise` 并缓存；
   - 用该 `chord` 统一驱动：
     - `apply_turn_affect_and_drives(..., chord=chord)`（更新 5 维情绪、4 维内驱力与跨人情绪迁延余波 `inner_thought`）；
     - `evaluate_shadow_appraisal(..., chord=chord)`（生成厌恶、逆反与四大撒谎指令）；
     - `compute_cybernetic_core(..., chord=chord)`（计算三磁针序参量与选矿剂工具路由）。
---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-30）

- **`M26.1 ~ M26.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **全库 24 处硬编码中文语义正则与关键词元组 100% 清零**：
    - `mind/plasticity.py`（覆盖率 **`94%`**）：彻底移除 `POSITIVE_CUES`、`NEGATIVE_CUES`、`SELF_DEPRECATION_RE`、`NEGATED_PRAISE_RE` 与 `import re`；
    - `mind/drives.py`（覆盖率 **`99%`**）：彻底移除 `PRAISE_PATTERN`、`RIVAL_CRITIC_RE`、`SCOLD_OR_DOUBT_RE`、`QUESTION_PATTERN` 与 `import re`；
    - `mind/shadow_appraisal.py`（覆盖率 **`95%`**）：彻底移除 `RUDE_DISGUST_RE`、`COERCIVE_CMD_RE`、`TEASE_EXPOSE_RE`、`MISTAKE_CALLOUT_RE`、`TASK_REQUEST_RE` 与 `import re`；
    - `mind/personality.py`（覆盖率 **`90%`**）：彻底移除 `COERCIVE_OR_RUDE_RE`、硬编码对手名与 `import re`；
    - `mind/memory_consolidator.py`（覆盖率 **`87%`**）：彻底移除 `FACT_PATTERN`、`SPOOF_CALLOUT_RE`、`BOT_PUSHBACK_RE`、`HIPPOCAMPUS_SPOOF_RE` 与 `import re`；
    - `mind/salience_hydraulics.py` & `mind/cybernetics.py`（覆盖率 **`98%`**）：移除全部语义匹配正则，统一由 `SubconsciousChordResult` 与 `_chord_cache` 驱动。
  - 全库 73 项测试 100% 通过，总覆盖率 **`90.24% (90%)`**，Pylint **`10.00/10`**，Mypy Strict **90 个源文件 0 错误**。
