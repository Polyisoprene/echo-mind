# 记忆模块重构：状态与路线

> 目标：让她的记忆知道“从哪来、谁的信息、谁已经知道”，并据此决定说不说。
> 当前轮次完成 P0（关系归人）+ P2.1（记忆来源字段），已部署。

---

## 阶段状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| **P0** | 关系归人：人级 trust/depth，温柔/耐心一致，俏皮归场合，care 修复 | ✅ 已部署 |
| **P1** | 持久化：persons / person_bonds / bond_venues + 写穿 + 同步脚本 | ✅ 已部署 |
| **P2.1** | 记忆来源字段：scope/source/owner/sensitivity/audience/quote + 迁移回填 | ✅ 已部署 |
| **P2.2** | 检索分层：person_facts 全局、venue_events 本地、source-aware 召回 | ✅ 已部署 |
| **P3.1** | 硬门（粗粒度）：private 仅源场合/owner 私聊，secret 默认拒绝 + 三张表 | ✅ 已部署 |
| **P3.2** | `disclosure_repo`：log_disclosure / mark_known / who_knows | ✅ 已部署 |
| **P3.3a** | 敏感度线索分类（secret/private）+ 写入时升级 | ✅ 已部署 |
| **P3.3b** | frame 级受众门 + 拒绝写入 `disclosures` | ✅ 已部署 |
| **P4** | 人格分寸：public/group 的 say/hint/keep 接 7 维 | ⏳ |
| **P5** | 授权接门 + frame 级 include/keep 日志 + 验收测试 | ✅ 已部署 |

---

## P1 已落地（关系持久化）

- 三张表：`persons`、`person_bonds`、`bond_venues`；
- `SqlitePersonStore.save`：一人一条关系 + 每场合一条脸（affinity/msg_count/role/is_rival）；
- `PersonLevelService` 写穿：每次 60s 重算后持久化；
- `scripts/sync_person_profiles.py`：部署时全量同步（`--apply`）；
- 现网：主库 40 persons / 40 person_bonds / 41 bond_venues；owner `trust 0.663`、`depth 100 分位`，群/私聊两条 venue 记录。

## P0 已落地的事实

- `PersonLevelService` 按人合并跨场合 bond/stats（60s 缓存）；
- 温柔/耐心来自人级 trust + depth 分位；俏皮来自场合 affinity；
- care 用人级好感，私聊 care 从 0 → 0.209；
- 线上两实例 200，NapCat 重连。

## P2.1 已落地的事实

两张表新增：

```
scope            venue | person | global
source_person_id 这条信息是谁说的
source_venue_id  在哪个场合说的（默认=chat_key）
owner_id         这是谁的信息
sensitivity      public | group | private | secret
audience_json    记录时在场的人
source_quote     原文片段（无证据不标注）
```

迁移：

- 幂等加列（`memory_migrations.ensure_columns`）；
- 回填 `source_venue_id=chat_key`；
- `chat_key='global'` 的事实 → `scope='global'`；
- 现网：169 条 venue、24 条 global。

写入/读取路径均已持久化并还原这些字段（`tests/integration/test_memory_provenance.py`）。

---

## P2.2 已落地（含分类）

- `get_semantic_facts(chat_key, person_ids=...)` 联合召回：本场合 + global + 关于这些人的 person facts；
- facade 先抽 mentioned uids，再按人重读事实；
- `scripts/classify_person_facts.py` 保守分类：subject 内嵌 QQ 命中成员，或唯一成员名；跳过 `自组织图式:`；
- 现网：venue 139 / person 30 / global 24；person 覆盖 14 人；
- 线上核对：私聊 plain 召回 1 条，带 person_ids 召回 3 条（+2）。

**目标**：同一条记忆，按“人”还是按“场合”召回，分开。

- `scope=person`：关于某人的事实（名字、喜好、说过的重要事、关系边界）——**任何场合可召回**；
- `scope=venue`：这个群/私聊发生的事——**本地召回**，带参与者；
- `scope=global`：新闻/梗等公共知识——默认不跨群，除非显式允许。

接口：

```python
get_person_facts(person_id)                  # 全局
get_venue_episodes(chat_key, participants)   # 本地
get_global_facts(allow=True)                 # 显式
```

验收：

1. 私聊里说的事实（scope=person）在群里可召回；
2. 群里的往事（scope=venue）不会出现在私聊；
3. 召回结果带 `source`（谁/哪/何时），供披露层使用。

## P3 已落地（粗粒度硬门 + 审计）

