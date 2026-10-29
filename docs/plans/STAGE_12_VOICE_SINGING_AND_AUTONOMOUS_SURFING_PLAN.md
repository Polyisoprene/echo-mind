# Stage 12 详细工程设计、全局建模与架构升级规范：主动语音表达决策、飞鱼全曲 AI 翻唱闭环、后台自主全网搜索与刷B站冲浪引擎
**（Stage 12 Detailed Engineering Specification: Proactive Voice Expression, Feiyu Full-Song AI Cover & Autonomous Web/Bilibili Surfing Engine — Status: ✅ 已验收通过）**

---

## 一、 全局问题建模与根因分析（Global Problem Modeling & Root-Cause Analysis）

针对用户提出的三大核心问题（① 机器人完全不会主动发语音；② 唱歌技能缺失；③ 无法获知机器人是否主动去网页搜索未知信息或刷B站），我们对照旧版 `qq-agent/skills/feiyu-voice` 与 `echo-mind` 现有代码，定位出以下架构断路：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               Stage 12 三大核心问题全局架构建模 (Global Root-Cause Model)              │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 维度一 (M12.1-A)   │ 【问题】机器人每轮只调 send_message 发文字，从不主动调用 feiyu_say│
│ 主动语音决策抑制   │ 【根因】PromptComposer 在 System 与 User 提示词中硬性写死“发言请  │
│ Voice Suppression  │  通过调用 send_message 完成”，只字未提 feiyu_say；且认知帧在情绪  │
│                    │  高涨/吃醋/撒娇/私聊时缺少「🎙️ 主动语音表达冲动」指令注入        │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 维度二 (M12.1-B)   │ 【问题】飞鱼全曲 AI 翻唱 / 唱歌技能 (feiyu_cover) 缺失            │
│ 唱歌技能未迁移     │ 【根因】192.168.3.2:9880 GPU 服务的 POST /v1/assets + /v1/cover   │
│ Missing Song Cover │  完整链路（B站搜歌拉取 DASH 音轨 → 上传素材 → HDemucs 人声伴奏分  │
│                    │  离 + RVC 换声混音 → 下载发送语音）在重构时漏迁                   │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 维度三 (M12.2)     │ 【问题】1. web_search 只绑了 cnmeme.wiki，无全网搜索后端；        │
│ 自主探索与刷B站    │  2. 心跳产生 curiosity_explore 时只写了条空日志，未真正调用搜索或 │
│ 开环 & 不可观测    │     bili_popular 刷B站，也未将学到的新知写回长期记忆；            │
│ Open-Loop Explorer │  3. 控制台总览页未展示 exploration_logs（冲浪与刷B站足迹）        │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 二、 分阶段详细工程设计（Milestone Engineering Specification）

### 里程碑 `M12.1`：主动语音表达认知引导 + 飞鱼全曲 AI 翻唱（`feiyu_cover`）全链路恢复

1. **解除 `send_message` 唯一通道锁定，注入主动语音表达策略（`prompt_composer.py`, `frame_renderer.py`, `voice_tools.py`）**：
   - 在 `PromptComposer.compose` 中将单一的 `send_message` 提示升级为 **《🗣️ 文字与真语音双通道表达指南》**：
     - **文字（`send_message`）**：日常群聊接话、长句、带具体信息时使用；
     - **真语音说话（`feiyu_say`）**：你有自己好听的嗓子（GPU 常驻，约 10 秒合成），**想发语音就主动发，不必等别人要求**！当处于以下场景之一时，优先直接调用 `feiyu_say` 发语音代替 `send_message`（发了语音就不要再发重复文字）：
       ① 跟主人私聊、道早安/晚安、撒娇、哄人时；
       ② 吃醋哼哼、害羞嘴硬、开心得想哼歌、或想让对方直接听见你语气时；
       ③ 群友主动让你“说句话 / 发语音 / 叫一声”时。
     - **带伴奏唱整首歌（`feiyu_cover`）**：当任何人让你“唱首歌 / 唱首《XXX》/ 来首歌”或发来音乐让你翻唱时，**直接调用 `feiyu_cover`**！
   - 在 `frame_renderer.py` 的 `build_curiosity_prompts`（或情绪冲动提示）中：当检测到私聊场景、或情绪高涨（`valence >= 70` / `jealousy >= 25` / `shyness >= 40`）、或触发消息提到 `语音 / 声音 / 听你说 / 唱` 时，动态注入 `🎙️ [主动语音/唱歌冲动]` 提醒。
