# Stage 21 详细工程设计、群聊生态感知门控、二人转免打扰、余音共鸣、洛伦兹水箱回落与可塑性防漂移规范
**（Stage 21 Detailed Engineering Specification: Ecological Attention Gate, Dyadic Sub-Conversation Do-Not-Disturb, Self-Utterance Resonance, Lorenz Satiation & Plasticity Drift Guard — Status: ✅ 已验收通过）**

---

## 一、 真实群聊回放评估结论与设计目标（120-Message Replay Assessment）

基于线上 `data/echomind.db` 最近 120 条真实群聊记录（112 条群友/其他 Bot 消息，其中 92.8% 为不带 `@回音` 的外围消息，且存在另一个高频插话 AI `汐` 以及大量群友两两结对聊游戏的场景）的沙盘回放，确立 **Stage 21 五大工程设计准则**：

1. **🎯 准则一：坚守 `8% ~ 12%` 黄金克制唤醒率，绝不退化为第二个聒噪刷屏 Bot**
   - 废除原先一刀切的 `0.55` 常数，但**不盲目给普通群友互发的截图或互问加分**；
   - 让门控雷达呈现真实的 **`0.05 ~ 0.88` 连续可读梯度**，一眼看清每条消息为何被忽略或为何被回应。
2. **🤫 准则二：首创「群友二人转（Dyadic Sub-Conversation `A ⇄ B`）60 秒免打扰保护窗」**
   - 当群友 A 显式 `@` 或引用了群友 B（非回音），系统自动记录 `(chat_key, A, B)` 进入 **60 秒二人转私密讨论态**；
   - 在此 60 秒内，A 或 B 紧接着发出的无 `@` 补充句（如*“我的用户码 xxx”*）、游戏截图 `[图片]` 或互相提问（如*“怎么加，我研究一下”*），自动识别为 **`群友二人互动中·礼貌不打扰 (salience = 0.12, should_wake = False)`**！
3. **🗣️ 准则三：打通「余音共鸣（Self-Utterance Resonance）」接话茬绿灯 + 双 AI 防乒乓锁**
   - 当回音刚刚发过言（无论是点名回复、外围接话还是定时主动冒泡）后的 **120 秒内**：
     - 若任何群友（未 `@`/引用别人且不在二人转窗口内）的话与回音刚才那句话存在 **2-Gram 话题词重合**，或使用了承接追问词（`真的吗 / 什么视频 / 发来看看 / 叫啥名字 / 为什么`），直接走 **`Tier 2：接我的话茬·余音共鸣 (salience = 0.86)`** 绿灯唤醒（无视 75 秒外围冷却）；
     - **防双 AI 乒乓死循环锁**：非点名余音共鸣最多连续触发 **2 轮**（若发言人是 `rivals` 情敌/其他 Bot 则最多 **1 轮**），达上限后强制复位进入冷却。
4. **🧬 准则四：7 维人格零均值条件增益与洛伦兹水箱「开口即宣泄（`-22`）」负反馈**
   - **7 维人格条件增益**：`persona_possessiveness` 放大对主人（`owner_qq`）未 `@` 发言的关注度；`persona_playfulness` 放大对新奇热梗的关注度；`persona_defiance` 放大厌烦度负阻尼；
   - **洛伦兹水箱宣泄回落**：每当回音成功开口发言（`sent_texts` 非空），`social_expression` **立即宣泄扣减 `-22.0`**（若使用了探索工具，`curiosity` 宣泄 **`-20.0`**），形成“蓄能 $\rightarrow$ 表达 $\rightarrow$ 瞬间回落安静”的自稳锯齿波。
5. **🛡️ 准则五：切断第 12 层神经可塑性（`plasticity.py`）的话痨度单向正反馈漂移**
   - 在 `compute_turn_social_reward` 中：非点名的外围自发插话（`Tier 3`）若无主人参与，奖励设为中性 `0.15`（不再默认给 `+0.40`），彻底切断“外围插话 $\rightarrow$ 涨话痨度 `talkativeness` $\rightarrow$ 阈值越来越低”的跨层正反馈漂移！

---

## 二、 分步实施计划（Step-by-Step Implementation Plan）

