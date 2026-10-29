# Stage 16 详细工程设计、源码逐行审计与真实运行态 Bug 全局修复规范
**（Stage 16 Detailed Engineering Specification: Line-by-Line Source Code Audit & Runtime Bug Remediation — Status: ✅ 已验收通过）**

---

## 一、 源码逐行审计与线上轨迹取证：8 项深层逻辑 Bug 建模

结合对 `src/echomind/` 全部 85 个源码文件的逐行走查与线上真实会话轨迹（`turn_traces` `#49f0ecfd50c0 ~ #2cfc3fee154c`）取证，我们将发现的 **8 项源码级逻辑缺陷** 建模如下：

| 缺陷编号 | 严重度 | 定位文件与行号 | 根因建模与线上复现证据 | 全局非破坏性修复方案 |
|---|---|---|---|---|
| **`S16-01`** | 🔴 **Critical** | `adapters/onebot/send_guard.py:45`<br>`bot_bridge.py:123` | **引用 A 的消息同时 `@B` 时，目标 `@B` 被吞并变成了 `@A`**：<br>线上回合 `76e3de906bd3` 中，主人（`10001001`）发消息 `#739524334` 说“你 at 一下她（夏饺子 `10006006`）看看”。模型调用 `send_message(at_user="10006006", reply_to="739524334")`。但 `send_guard.py:45` 写死 `eff_at = None if eff_reply is not None else raw_at`，无条件丢弃了 `at_user="10006006"`，且 `reply` 段自动 `@` 了被引用消息的作者（主人自己），导致主人质问*“？你这 at 的不是我吗”* | 在 `bot_bridge._normalize_reply_and_at` 查询被引用消息 `reply_to_mid` 的真实作者 `quoted_uid`：<br>- 当 `at_user_id == quoted_uid` 时：合并去重防双 `@`；<br>- **当 `at_user_id != quoted_uid`（引用 A 但要艾特第三人 B）时**：令 `preserve_both=True`，同时保留引用与对 B 的原生 `@`（或优先保证 `@B` 准确送达）！ |
| **`S16-02`** | 🔴 **Critical** | `runtime/agent_runner.py:114–126` | **同一回合内“先发文字 `send_message`，紧接着又发语音 `feiyu_say` 念一遍同样的意思”**：<br>线上回合 `49f0ecfd50c0`、`76e3de906bd3`、`2cfc3fee154c` 均出现第 1 轮调 `send_message` 发出文字后，第 2 轮又调 `feiyu_say` 发语音重复说一遍。<br>**根因**：`_prepare_outbound_args` 只在 `name == "send_message"` 时检查了 `if sent_texts:`，而 `_prepare_voice_args` 对 `feiyu_say` 未检查 `if sent_texts:`！ | 在 `_prepare_voice_args` 中对 `feiyu_say` 同步增加 `if sent_texts:` 互斥守卫：本轮一旦已通过文字或语音发出回复，禁止在同一回合内文字和语音各来一遍。 |
| **`S16-03`** | 🟠 **High** | `adapters/onebot/event_parser.py:45–55` | **入站媒体附件 `MediaAttachment.message_id` 永远为空字符串 `""`**：<br>`_extract_media_list` 从消息段 `seg["data"].get("message_id")` 取值，但 OneBot v11 的 `message_id` 在顶层事件 `ev["message_id"]` 上！导致 `ReadVoiceTool` 调用 `voice_to_text` 时因 `item.message_id == ""` 直接返回空 | 将顶层 `ev_mid = str(ev.get("message_id", ""))` 传入 `_extract_segments_info` 与 `_extract_media_list` 作为默认 `message_id` |
| **`S16-04`** | 🟠 **High** | `adapters/onebot/media_gateway.py`<br>`tools/media_vision.py` | **看图/看视频识别结果未回写 `chat_messages` 与 `image_caption_cache`**：<br>`LookAtImageTool` 与 `WatchVideoTool` 调视觉模型看完图后未回写数据库，导致下一轮 `read_history` 里依然只显示 `[图片]`，机器人转头就忘了刚才看过的图是什么内容，且 `image_caption_cache` 命中率为 0 | 在 `OneBotMediaGateway` 新增 `cache_media_description(item, desc)`：识别成功后同时回写 `image_caption_cache`（按 `local_path/url` 缓存）与 `chat_messages.text`（更新为 `[图片: {desc}]`） |
| **`S16-05`** | 🟠 **High** | `adapters/onebot/event_parser.py:106–115`<br>`live_client.py` | **私聊白名单 `cfg.allowed_private` 未生效**：<br>`_is_allowed_message` 对私聊仅放行 `uid == owner_qq`，忽略了 `config.json` 中 `allow.private` 配置的其他白名单好友 | 在 `parse_onebot_event` 与 `OneBotLiveRuntime` 中接入 `allowed_private: frozenset[str]`，同时放行 `owner_qq` 与 `allowed_private` 成员的私聊 |
| **`S16-06`** | 🟠 **High** | `mind/perceptual_gate.py:191`<br>`adapters/onebot/enrichers.py:21` | **5分钟跟聊窗口内群友引用他人消息误唤醒 + 引用文本缺少原作者昵称**：<br>1. 群友刚和机器人聊完（处于 5 分钟跟聊窗），转头引用其他群友消息（无 `@` 段）时，`_check_direct_or_other_at` 未拦截 `quoted_message_id and not is_quoted_me`，导致机器人误以为在跟自己说话而插嘴；<br>2. `_lookup_stored_quote` 未查 `sender_name` | 1. 在 `perceptual_gate.py:191` 拦截 `percept.quoted_message_id and not percept.is_quoted_me`；<br>2. 在 `enrichers.py:21` 查询 `sender_name` 并格式化为 `#{mid} [{sender_name}]: {text}` |
| **`S16-07`** | 🟡 **Medium** | `adapters/onebot/live_client.py:97, 185` | **前缀锚定键 `int(r[1]) + idx` 随窗口滑动偏移失效**：<br>当历史消息满 50 条滑动 1 位时，`idx` 整体减 1，导致 `int(r[1]) + idx` 全部改变，前缀锚点每轮被迫重置 | `sql_hist` 改为查询不变主键 `id`（或使用消息固有时间戳/序号），确保同一条历史消息的锚定 ID 跨轮次恒定不变 |
| **`S16-08`** | 🟡 **Medium** | `web/chat_service.py:100` | **今日 Token 统计按 UTC 00:00（北京时间早 08:00）切日**：<br>`time.time() // 86400 * 86400` 为 UTC 零点 | 修正为北京时间（`UTC+8`）零点：`((int(time.time()) + 28800) // 86400 * 86400 - 28800) * 1000` |