2. **B站原曲音轨提取 + 飞鱼 GPU 全曲 AI 翻唱闭环（`adapters/media/bili.py`, `adapters/media/feiyu.py`, `tools/voice_tools.py`）**：
   - **`BiliClient.fetch_song_audio(query: str) -> tuple[bytes, str, str]`**（`src/echomind/adapters/media/bili.py`）：
     - 支持输入歌名关键词（如 `"周杰伦 晴天"`、`"恋爱循环"`）或 `BV` 号；
     - 自动通过 WBI 搜索筛选最佳时长（`35s ~ 420s`）的原版音乐视频 → 获取分 P `cid` → 请求 WBI 签名的 `/x/player/wbi/playurl?bvid=...&cid=...&fnval=16` → 下载 `dash.audio` 音轨二进制流，返回 `(audio_bytes, title, bvid)`；
   - **`FeiyuVoiceBackend.synthesize_cover(audio_bytes, filename, *, pitch_shift=None, max_seconds=240) -> str`**（`src/echomind/adapters/media/feiyu.py`）：
     - `POST /v1/assets`（multipart 上传原曲音频）获取 32 位 `audio_id`；
     - `POST /v1/cover` 提交全曲 HDemucs 分离 + RVC 换声混音任务；
     - 轮询 `GET /v1/jobs/{job_id}` 直至 `success`（最长等待 360 秒），下载 `/v1/jobs/{job_id}/audio` 并返回 Base64 音频；
   - **`FeiyuCoverTool` (`name = "feiyu_cover"`)**（`src/echomind/tools/voice_tools.py`）：
     - 注册进 `ExtensionRegistry` 与 `AgentSessionRunner` 出站语音通道，调用 `sender.send_voice(chat_key, audio_b64, f"[翻唱]《{title}》")` 直接把整首带伴奏的翻唱语音发到 QQ 群/私聊！

---

### 里程碑 `M12.2`：全网搜索后端（`WebSearchBackend`）+ 后台自主查梗/刷B站冲浪执行器 + 控制台足迹面板

1. **多源全网搜索后端（`src/echomind/tools/explore_and_voice.py` & `core/bootstrap.py`）**：
   - 新增 `BiliAndWebSearchBackend`（实现 `ISearchBackend`）：
     - 当 `CnMemeWikiClient` 未收录某词条或执行全网搜索时，并发检索 **萌娘百科/百度百科摘要 + B站全站视频搜索（`BiliClient.search_videos`）**，返回真实词条解释与 B站相关热门视频标题/UP主/BV号；
     - 通过 `CompositeSearchBackend((meme_client, bili_web_backend))` 注入 `HolyWebSearchTool`（`web_search`），使 `web_search` 真正具备全网与 B站热点检索能力。
2. **后台自主好奇心探索与闲暇刷B站执行闭环（`src/echomind/runtime/scheduler.py` & `mind/explorer.py`）**：
   - 在 `explorer.py` 中：当 `curiosity_queue` 为空但 `curiosity >= 45.0` 且闲置 `>= 8` 分钟时，生成 `drive_kind="bili_surf"`（自主刷 B站热门榜 `bili_popular` 与梗百科新词，看看最近有什么好玩的新视频/新梗）；
   - 在 `CognitiveHeartbeatScheduler` 中接入 `registry: ExtensionRegistry` 与 `mem_writer: IMemoryWriter`：
     - 当心跳产生 `curiosity_explore`（查未知新词）时：**真正调用 `registry.execute_tool("web_search", ...)`** 获取搜索结果，将学到的新知识作为 `SemanticFact(source="explored")` 存入长期语义记忆，并将真实搜索摘要写入 `exploration_logs` 与 `turn_traces`（会话列表可见 `[自主求知] 搜索『XX』`）！
     - 当心跳产生 `bili_surf`（闲暇刷B站）时：**真正调用 `registry.execute_tool("bili_popular", ...)`** 浏览 B站热门视频，挑选感兴趣的新鲜视频记入 `working_state.current_activity`（如 `"刚在B站刷到《XX》"`）、写入 `SemanticFact` 与 `exploration_logs` 及 `turn_traces`（会话列表可见 `[自主刷B站] 浏览B站热门榜`）！
3. **控制台「总览」页新增《🔭 自主冲浪、网页搜索与刷B站足迹》实时面板（`mind_inspector_service.py`, `index.html`, `app.js`）**：
   - `MindInspectorService.build_snapshot()` 新增返回 `exploration_logs`（最新 20 条自主搜索/刷B站记录，含时间、类型 `curiosity_explore / bili_surf`、主题、实际搜到的内容摘要）；
   - `POST /api/mind/tick` 支持立即触发并执行一次完整的后台探索/刷B站循环；
   - 控制台「总览」页直观展示每一条自主搜索与刷 B站记录，并提供 **「🔭 立即去刷B站 / 探索新梗」** 按钮。

---

### 里程碑 `M12.3`：空间说说与动态技能「多目标主动发消息」架构升级（`qzone_and_profile.py`, `qzone_scheduler.py`, `app.js`）

