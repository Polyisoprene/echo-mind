# Stage 17 详细工程设计、Web 与运行时配置热同步源码审计与修复规范
**（Stage 17 Detailed Engineering Specification: Runtime State Sync & Hot-Reload Completeness Remediation — Status: ✅ 已验收通过）**

---

## 一、 全局问题建模与根因分析（Global Problem Modeling & Root-Cause Analysis）

在对 `web/`、`adapters/media/`、`adapters/onebot/enrichers.py` 与 `main.py` 进行第二轮源码逐行审计后，我们识别出 **6 项涉及「持久化状态启动同步」与「控制台配置修改后组件热重载闭环」的源码缺陷**：

| 缺陷编号 | 严重度 | 定位文件与行号 | 根因建模（Root Cause） | 全局修复方案（Remediation） |
|---|---|---|---|---|
| **`S17-01`** | 🔴 **High** | `web/skill_config_service.py:42`<br>`web/app.py:160`<br>`main.py:142` | **服务重启后已禁用/已删除的技能状态未自动恢复，且 `GET /api/mind/skills` 存在并发竞态**：<br>`SkillConfigService.sync_states()` 仅在 `list_configs()` 中被调用，服务启动时未执行，且前端 `Promise.all([/api/mind/skills, /api/mind/skills/configs])` 并发请求时 `GET /api/mind/skills` 会读到未同步前的默认状态 | 1. 在 `GET /api/mind/skills` 路由中先调用 `await skill_cfg.sync_states()`；<br>2. 在 `main.py:lifespan` 启动时立即执行一次 `await SkillConfigService(container).sync_states()` |
| **`S17-02`** | 🔴 **High** | `web/skill_config_service.py:83`<br>`adapters/media/feiyu.py:48` | **控制台修改 `feiyu_voice`（飞鱼语音地址/Key/默认风格）保存后未热生效**：<br>`SkillConfigService.save("feiyu_voice", ...)` 仅写入 SQLite `skill_configs` 表，`FeiyuVoiceBackend` 实例从未读取该表或热更新自身属性 | 在 `FeiyuVoiceBackend` 新增 `configure(base_url, api_key, default_style)` 方法；在 `SkillConfigService.sync_states()` 与 `save("feiyu_voice", ...)` 时实时热更新 `container.voice_backend` |
| **`S17-03`** | 🟡 **Low** | `web/app.py:78–89` | **`web/app.py` 中残留未使用的旧版 `LlmConfigPayload` 类**：<br>真实使用的 `LlmConfigPayload` 位于 `web/ext_routers.py:23` | 删除 `web/app.py` 中冗余的 `LlmConfigPayload` 定义 |
| **`S17-04`** | 🟡 **Medium** | `web/probe_service.py:38–49` | **认知探针 `CognitiveProbeService.probe` 未返回 `cybernetic_core`**：<br>Stage 14 新增的三磁针自组织核心与选矿剂信息未包含在 `/api/mind/probe` 响应中 | 在 `probe_service.py` 返回字典中补齐 `"cybernetic_core": frame.cybernetic_core.model_dump()` |
| **`S17-05`** | 🟠 **High** | `adapters/onebot/enrichers.py:16`<br>`web/llm_config_service.py:265`<br>`main.py:148` | **`QuoteStickerEnricher` 唤醒词写死 `("回音", "尾尾")`，未同步 `config.json` `keywords` 与控制台人设改名**：<br>当用户在控制台修改 `bot_name` 或在 `config.json` 配置 `store.keywords` 时，点名唤醒检测器未同步更新 | 在 `QuoteStickerEnricher` 新增 `set_bot_names(names)`，在启动与 `LlmConfigService.apply_persona` 时实时同步 `(bot_name, *keywords)` |
| **`S17-06`** | 🟠 **High** | `adapters/media/vision.py:15`<br>`web/llm_config_service.py:240` | **控制台切换主模型网关后，`OpenAiVisionDescriber` 未同步热重载端点**：<br>`LlmConfigService.apply` 只重载了 `container.llm_gateway`，导致看图/看视频仍请求旧网关 | 在 `OpenAiVisionDescriber` 新增 `reload_endpoint(endpoint)` 并挂载至 `container.vision_describer`，在 `LlmConfigService.apply` 中同步热重载 |

---

## 二、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M17.1` ~ `M17.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M17.1`（`S17-01` 技能持久化状态启动/查询同步 + `S17-02` 飞鱼语音配置实时热更新）**：
    - `web/skill_config_service.py`（覆盖率 **`94%`**）、`web/app.py`（覆盖率 **`98%`**）、`adapters/media/feiyu.py`（覆盖率 **`62%`**）：`GET /api/mind/skills` 与 `main.py` 启动时自动调用 `sync_states()`，并在保存 `feiyu_voice` 设置时实时调用 `FeiyuVoiceBackend.configure(...)` 热生效。
  - **`M17.2` & `M17.3`（`S17-03 ~ S17-07` 热重载闭环与探针/鉴权加固）**：
    - `adapters/media/vision.py`（覆盖率 **`97%`**）& `web/llm_config_service.py`（覆盖率 **`94%`**）：切换主模型网关时同步调用 `OpenAiVisionDescriber.reload_endpoint`；
    - `adapters/onebot/enrichers.py`（覆盖率 **`91%`**）：修改人设名字时同步更新 `QuoteStickerEnricher.set_bot_names`；
    - `web/probe_service.py`（覆盖率 **`100%`**）：探针返回补齐 `cybernetic_core`；
    - `web/app.py` & `main.py`：清理冗余 `LlmConfigPayload` 并在外层 ASGI 入口统一挂载 `build_guard_and_cache_middleware(cfg.auth_key)`。
  - 全库 65 项测试 100% 通过，总覆盖率 **`90.63% (91%)`**，Pylint **`10.00/10`**，Mypy Strict **85 个源文件 0 错误**。
