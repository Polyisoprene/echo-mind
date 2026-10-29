# Stage 13 详细工程设计、全局建模与架构升级规范：时间流逝感知、防重复分享去重、时间与外界冲浪信息驱动的情绪/人格演化引擎
**（Stage 13 Detailed Engineering Specification: Temporal Perception, Anti-Repeat Novelty Gate & Exogenous/Temporal Affect-Personality Evolution — Status: ✅ 已验收通过）**

---

## 一、 全局问题建模与根因分析（Global Problem Modeling & Root-Cause Analysis）

结合线上群聊真实日志（`chat_messages#2395 ~ #2414`）与认知核心代码审计，我们将用户指出的三大深层问题建模如下：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               Stage 13 三大核心问题全局架构建模 (Global Root-Cause Model)              │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 问题一 (M13.2)     │ 【现象】13:35、13:45、13:50、13:55 连续 4 次分享同一个B站视频     │
│ 同一内容反复分享   │ 【根因】1. bili_popular 每次固定取第1名 (_first_bullet_line)，无已 │
│ Lack of Novelty &  │    看/已分享 BV 去重记忆；                                        │
│ Drive Satiation    │  2. 冲浪后未扣减 curiosity/social_expression 驱力（无满足感回落）；│
│                    │  3. 每次后台冲浪都强行往群里发消息，且 current_activity 一直挂着  │
│                    │    该视频标题，导致后续普通群聊也不断往该视频上扯。               │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 问题二 (M13.1)     │ 【现象】发出消息后很久没人理，13分钟后别人聊别的图，她还以为在接  │
│ 时间失明与跨时空   │  她刚才说的省际刻板印象话题                                       │
│ 强行接话           │ 【根因】PromptComposer._format_percept_line 完全丢弃了 timestamp_ms│
│ Time-Blind Context │  既无消息时间 `[14:08]`，也无 `── ⏱️ 间隔 13 分钟 ──` 断层提示，   │
│                    │  大模型看相差 2 秒和相差 2 小时的两句话毫无区别！                 │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 问题三 (M13.3)     │ 【现象】情绪与7维人格只在群聊触发时变化，不受时间流逝与外界冲浪影 │
│ 封闭式情感/人格    │  响                                                               │
│ Open-System Affect │ 【根因】drives.py 与 plasticity.py 仅绑定在群聊 TurnOutcome 上，缺 │
│ & Exogenous Input  │  少：① 随真实时间流逝 ∆t 的情绪指数半衰期平复与昼夜心境漂移；    │
│                    │  ② 自主冲浪/刷B站获取外界信息后的情绪愉悦提升与性格可塑微演化。   │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 二、 分阶段详细工程设计（Milestone Engineering Specification）

### 里程碑 `M13.1`：全链路时间感知系统（Temporal Context & Topic-Break Architecture）
1. **消息级时间戳与 `≥ 5 分钟` 时间断层分割线（`src/echomind/runtime/prompt_composer.py`）**：
   - 在 `_format_percept_line(p)` 中注入北京时间 `[HH:MM]`：`[14:08 #2413] 真实gachi(QQ:...): ...`；
   - 新增 `_render_temporal_percept_lines(percepts: tuple[Percept, ...]) -> list[str]`：
     遍历消息序列，计算相邻两条消息的时间差 $\Delta t = (t_i - t_{i-1}) / 60000$：
     - 当 $\Delta t \ge 5$ 分钟时，在两条消息之间自动插入显式时间断层标记：
       `── ⏱️ [时间断层：中间安静了 X 分钟，上一段话题早已自然翻篇，切勿再把后面的话当成对前面旧话题的回应] ──`
2. **认知帧注入当前北京时间与跨轮次时间间隔提示（`src/echomind/mind/frame_renderer.py`）**：
   - 在 `render_mind_block` 头部显示当前北京时间与时段（如 `2026-10-29 14:10（午后）`）；
   - 当本轮触发消息距离上一条历史消息间隔 $\ge 5$ 分钟，或 `current_activity` 中包含已在历史消息中发过的视频/话题时，注入明确的 **「⏱️ 旧话题翻篇纪律」**。

---

### 里程碑 `M13.2`：防重复分享去重池、冲浪内驱力满足（Satiation）与静默吸收机制
1. **已看/已分享内容去重与多候选挑选（`src/echomind/runtime/scheduler.py` & `adapters/media/bili.py`）**：
   - `BiliClient.popular(limit=10)`：拉取热门榜前 10 条候选视频；
   - 在 `CognitiveHeartbeatScheduler` 中查询 `exploration_logs` 与 `chat_messages` 最近已看/已分享过的视频标题或 `BV` 号集合 `seen_keys`；
   - 从热门榜或搜索结果中**挑选第一条尚未在 `seen_keys` 中出现过的新鲜条目**（`_pick_unseen_bullet_line`）！若当前热门榜前 10 条全都看过了，则直接跳过重复分享。
