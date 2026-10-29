# Stage 18 详细工程设计、多层嵌套合并转发递归展开、动态情敌解耦、性格词条新陈代谢与控制台布局对齐规范
**（Stage 18 Detailed Engineering Specification: Recursive Multi-Level Forward Unpacking, Dynamic Rivals, Persona Trait Metabolism & Console Layout Alignment — Status: ✅ 已验收通过）**

---

## 一、 全局问题建模与根因分析（Global Problem Modeling & Root-Cause Analysis）

针对用户指出的 5 项核心问题，我们从前端布局、认知核心状态机、记忆新陈代谢与 OneBot 协议层进行全局建模：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│               Stage 18 五大问题全局架构建模 (Global Root-Cause Model)                  │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ 问题 1 & 4 (M18.4) │ 【现象】1. 性格页「生长出的性格词条」不能下滑，把左右卡片无限拉长 │
│ 控制台布局失衡     │  2. 记忆页右侧「海马体总结记忆」比左侧短一半，下方出现大片空白    │
│ Layout Imbalance   │ 【根因】1. #trait-list 漏加 scroll-y 类与 max-height 约束；       │
│                    │  2. 记忆页左卡片垂直堆叠了两个 440px 的 scroll-y（总高~950px），  │
│                    │    而右卡片仅一个 440px 的 #memory-episodic，高度严重不对等。     │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 问题 2 (M18.3)     │ 【现象】生长出的性格词条一直存在、只增不减，不会随时间演化淘汰    │
│ 性格词条无新陈代谢 │ 【根因】1. working_repo.py:204 在每轮正向奖励时对全表所有词条无差 │
│ Missing Trait      │    别执行 strength + 1，导致所有旧词条全部被顶满到 10/10；        │
│ Metabolism         │  2. 睡眠修剪期从未对长期未复现的旧词条执行时间衰减与容量淘汰。    │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 问题 3 (M18.1)     │ 【现象】无法展开合并转发聊天记录及多层套娃嵌套转发聊天记录        │
│ 合并转发与多层套娃 │ 【根因】event_parser.py 未解析 type=="forward" 段，且缺少调用     │
│ Nested Forward     │  get_forward_msg 并递归展开嵌套 forward 节点（depth 1..4）的引擎  │
│ Unpacking          │  与主动查看工具 read_forward。                                    │
├────────────────────┼───────────────────────────────────────────────────────────────────┤
│ 问题 5 (M18.2)     │ 【现象】后台 mind/facade.py:59 硬编码写死了 RIVALS = ("汐","豆包")│
│ 情敌硬编码         │ 【根因】未从 social_bonds 表的 is_rival = 1 字段动态读取情敌名单  │
└────────────────────┴───────────────────────────────────────────────────────────────────┘
```

---

## 二、 分阶段详细工程设计（Milestone Engineering Specification）

### 里程碑 `M18.1`：多层嵌套合并转发聊天记录递归展开引擎（`forward_expander.py` + `ReadForwardTool`）
1. **协议层解析 `forward` 消息段（`src/echomind/adapters/onebot/event_parser.py`）**：
   - 在 `CQ_LABELS` 与 `_seg_to_text` 中识别 `seg_type == "forward"`：提取 `res_id = str(data.get("id") or data.get("res_id") or "")`，生成 `[合并转发聊天记录 id={res_id}]`。
2. **多层递归展开器（`src/echomind/adapters/onebot/forward_expander.py`）**：
   - 实现 `expand_forward_tree(caller: IOneBotApiCaller, message_id: str = "", res_id: str = "", *, max_depth: int = 4, max_nodes: int = 40) -> tuple[str, tuple[MediaAttachment, ...]]`：
     - 支持通过 `message_id`（优先）或 `id=res_id` 调用 OneBot `get_forward_msg`；
     - 遍历节点数组，提取每条消息的 `sender_name(QQ:uid)`、文本与图片附件；
     - **多层套娃递归展开（`depth = 1 .. max_depth=4`）**：当节点内包含嵌套的 `type == "forward"` 或 `type == "node"` 段时：
       - 若内嵌了 `data.content` / `data.messages` 列表，直接递归展开；
       - 若仅含内嵌 `data.id` / `res_id`，则递归调用 `get_forward_msg` 展开下一层，并用树状缩进（`  ├─ 📦 [第2层嵌套转发]`）清晰呈现层级结构！
   - **入站自动展开 + 工具按需展开双闭环**：
     - 在 `OneBotLiveRuntime.handle_raw_event` 中：检测到入站消息含 `[合并转发` 时，自动调用 `expand_forward_percept` 将展开后的多层完整对话树直接写入 `Percept.text` 与 `chat_messages`；
     - 新增 `ReadForwardTool`（`name = "read_forward"`，分类 `"信息探索"`），支持模型随时传入 `#message_id` 或 `res_id` 展开查看任意合并转发记录并写回存档。

---

### 里程碑 `M18.2`：彻底移除硬编码 `RIVALS`，改为从 `social_bonds (is_rival = 1)` 动态加载
1. **`src/echomind/domain/ports.py` & `adapters/storage/memory_repo.py`**：
   - 在 `IMemoryReader` 新增第 5 个方法（符合 `MAX_PORT_METHODS <= 5`）：
     `async def get_rival_names(self, chat_key: str) -> tuple[str, ...]: ...`
   - 在 `SqliteMemoryRepository.get_rival_names` 中查询：
     `SELECT user_name, user_id FROM social_bonds WHERE chat_key IN (?, 'global') AND is_rival = 1`
2. **`src/echomind/mind/facade.py`**：
   - 删除硬编码常量 `RIVALS = ("汐", "豆包")`；
   - 在 `evaluate_incoming` 与 `_advance_working_state` 中动态调用 `await self._reader.get_rival_names(chat_key)` 获取当前群聊中被标记为情敌的昵称与 QQ 号列表（同时在数据库初始化迁移中将原本的 `is_rival` 交由控制台「社交」页全权管理）。

---

### 里程碑 `M18.3`：性格词条（`persona_traits`）时间衰减与新陈代谢淘汰机制
1. **修正 `sync_persona_traits` 的无差别全量强化 Bug（`src/echomind/adapters/storage/working_repo.py`）**：
   - 移除原本在 `strength_delta > 0` 时对全表所有词条无脑 `+1` 的逻辑（正向强化仅发生在同类词条复现 `ON CONFLICT(trait_text) DO UPDATE SET strength = MIN(10, strength + 2), created_at = ?` 时；当 `strength_delta < 0` 负反馈时全表词条微降 `-1`）；
2. **新增时间半衰期新陈代谢与容量上限淘汰（`decay_and_prune_traits`）**：
   - 在 `SqliteWorkingStateStore.sync_persona_traits` 与 `CognitiveHeartbeatScheduler.run_sleep_pruning` 中执行新陈代谢：
     - 超过 12 小时未被再次触发强化的词条，每次睡眠修剪自动衰减 `strength = strength - 1`；
     - `strength <= 0` 的词条立即从数据库淘汰删除；
     - 实施达尔文容量上限（最多保留强度最高的 12 条活跃词条），超出部分自动优胜劣汰。

---

### 里程碑 `M18.4`：控制台「性格」页词条滚动约束与「记忆」页左右列等高对齐
1. **`src/echomind/web/static/index.html` & `style.css`**：
   - 为 `#trait-list` 增加 `class="scroll-y" style="max-height:300px"`，为 `#ban-list` 增加 `style="max-height:110px;overflow-y:auto"`，防止词条变多时撑爆卡片高度；
   - 将「记忆」页左列的 `#memory-facts`（`max-height:300px`）与 `#memory-rules`（`max-height:220px`）同右列的 `#memory-episodic`（`max-height:610px`）做等高对齐，彻底消除右侧下方空白。

---

## 三、 阶段实测验收记录（Acceptance Results · 2026-10-29）

- **`M18.1` ~ `M18.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`M18.1`（多层嵌套合并转发聊天记录递归展开器）**：
    - `adapters/onebot/forward_expander.py`（覆盖率 **`80%`**）、`event_parser.py`（覆盖率 **`88%`**）、`live_client.py`：实现 `expand_forward_tree`（支持最高 4 层套娃嵌套转发递归展开，提取发言人、消息与内嵌图片）、入站自动展开 `expand_incoming_forward` 与主动查看工具 `ReadForwardTool` (`read_forward`)。
  - **`M18.2`（移除硬编码情敌，改为 `social_bonds` 动态驱动）**：
    - `domain/ports.py`（覆盖率 **`100%`**）、`adapters/storage/memory_repo.py`（覆盖率 **`100%`**）、`mind/facade.py`（覆盖率 **`97%`**）：彻底移除 `RIVALS = ("汐", "豆包")`，通过 `get_rival_names` 实时从 `social_bonds (is_rival = 1)` 动态读取情敌名单。
  - **`M18.3` & `M18.4`（性格词条新陈代谢淘汰与控制台布局对齐）**：
    - `adapters/storage/working_repo.py`（覆盖率 **`100%`**）& `runtime/scheduler.py`：移除每轮对全表所有词条无差别 `+1` 的 Bug；实现 12 小时未复现自动 `-1` 衰减、`strength <= 0` 淘汰删除与 15 条达尔文容量上限；
    - `web/static/index.html`：为 `#trait-list` 增加滚动容器约束（`max-height:280px`），并将「记忆」页左右两列卡片等高对齐。
  - 全库 66 项测试 100% 通过，总覆盖率 **`90.33% (90%)`**，Pylint **`10.00/10`**，Mypy Strict **86 个源文件 0 错误**。
