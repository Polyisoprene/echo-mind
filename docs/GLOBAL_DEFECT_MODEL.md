# 全局缺陷模型（Global Defect Model）

目标：从全局数据流出发，给每个 review 问题定级、估算影响面、排依赖，再逐批修复。
本文件是修复台账；每轮更新状态。

## 1. 数据流与缺陷位置

```
percept
  → evaluate_incoming（bot 信念、感知门）          [D1]
  → build_cognitive_frame（事实/往事/硬门/分寸）    [D2, D4-D9, D12]
  → prompt 组装（人格块位置、扩展）                [D14, D17]
  → 生成
  → on_turn_completed（对话缓冲、工作状态）         [D2, D16]
  → consolidation（来源/敏感度/告知史）             [D4, D7]
  → retrieval（人/场合/global）                     [D6, D8, D12]
```

影响面记号：**R** = 受影响范围（all=所有会话，person=单人记忆，one=单条），**L** = 发生概率，**S** = 严重度（1-5）。

## 2. 缺陷台账

| ID | 问题 | 根因 | 影响 | R / L / S | 状态 |
|---|---|---|---|---|---|
| D1 | bot 信念跨群串 | `_BELIEFS` 模块级 dict | A 群断言“某人是 bot”，B 群也按 bot 处理 | all / 2 / 3 | ✅ 已修 |
| D2 | 探针对话上下文跨会话 | 单个 `DialogueContext` 共享 | 私聊/群聊的话进入彼此探针上下文 | all / 4 / 3 | ✅ 已修 |
| D3 | 禁用词按“上一轮会话”生效 | `_active_bans` 单值 | 切群后误拦或漏拦 | all / 4 / 3 | ✅ 已修 |
| D4 | 告知史空转 | 无代码调用 `mark_known` | `memory_knowledge` 0 行，“谁知道”不可用 | person / 5 / 4 | ✅ 触发器 |
| D5 | 授权无法创建 | 只有 `grant/has_grant` 适配器 | `disclosure_grants` 0 行，secret 永远放不出 | person / 5 / 4 | ✅ CLI |
| D6 | 26 条 global 事实未审 | 迁移默认 `scope=global`、`sensitivity=group` | 任何群可见，可能含私人信息 | all / 3 / 5 | ✅ 已审 |
| D7 | 敏感度误报不可逆 | 分类器只升不降、无复核入口 | 一条误判 secret 永久不可召回 | one / 2 / 4 | ✅ 复核台 |
| D8 | P1 表只写不读 | 检索仍实时计算 | 控制台/工具读表得到快照，可能与实时不一致 | person / 3 / 2 | ✅ 读表 |
| D9 | 披露日志不是“实际说了” | 只在 frame 记 include/keep | 168 行全是 `say/persona`，无法审计真正说出的内容 | all / 5 / 3 | ✅ 归因 |
| D10 | 人格特质按场合分裂 | `persona_traits` 6 条 global + 3 条 group | 读路径本就全局（无 chat 过滤），`chat_key` 只是来源 | person / 4 / 4 | ✅ 非缺陷 |
| D11 | 好感常数未重标定 | `AFFINITY_OFFSET/SPAN` 仍是 legacy | 人级 care 排序可能偏 | person / 3 / 3 | ⏳ |
| D12 | FACTS_V2 未接新字段 | 读路径默认 off，新 provenance 只在 legacy | 一旦开启，来源/敏感度全丢 | all / 2 / 4 | ✅ 禁启 |
| D13 | token 端点仅靠 loopback | `/api/session/token` 对本机任意进程发 token | 同机反代/恶意进程可拿 token | host / 2 / 4 | ✅ Host/Origin |
| D14 | 人格块在 user 消息 | A3 placement 实验撤回后未再动 | 指令权威性/近因偏置 | one / 3 / 2 | ⏳ |
| D15 | 特质模型与命名 | HEXACO 命名、5 条固定涌现特质、无语义检索 | 人格解释力/自适应不足 | persona / 5 / 3 | ⏳ |
| D16 | 工作状态多写入点 | 9 处 `save_working_state`，scheduler 与 turn 可并发 | 后写覆盖，情绪/驱动漂移 | all / 3 / 3 | ⏳ 评估完 |
| D17 | 扩展好感阈值旧标尺 | 配置仍是 50/200/500/1000 | 扩展侧等级与核心分位不一致 | one / 5 / 2 | ⏳ |
| D18 | 披露日志无保留策略 | 只增不删 | 168 行已在短时间累积 | all / 5 / 2 | ✅ 清理 |
| D19 | 缺外部评测 | 只有单测/集成 | 无法证明跨会话一致性与授权边界 | all / 5 / 3 | ⏳ |
| D20 | 本地领先 origin 24 提交 | 多轮提交未 push | 远端缺 P0-P5/P1 | ops / 5 / 3 | ⏳ |