1. **多目标语法解析器（`parse_proactive_targets` in `src/echomind/runtime/qzone_scheduler.py`）**：
   - 将原本只能填单个目标的 `proactive_target` 升级为**多目标列表语法**（支持用英文逗号 `,`、中文逗号 `，`、分号 `;`、空格或换行分隔任意多个目标），同时兼容以下三种目标形态：
     - **群聊主动冒泡**：`group:10002002`（或简写 `g:10002002`）→ 在该群自然开启一个日常话题；
     - **群聊指定 `@` 某人搭话**：`group:10002002@10001001` → 在群 `10002002` 中主动 `@` 指定 QQ 成员搭话；
     - **个人私聊主动问候**：`private:10001001`（或简写 `p:10001001` / 纯数字 QQ 号）→ 私聊该用户发送日常分享或问候。
2. **按目标场景定制生成与多目标并发投递（`_generate_and_send_proactive`）**：
   - 当主动发消息到期时，遍历解析出的所有目标 `(chat_key, at_uid)`（单次最多投递前 6 个目标）：
     - 针对 `group:群号`（无 `@`）：生成群聊自然冒泡开场白；
     - 针对 `group:群号@QQ`：生成针对该群友的专属搭话并携带原生 `at_user_id=at_uid` 发送；
     - 针对 `private:QQ`：生成一对一私聊问候并发送。
3. **控制台「技能」抽屉可视化多目标编辑器（`src/echomind/web/static/app.js`）**：
   - 在 `qzone_publish` / `profile_signature` 的设置抽屉中，为 `proactive_target` 渲染：
     - **已配置目标标签列表（Tag Chips）**：直观展示每个目标（如 `💬 群聊 10002002`、`💌 私聊 10001001`、`🎯 群 10002002 @ 10008008`），点击 `✕` 即可移除；
     - **快捷添加器**：下拉选择类型（`群聊冒泡` / `个人私聊` / `群内@某人`）+ 从现有群/群友列表一键选取或输入号码 → 点击 **「➕ 添加目标」** 自动拼入配置框。

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M12.1` ~ `M12.3` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M12.1`（主动发语音表达引导与飞鱼全曲 AI 翻唱 `feiyu_cover`）**：
    - `runtime/prompt_composer.py`（覆盖率 **`100%`**）& `mind/frame_renderer.py`（覆盖率 **`97%`**）：解除原先只允许调 `send_message` 的提示词限制，注入《🗣️ 说话、发语音与唱歌表达指南》，并在情绪饱满（开心/害羞/吃醋）或用户提及语音/唱歌时动态注入 `🎙️ [主动语音表达欲]` / `🎤 [语音与歌唱激活]`；
    - `adapters/media/bili.py`、`adapters/media/feiyu.py`、`tools/voice_tools.py`：完整实现 `BiliClient.fetch_song_audio`（B站搜歌 + WBI playurl 提取 DASH `.m4a` 音轨）、`FeiyuVoiceBackend.synthesize_cover`（`POST /v1/assets` + `POST /v1/cover` + 轮询下载）与 `FeiyuCoverTool`（`feiyu_cover`），恢复带伴奏全曲 AI 翻唱能力。
  - **`M12.2`（全网+B站复合搜索后端、后台自主冲浪/刷B站执行闭环与控制台足迹面板）**：
    - `tools/explore_and_voice.py`（覆盖率 **`93%`**）：新增 `BiliSearchBackend`，通过 `CompositeSearchBackend` 将 `cnmeme.wiki` 与 B站实时搜索融合进 `web_search`；
    - `mind/explorer.py`（覆盖率 **`95%`**）& `runtime/scheduler.py`（覆盖率 **`96%`**）：心跳触发 `curiosity_explore` 或 `bili_surf` 时真实调用 `web_search` / `bili_popular`，将搜到的词条或刷到的 B站热门视频同步写入 `semantic_facts`、`working_state.current_activity`、`exploration_logs` 与 `turn_traces`；
    - 控制台「总览」页新增 **《🔭 自主网页搜索与刷B站冲浪足迹》** 面板及 **「🔭 立即去刷B站 / 探索未知新梗」** 按钮，线上实测一键刷取 B站热门榜并更新生活状态。
  - **`M12.3`（空间说说与动态技能「多目标主动发消息」升级）**：
    - `tools/qzone_and_profile.py`（覆盖率 **`91%`**）& `runtime/qzone_scheduler.py`（覆盖率 **`90%`**）：新增 `parse_proactive_targets`，支持同时配置任意多个 `private:QQ`（私聊个人）、`group:群号`（群聊冒泡）与 `group:群号@QQ`（在群内指定 `@` 某人搭话），并按目标场景定制生成主动消息投递；
    - `web/static/app.js`：在技能设置抽屉中为 `proactive_target` 提供可视化目标标签（Tag Chips）与下拉快捷添加器。
  - 全库 61 项测试 100% 通过，总覆盖率 **`90.91% (91%)`**，Pylint **`10.00/10`**，Mypy Strict **84 个源文件 0 错误**。