2. **冲浪内驱力满足（Drive Satiation）与默认静默吸收（`src/echomind/mind/facade.py` & `runtime/scheduler.py`）**：
   - **内驱力满足回落**：在 `CognitiveCoreFacade._consume_proposal_state` 中，当触发 `bili_surf`、`curiosity_explore` 或 `cold_group_topic` 后，立即将 `curiosity` 下调 `-25.0`、`social_expression` 下调 `-25.0`（体现“刷完B站/说完话后好奇心与表达欲得到满足”），避免每 5~10 分钟连续触发！
   - **区分「自己静默刷B站（`bili_surf`）」与「冷场主动开话头（`cold_group_topic`）」**：
     - `bili_surf`（闲暇刷B站）默认**静默吸收进脑海**（更新知识库、情绪与人格，**不往群里刷屏发链接**）；
     - 只有当群聊真正冷场达到阈值（`cold_group_topic`）且该话题**从未在群里发过**时，才向群里主动分享一次；分享完毕后立即将 `working_state.current_activity` 切换回日常休闲状态（如 `"戴着耳机听歌摸鱼"`），不再把视频标题一直挂在 `current_activity` 上导致后续每轮都提！
   - 同理在 `QzoneMoodShowcaseScheduler._send_one_proactive_target` 中：发完一次主动消息后，若 `current_activity` 含有已发出的链接/视频名，自动将 `current_activity` 刷新为日常状态，绝不在私聊和群聊重复发同一个链接。

---

### 里程碑 `M13.3`：时间流逝与外界信息（冲浪/B站/搜索）驱动的情绪与 7 维人格演化引擎
1. **基于真实时间差 $\Delta t$ 的情绪半衰期平复与昼夜节律（`src/echomind/mind/drives.py`）**：
   - 新增纯函数 `apply_temporal_decay_and_circadian(snapshot: WorkingSnapshot, elapsed_minutes: float, now_ms: int) -> WorkingSnapshot`：
     - 根据距离上次状态更新的真实分钟数 `elapsed_minutes`（指数衰减因子 $\gamma = 1 - 0.5^{\Delta t / 30}$）：
       - `jealousy`、`irritation`、`shyness` 向各自静息基线（`0.0`、`0.0`、`15.0`）按半衰期自然平复；
       - `energy` 向当前北京时间的昼夜节律目标（清晨 `78`、白天 `76`、午后小憩 `62`、傍晚 `74`、夜晚 `44`、深夜 `22`）平滑收敛；
       - 独处期间 `curiosity` 与 `attachment` 随时间温和自然生长。
2. **外界信息（B站冲浪 / 网页搜索）对情绪与 7 维人格的动态塑造（`src/echomind/mind/plasticity.py` & `runtime/scheduler.py`）**：
   - 新增 `apply_exogenous_surf_impact(working_store: IWorkingStateStore, kind: str, topic: str, finding: str) -> None`：
     - **对连续情绪（`AffectiveVector`）的影响**：刷到新鲜有趣的 B站视频或热梗词条时，缓解无聊与烦躁（`valence +6.5`、`irritation -8.0`、`curiosity -22.0`）；
     - **对 7 维可塑性格（`plastic_params` & `plastic_logs`）的影响**：
       - 自主刷 B站热门视频（`bili_surf`）或搜索新梗（`curiosity_explore`）时，根据内容特征微调 `persona_playfulness`（俏皮玩梗度 `+0.8`）、`curiosity_rate`（求知欲 `+0.6`）或 `persona_warmth`（温暖度 `+0.6`），并写入 `plastic_logs`（如 `"在B站自主冲浪刷到《...》，眼界与玩梗灵动度提升"`），使她的性格不仅受群友影响，也会因为自己平时刷B站、看世界而自然成长！

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M13.1` ~ `M13.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M13.1`（全链路时间感知系统）**：
    - `runtime/prompt_composer.py`（覆盖率 **`99%`**）& `mind/frame_renderer.py`（覆盖率 **`97%`**）：每条上下文消息附带北京时间 `[HH:MM]`；当相邻两条消息时间间隔 $\ge 5$ 分钟时，自动插入 `── ⏱️ [时间断层：中间安静了 X 分钟，旧话题已翻篇] ──` 分割线，并在最新消息与历史间隔 $\ge 5$ 分钟时注入 `⏱️【时间流逝断层提醒】`，彻底消除跨时空强行接旧话的问题。
  - **`M13.2`（防重复分享去重池、内驱力满足回落与活动状态阅后即焚）**：
    - `runtime/scheduler.py`（覆盖率 **`82%`**）、`runtime/qzone_scheduler.py`（覆盖率 **`90%`**）& `mind/facade.py`（覆盖率 **`97%`**）：维护已看/已发 BV 号与视频标题去重池 `_load_seen_keys`，自动跳过已分享过的视频；闲暇 `bili_surf` 默认静默吸收不刷屏；一旦在群聊或私聊分享过一次视频，立即扣减 `curiosity / social_expression` 内驱力并将 `current_activity` 复位为日常休息状态。
  - **`M13.3`（时间流逝与外界冲浪信息驱动的情绪/人格演化引擎）**：
    - `mind/drives.py`（覆盖率 **`92%`**）& `mind/plasticity.py`（覆盖率 **`95%`**）：实现基于真实流逝时间 $\Delta t$ 的情绪半衰期平复（`apply_temporal_decay_and_circadian`）与自主冲浪对情绪及 7 维性格的动态塑造（`apply_exogenous_surf_affect` + `adapt_from_exogenous_info`）。
  - 全库 62 项测试 100% 通过，总覆盖率 **`90.63% (91%)`**，Pylint **`10.00/10`**，Mypy Strict **84 个源文件 0 错误**。