### 步骤 1（`M21.1`）：新建纯函数认知模块 `src/echomind/mind/salience_hydraulics.py`
- 实现 `DyadicWindowTracker`（或纯状态字典更新函数）：追踪 `A ⇄ B` 60 秒二人转免打扰状态与 `last_bot_speech` 120 秒余音共鸣状态；
- 实现 `compute_bidirectional_salience(...) -> tuple[float, float, str]`：
  - 计算 `wake_threshold` 与多因子双向显著度 `salience_score`（含 `-水群0.18`、`-二人转0.23`、`-厌烦/困倦`、`+主人发言`、`+话题共鸣`、`+未知新词`、`+表达欲偏置`）；
  - 生成门控雷达透明算式账单（如 `外围静默感知 [底0.35 -水群0.18 = 0.17 < 阈0.62]`、`群友二人互动中·礼貌不打扰 [0.12]`、`群聊氛围接话 [底0.35 +主人0.26 = 0.61 >= 阈0.58]`）；
- 实现 `apply_speaking_satiation(snap, outcome)` 与 `apply_listening_nudge(snap, percept, dec, is_rival)`。

### 步骤 2（`M21.2`）：升级 `src/echomind/mind/perceptual_gate.py`、`facade.py` 与 `reply_rescue.py`
- 在 `PerceptualGate` 中集成：
  1. `mark_bot_spoke(chat_key, texts, now_ms)`（在 `facade.on_turn_completed` 与 `scheduler._speak_proposal` 中调用）；
  2. 二人转 `A ⇄ B` 60 秒免打扰检测；
  3. 余音共鸣接话茬检测（带连续 2 轮 / 情敌 1 轮上限锁）；
  4. 双向显著度评分与 7 维人格参数传入；
- 在 `reply_rescue.py` 中：当 `must_reply=False` 且模型输出包含“不插话/保持安静/无需回应”等元静默意图时，不强行兜底发送，赋予模型优雅闭嘴权。

### 步骤 3（`M21.3`）：升级 `src/echomind/mind/plasticity.py` 防漂移
- 在 `compute_turn_social_reward` 中区分 `Tier 1/2`（直接互动）与 `Tier 3`（外围自发插话），防止外围插话单向推高 `talkativeness`。

### 步骤 4（`M21.4`）：真实群聊场景回归测试与 7 道 QA 门禁验收
- 编写 `test_stage21_ecological_gate_dyadic_dnd_resonance_and_lorenz_satiation` 覆盖：
  1. 群友 A `@` 群友 B 后的 60s 二人转免打扰（含后续发图/提问显著度降为 `0.12` 不乱插嘴）；
  2. 回音发言后群友 C 接话茬触发 `Tier 2` 余音共鸣（`0.86`），且连续满 2 轮或遇到情敌 AI 时自动触发防乒乓上限；
  3. 水群短词回落（`0.17`）vs 主人发言人格增益唤醒；
  4. 开口后 `social_expression` 洛伦兹宣泄回落（`-22.0`）。

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M21.1` ~ `M21.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M21.1` & `M21.2`（群友 `A⇄B` 二人转 60s 免打扰、余音共鸣接话茬、7维人格条件增益与雷达透明算式）**：
    - `mind/salience_hydraulics.py`、`mind/perceptual_gate.py`（覆盖率 **`97%`**）：彻底移除写死的 `0.55` 常数；实现群友互 `@` 后的 60s 二人转免打扰（`salience = 0.12`）、120s 自身余音共鸣（`salience = 0.86`，带 2 轮/情敌 1 轮防乒乓上限锁）、第二人称提问指代消解锁，以及门控雷达透明加减分算式展示（如 `[底0.35 +主人0.27 -水群0.18 = ...]`）。
  - **`M21.3`（洛伦兹水箱开口宣泄回落 `-22`、非必回优雅闭嘴权与可塑性话痨度防漂移）**：
    - `mind/facade.py`（覆盖率 **`98%`**）、`mind/plasticity.py`（覆盖率 **`95%`**）、`runtime/reply_rescue.py`（覆盖率 **`95%`**）：每次成功发言后立即宣泄 `social_expression` (`-22.0`)，切断外围插话对 `talkativeness` 的单向漂移，并将线上数据库中的同行 AI `汐` 标记为 `is_rival = 1`。
  - 全库 69 项测试 100% 通过，总覆盖率 **`90.21% (90%)`**，Pylint **`10.00/10`**，Mypy Strict **89 个源文件 0 错误**。