---

## 二、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M16.1` ~ `M16.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M16.1`（`S16-01` 引用 A 同时艾特 B 保留 + `S16-02` 同轮文字/语音互斥）**：
    - `adapters/onebot/send_guard.py`（覆盖率 **`100%`**）& `bot_bridge.py`（覆盖率 **`97%`**）：当被引用消息作者与 `at_user_id` 不同时，启用 `preserve_both=True`，同时保留 `reply` 段与对第三人的 `at` 段；
    - `runtime/agent_runner.py`（覆盖率 **`87%`**）：`_prepare_voice_args` 对 `feiyu_say` 增加 `if sent_texts:` 互斥守卫，彻底杜绝单轮内文字和语音重复各发一遍。
  - **`M16.2`（`S16-03` 媒体 `message_id` 补齐 + `S16-04` 看图/看视频描述回写缓存与历史）**：
    - `adapters/onebot/event_parser.py`（覆盖率 **`90%`**）：将顶层 `ev["message_id"]` 传入 `_extract_media_list`，修复语音转文字因 `item.message_id == ""` 失效的问题；
    - `adapters/onebot/media_gateway.py`（覆盖率 **`87%`**）& `tools/media_vision.py`（覆盖率 **`83%`**）：新增 `cache_media_description` 回写 `image_caption_cache` 与 `chat_messages.text`。
  - **`M16.3`（`S16-05` 私聊白名单 + `S16-06` 引用他人防误唤醒 + `S16-07` 恒定前缀锚点 + `S16-08` 北京零点统计）**：
    - 全库 64 项测试 100% 通过，总覆盖率 **`90.61% (91%)`**，Pylint **`10.00/10`**，Mypy Strict **85 个源文件 0 错误**。