## 3. 已修（D1-D9、D12、D13、D18）

- `bot_belief`：`_BELIEFS` 改为 `dict[chat_key, dict[uid, score]]`；`set_beliefs(chat_key, ...)`、`apply_belief(chat_key, sender_id)`；感知门按 `percept.chat_key` 取。
- `DialogueContext`：内部改为 `dict[scope, deque]`；`add/note/lines/clear` 都带 scope；facade 用 `percept.chat_key` / `outcome.chat_key`。
- `AgentSessionRunner`：`_active_bans` 改为 `dict[chat_key, tuple]`；发送/救援按当前 `chat_key` 取。
- 新增隔离测试：信念、对话、禁用词各自跨会话不串。

### D4 告知史生产者

- `semantic_facts` / `episodic_memories` 的 INSERT/UPDATE 触发器写入 `memory_knowledge`：
  `source_person_id → told_to_me`，`owner_id → knows`；
- 迁移时回填存量；主库现有 **29** 条知识行（均为 `knows`：owner 有值、source 为空），新写入会按 source/owner 分别记；

### D5 授权入口

- `scripts/grant_disclosure.py --memory-id --grantee --by [--expires-days]`；
- 门仍按 `has_grant` 判断，授权现在有可执行入口（CLI，非 UI）。

### D6 global 事实审计

- 主库 26 条、全部是 B 站/梗 Wiki 的公开网页片段，`owner/source` 全空；
- 统一标 `sensitivity=public`，`scope=global` 不变；小沫库 6 条同样处理；
- 结论：无个人隐私外泄；成人向内容属于内容策略，不在本轮隐私范围。

### D7 敏感度复核

- `sensitivity_reviews` 表 + `SqliteSensitivityReviewer`；
- `scripts/review_sensitivity.py --list` 只列 `private/secret`；`--id N --set group --reason ... --apply`；
- 复核写入审计行，误报可降级。

### D8 P1 读取切表

- `SqlitePersonStore.load_with_ts` 返回画像与最近 `updated_ms`；
- `PersonLevelService` 在缓存失效时先读表，快照在 TTL 内则直接使用，否则重算并写穿；
- 重启后不会立刻重算，只有在快照超过 60s 时才回退到实时计算。

### D9 生成后引用归因

- frame 记录本会话纳入的 person 事实（`_included`，回合结束即弹出）；
- `attribute_reply` 用“主体出现或 8 字重叠”保守判断回复是否引用；
- 命中写 `disclosures(action='said', phase='post', reason='reply_overlap')`。
- **限制**：这是词面重叠启发式，不是语义归因；只记录“可能说了”，不保证精确。

### D18 披露日志保留

- `SqliteDisclosureLog.prune(before_ms)` + `scripts/prune_disclosures.py --days 30 [--apply]`。

### D12 FACTS_V2 禁启

- `SqliteMemoryRepository` 构造时若 `FACTS_V2=on` 直接 `RuntimeError`；
- 理由：claim 行没有 scope/owner/sensitivity，开启会静默丢来源；
- 默认 off，行为不变；要给 v2 做 provenance 平权后再解禁。

### D13 token 端点

- 新增 `is_loopback_request`：client、Host、Origin 三者都必须是 loopback；
- `/api/session/token` 只在三者都通过时返回 token，否则返回空串；
- 中间件的 loopback 判定也加 Host 检查；
- 反代若保留公网 Host/Origin，不再被当成 loopback。

### D16 评估（未修）

- 共 **9 处** `save_working_state`：facade 2、facade_autonomy 2、qzone 2、scheduler 1、consolidator 1、chord_gateway 1；
- scheduler 的自主 tick 与 turn 的回写可并发，属于 last-writer-wins；
- 修法：单写者队列或快照版本号 + 冲突重放，下一轮处理。

### D10 复核结论：非缺陷

- `sync_persona_traits` 的查询没有 `chat_key` 过滤，返回全局 top 12；
- `chat_key` 只作来源标记，不是读取作用域；所以不存在“群里长出的习惯私聊没有”的行为分裂。

## 4. 修复顺序（按依赖）

1. **披露闭环**：D4 告知史生产者 → D5 授权入口 → D6 global 审计 → D7 复核/降级。
2. **读取与审计**：D8 P1 读表 → D9 生成后归因 + D18 保留策略。
3. **人格一致性**：D10 特质收口 → D11 常数重标定 → D16 工作状态单写者。
4. **安全与兼容**：D12 FACTS_V2 → D13 token → D14 人格块位置。
5. **模型与评测**：D15 特质模型 → D17 扩展阈值 → D19 外部评测。
6. **发布**：D20 push。

## 5. 验收口径

- 每个 D 项：有复现/证据、有测试、有部署验证；
- D1-D3 已满足：`tests/unit/test_bot_belief.py`、`test_dialogue_context.py`、发送拦截集成测试；
- 全量门禁：286 passed / 92%。