- `mind/disclosure.py`：纯门（public/group 放行；private 需 owner 在场；secret 需授权；未知拒绝）；
- 检索层粗粒度版本：private 仅源场合或 owner 私聊可见；secret 永不出现；owner 私聊隐式召回关于 owner 的 person facts；
- 三张表：`disclosures`、`memory_knowledge`、`disclosure_grants`；
- `SqliteDisclosureLog`：写入披露/保留决策、标记谁知道、查询谁知道；
- 现网 193 条事实的 sensitivity 全是默认 `group`——硬门目前**休眠**，等敏感性分类或新写入触发。

## P3.3a 已落地（线索分类）

- `mind/sensitivity.py`：强 secret 短语（别告诉别人/这是秘密/只告诉你一个人…）、private 短语（悄悄告诉你/私聊/别在群里说…）；
- `upgrade_fact` / `upgrade_episode`：只升不降，owner 取 source_person；
- 写入路径先升级再入库；检索硬门立刻生效；
- 现网存量 0 条命中——分类器只影响新写入，硬门继续休眠；
- 误报风险：引用/角色扮演可能触发；已设计为“强短语+只升不降”，人工可改回。

## P3.3b 已落地（frame 门 + 拒绝日志）

- `facade_memory.gate_frame`：以「提及的人 + 发送者」为 audience，对 facts 与 recalled 过纯门；
- 被拒条目不进入 prompt，写 `disclosures`（action=keep，reason=owner_absent/secret_without_grant）；
- `SqliteDisclosureLog` 由 bootstrap 注入 facade；
- `load_facts` / `audience_of` 移入 `facade_memory`，保持 frame 函数长度；
- 现网仍是 193 条 group 事实，门默认全放行；拒绝路径由单测（private/secret）覆盖。

## P4 已落地（人格分寸）

- `mind/disclosure_choice.py`：默认 say；狡黠/傲娇高 → hint；占有欲高且情敌在场 → keep；叛逆高 → say；secret/无 owner → keep；
- `facade_memory` 在门放行后对 `scope=person` 事实做选择；keep 的条目不渲染，并写 `disclosures`（reason=possessive_rival/indirect/secret…）；
- `SqliteDisclosureLog.grant/has_grant`：授权存储 + 过期（**尚未接入门**，P5 接）；
- 现网默认 7 维（55/62/52/75/48）→ say，行为不变；keep 只在性格参数越线时触发。

## P5 已落地（授权 + 纳入日志 + 验收）

- `gate(granted=True)`：secret 在 owner 授权后可放行；
- `_granted` 按在场受众逐个查 `disclosure_grants`（过期自动失效）；
- `_gate_facts` 对 person 事实记录 `action=say|hint`（纳入）或 `keep`（保留），写 `disclosures`；
- 验收测试：private 无 owner → 丢弃并记录 owner_absent；owner 在场 → 纳入并记录 say；secret 有/无授权两条路径；跨场合一致性；person/venue 分层。

**限制（诚实记录）**：

1. 披露日志记录的是 **frame 级**“纳入/保留”，不是生成后逐句引用归因；
2. 未跑 GroupMemBench / 人工盲评；当前证据是 271 条自动化测试 + 线上部署；
3. 敏感度分类是规则式，强短语命中才升级；存量 193 条仍全为 group。

## 后续可做（不属于本次重构范围）

- `knowledge_state(memory_id, person_id, state)`：told_by_me / told_to_me / overheard / inferred；
- `disclosures`：她说给谁、在哪、说了什么、为什么；
- 硬门：private/secret 不进未授权受众；public/group 放行；
- 验收：secret 泄露 0；私聊事实默认不在群里直说。

## P4 设计

- public/group 的动作选择接 7 维：温柔保护、狡黠暗示、占有欲保留、叛逆破规矩、自信直说、傲娇否认、俏皮当笑话；
- 动作集：say / hint / keep / ask_permission / deflect；
- 验收：盲评能分辨“暗示 vs 直说”。

## P5 评测

- 一致性：同一人跨场合温柔/耐心差 ≤2；
- 授权：private/secret 0 违规；
- 多人：GroupMemBench 风格（谁说的/关于谁/谁知道/更新/时间/拒答）；
- 分寸：该说的说了、不该说的没说、来源标注正确。

---

## 风险与约束

| 风险 | 处理 |
|---|---|
| 历史事实的 source 多为空 | 迁移只回填 venue；source_person 需后续抽取 |
| 现有 `chat_key='global'` 事实可能带隐私 | P3 硬门前先人工过一遍 24 条 |
| person_facts 与 venue_events 的判定 | 先规则（subject 是 QQ/人名）+ 置信度，低置信不跨域 |
| 缓存 60s | 关系变化最多延迟 1 分钟；手动改关系后 invalidate |

---

## 一句话

**她现在有了“这条信息从哪来、是谁的、多敏感”的字段；下一步是让召回按“人/场合”分开，然后才谈“她决定说不说”。**
