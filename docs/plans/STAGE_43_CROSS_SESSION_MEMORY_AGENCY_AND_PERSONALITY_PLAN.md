# Stage 43：跨会话记忆、跨会话发送、FTS5、BDI 意图栈、partial 收口与 HEXACO 映射

> 状态：**P0 建模 + 纯领域基础已完成；P1-P5 待实现**（2026-11-02）。
> 约束：不编造数据；任何数值必须有公开论文、公开文档或本机工程测量支撑。
> 目标不是“加一个开关”，而是让回音在**来源、受众、意图、检索和表达**上成为连续的行动者。

---

## 0. 总原则

1. **能力优先于硬限制**：跨会话发送是“她可以决定发到哪”，不是“只允许发当前会话”。
2. **隐私不是全隔离**：按 `MEMORY_SOURCE_AND_DISCLOSURE.md` 的 source/audience/disclosure 模型处理。
3. **先 shadow，再读路径，再写路径**：任何改变检索或发送的实现，默认关闭，先对照基线。
4. **不伪造心理测量**：HEXACO 映射没有数据就只做构念覆盖审计，不编造相关系数或权重。
5. **六边形依赖**：`domain` / `mind` 不导入基础设施；所有存储/网络留在 adapters/runtime。

---

## 1. 六项功能与依赖图

```text
                    ┌────────────────────┐
                    │ 跨会话记忆          │
                    │ source / audience   │
                    └─────────┬──────────┘
                              │ 记忆与承诺
                    ┌─────────▼──────────┐
                    │ 跨会话发送          │
                    │ text / voice target │
                    └─────────┬──────────┘
                              │ 结果
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────▼─────────┐ ┌───────▼────────┐ ┌────────▼────────┐
│ BDI 意图栈         │ │ FTS5 词法检索   │ │ partial 收口     │
│ commitment/TTL    │ │ SQLite FTS5     │ │ auth/attribution │
└─────────┬─────────┘ └───────┬────────┘ └────────┬────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │ HEXACO 覆盖审计     │
                    │ 不先做数值映射      │
                    └────────────────────┘
```

依赖顺序：

```text
S43-01 跨会话记忆（source/audience）
  → S43-02 跨会话发送（目标解析 + 事后校验）
  → S43-03 BDI 意图栈（承诺/未完成意图）
  → S43-04 FTS5（词法候选，不替换现有检索）
  → S43-05 partial 收口（选定的 4 项）
  → S43-06 HEXACO 覆盖审计（不做无数据数值映射）
```

---

## 2. 跨会话记忆

### 2.1 目标

她应能记住：

- 私聊里发生的事；
- 群聊里发生的事；
- 某条信息的来源（哪个会话、谁说的、什么时候）；
- 谁已经知道这条信息；
- 当前受众是谁，是否适合说。

不是：

```text
A 群数据 B 群永远看不到
```

### 2.2 公开依据

- **Source monitoring**：Johnson, Hashtroudi & Lindsay (1993), *Source monitoring*, Psychological Bulletin.
- **Destination memory**：Gopie & MacLeod (2009), *Destination memory impairment in older people*, Psychology and Aging.
- **Contextual integrity**：Nissenbaum (2004), *Privacy as contextual integrity*, Washington Law Review.
- **Audience design**：Bell (1984), *Language style as audience design*, Language in Society.
- **LongMemEval**：Wu et al. (2024), arXiv:2410.10813，跨会话/时间推理评测。
- **MemGPT**：Packer et al. (2023), arXiv:2310.08560，分层记忆管理。

这些文献支持“来源 + 受众 + 披露”模型，不支持“所有会话无条件共享”。

### 2.3 数据模型

在现有 `semantic_facts` / `episodic_memories` 上增加来源与受众维度，不建第二套记忆库：

```text
memory_items
  id
  content
  source_chat_key       -- 来源会话
  source_person_id      -- 来源人
  source_quote          -- 原话片段
  observed_at_ms        -- 观察时间
  sensitivity           -- public / group / private / secret
  audience_json         -- 允许的受众
  scope                 -- venue / person / global
```

`knowledge_state`（告知史）：

```text
memory_id, person_id, known_at_ms, told_by_me, source_chat_key
```

`disclosures`（披露日志）：

```text
memory_id, told_to_person_id, told_in_chat_key, told_at_ms, mode
```

已有 B4/B5/B6 的 claims/provenance/valid_to 作为写入基础，不重复实现。

### 2.4 检索策略

当前：

```sql
chat_key IN (?, 'global')
```

目标：

```text
当前会话记忆
+ 其他会话的 public / group 记忆（按 source/audience 允许）
- secret 默认不跨受众
```

排序仍用现有融合，不新造打分：

```text
RRF(BM25/FTS5, dense, recency, relation)
```

跨会话候选只增加“可召回”，不直接提高权重；避免泄漏和 dominance。

### 2.5 验收

自动化：

1. A 群 `secret` 事实，B 群不可召回；
2. A 群 `public` 事实，B 群可召回且带来源；
3. 私聊承诺事件在群会话可召回，但不泄漏私聊原文；
4. 现有 70/70 与 LongMemEval 500 retrieval 不低于基线；
5. 来源标注准确率用人工/规则抽检，不以自评代替。

### 2.6 风险

- 隐私泄漏；
- 跨会话噪声淹没当前会话；
- 时间/来源混淆；
- 现有 `chat_key` 索引需要迁移。

默认 `CROSS_SESSION_MEMORY=off`，先 shadow。

---

## 3. 跨会话发送文字/语音

### 3.1 目标

她可以决定：

```text
发给当前会话
发给另一个已存在的会话
发文字
发语音
```

不是“只能发当前 chat_key”。

### 3.2 公开依据

- **Mixed-initiative interaction**：Horvitz (1999), *Principles of mixed-initiative user interfaces*, CHI.
- **Tool-augmented agents**：现有 agent tool-use 范式；不引入未经验证的自主路由算法。
- **安全审计**：OWASP ASVS/日志审计原则，用于目标与结果记录，不用于“硬禁止”。

### 3.3 工具设计

新增能力，不删除现有工具：

```text
send_to_chat(target_chat_key, messages[])
say_to_chat(target_chat_key, text, mood)
```

目标解析：

- 只接受已存在的 `chat_key`；
- 目标来自当前对话中明确出现的群/私聊，或操作者显式指定；
- 发送后必须返回目标 `chat_key` 与 `message_id`；
- 失败时返回明确错误，不允许“嘴上说已发”。

审计：

```text
outbound_audit
  tool, source_chat, target_chat, message_id, text_hash, ts, result
```

不做硬白名单；但必须记录、可回放、可追责。

### 3.4 验收

1. 私聊 `send_to_chat(group:...)` 真的出现在群 `chat_messages`；
2. 语音同理，目标群出现语音消息；
3. 发送失败时不产生“已发送”文案；
4. 现有 `send_message`/`feiyu_say` 行为不变；
5. 目标不存在时明确报错，不静默发到当前会话。

### 3.5 与自由意志的关系

自由意志体现在：

```text
她自己决定说不说、发到哪、用文字还是语音
```

工程责任体现在：

```text
记录目标、校验结果、失败可解释
```

---

## 4. BDI 意图栈

### 4.1 目标

当前 `IntentionItem` 有类型、有过滤函数，但**没有生产者**，所以永远是空栈。

要实现：

- 从对话/承诺中产生 intention；
- 最多 3 条；
- 有 TTL；
- 完成/过期/撤销；
- 参与注意门控与主动行为。

### 4.2 公开依据

- **BDI**：Rao & Georgeff (1995), *BDI Agents: From Theory to Practice*, ICMAS.
- **Commitment/reconsideration**：Bratman (1987), *Intention, Plans, and Practical Reason*.
- **Limited resource**：Miller (1956) / Cowan (2001) 工作记忆容量，支持小栈而非无限。

### 4.3 模型

```text
IntentionItem
  id
  summary
  created_at_ms
  expires_at_ms
  target_user_id
  target_chat_key
  source
  status: open / fulfilled / expired / revoked
  evidence_quote
```

生产者（按可信度排序）：

1. 显式承诺：她说“我这就去/我待会儿/我明天…”；
2. 用户明确请求且她答应；
3. 未完成的工具动作（发送失败、待确认）；
4. 主动计划（不默认生成，需规则/LLM 证据）。

不做：从任意闲聊自动生成“意图”，避免脑补。

### 4.4 验收

1. 显式承诺产生 1 条 intention；
2. 她完成发送后标记 fulfilled；
3. 过期自动移除；
4. 最多 3 条，超出按优先级/TTL 淘汰；
5. 70/70 不退化。

---

## 5. FTS5

### 5.1 目标

给 SQLite 增加 FTS5 词法检索，作为现有 BM25 的**候选/对照**，不是直接替换。

### 5.2 公开依据

- SQLite FTS5 官方文档：https://www.sqlite.org/fts5.html
- FTS5 `unicode61` / `trigram` tokenizer 官方说明；
- 中文没有空格，优先评估 `trigram`，并与现有 2-gram 对照。

### 5.3 实现

```text
memory_fts (content, chat_key, source, tokenize='trigram')
```

- 写入：与 `semantic_facts`/`episodic_memories` 同步；
- 查询：FTS5 top-k 作为 lexical 候选；
- 融合：与现有 BM25 结果做 RRF，不调整手写权重；
- 默认 shadow，`FTS5_ENABLED=off`。

### 5.4 验收

1. 中文同义/长词查询不比现有 BM25 差；
2. LongMemEval 500 retrieval recall@5 ≥ 0.954 基线；
3. 查询延迟 p95 可测，不能拖慢 live；
4. 迁移可回滚，FTS5 表可重建。

不把 FTS5 当“语义检索”；它只解决词法召回。

---

## 6. partial 项收口（选定 4 项）

不一次做 14 项，先选与 Stage 43 强相关的 4 项：

| ID | 现状 | 本阶段目标 |
|---|---|---|
| CAP-MEMORY-EVIDENCE | slot 默认 off，生产仅 1 条 gender | source/audience 字段补齐；slot 数据小流量 |
| CAP-AUTH-WRITE | auth_key 空全放行 | 写操作审计与 token 全覆盖；跨会话发送审计 |
| CAP-ACTION-ELIGIBILITY | additive / refusal 只许可 | 跨会话目标能力纳入 eligibility，不硬禁止 |
| CAP-RESPONSE-ATTRIBUTION | shadow only | 发送后结果归因，接入 intention fulfilled |

其余 partial 保持现状，避免范围爆炸。

### 验收

- 四项各自有单测/集成测试；
- 70/70 与 406 门禁不退化；
- 没有“默认开启”的未验证行为。

---

## 7. HEXACO 映射

### 7.1 事实

当前 7 维是自研维度：

```text
warmth, tsundere, playfulness, possessiveness,
confidence, guile, defiance
```

HEXACO 六轴：

```text
Honesty-Humility, Emotionality, Extraversion,
Agreeableness, Conscientiousness, Openness
```

公开依据：

- Ashton & Lee (2007), *Empirical, theoretical, and practical advantages of the HEXACO model*, PSPR.
- HEXACO-PI-R 构念定义。

### 7.2 不能做的事

不能直接编造：

```text
7D → HEXACO 的相关系数
7D → HEXACO 的权重矩阵
```

没有同批被试的 7D/HEXACO 数据，任何数值映射都是无依据的。

### 7.3 本阶段只做覆盖审计

实现：

```text
HexacoCoverage
  axis: six axes
  covered_by_7d: list
  missing: list
  status: covered / partial / absent
```

明确：

- 7D 没有 Conscientiousness / Openness 的独立轴；
- `guile` 只反向覆盖 Honesty-Humility 的一部分；
- `defiance` 与 Agreeableness 有构念重叠，但不是同一轴；
- 不宣称 CAP-HEXACO 已实现。

### 7.4 未来映射的验收

只有在获得至少一组同批 7D + HEXACO 评分后，才允许：

- 探索性因素分析；
- 计算相关/置信区间；
- 预注册验证；
- 不通过就保持“覆盖审计”状态。

---

## 8. 分阶段实施

### P0：模型与安全边界（本轮）

- 本文档；
- 现有 source/audience/disclosure 文档对齐；
- 不改变 live 行为。

### P1：跨会话记忆 shadow

- 数据字段/迁移；
- 只读 shadow 候选；
- 对照 70/70。

### P2：BDI 生产者

- intention 产生/完成/过期；
- 只影响 shadow/主动行为，不直接改 prompt。

### P3：跨会话发送

- text/voice 目标工具；
- 事后校验；
- 私聊→群实测。

### P4：FTS5

- 迁移/回填；
- shadow 对照 500；
- 不达基线不启用。

### P5：partial 四项

- auth/audit；
- action eligibility；
- attribution 闭环；
- slot 小流量。

### P6：HEXACO 覆盖审计

- 只做构念覆盖；
- 不做数值映射。

---

## 9. 全局验收

```text
功能：六项均有实现或明确的 blocked 状态
数据：每个数字都有来源（论文/官方文档/本机测量）
回归：406+ 门禁，fusion 70/70
安全：secret 不跨受众；发送有审计；失败不伪装成功
可回滚：每个 flag 默认 off/shadow
```

## 10. 参考

- Johnson, M. K., Hashtroudi, S., & Lindsay, D. S. (1993). Source monitoring. *Psychological Bulletin*.
- Gopie, N., & MacLeod, C. M. (2009). Destination memory impairment in older people. *Psychology and Aging*.
- Nissenbaum, H. (2004). Privacy as contextual integrity. *Washington Law Review*.
- Bell, A. (1984). Language style as audience design. *Language in Society*.
- Rao, A. S., & Georgeff, M. P. (1995). BDI Agents: From Theory to Practice. *ICMAS*.
- Bratman, M. E. (1987). *Intention, Plans, and Practical Reason*. Harvard University Press.
- Ashton, M. C., & Lee, K. (2007). Empirical, theoretical, and practical advantages of the HEXACO model. *Personality and Social Psychology Review*.
- Wu, D., et al. (2024). LongMemEval. arXiv:2410.10813.
- Packer, C., et al. (2023). MemGPT. arXiv:2310.08560.
- Horvitz, E. (1999). Principles of mixed-initiative user interfaces. *CHI*.
- SQLite FTS5: https://www.sqlite.org/fts5.html


---

## 11. P0 实施记录（2026-11-02）

已实现且未接 live：

| 模块 | 内容 | 测试 |
|---|---|---|
| `mind/session_memory_policy.py` | source/audience 跨会话召回策略；secret/private 不跨会话 | `tests/unit/test_session_memory_policy.py` |
| `mind/intention_stack.py` | BDI 意图栈：去重、上限 3、TTL 过期 | `tests/unit/test_intention_stack.py` |
| `mind/hexaco_coverage.py` | HEXACO 六轴覆盖审计；明确 Conscientiousness 缺失；不编数值映射 | `tests/unit/test_hexaco_coverage.py` |

参数账本新增：

```text
mind/intention_stack.py::MAX_INTENTIONS = 3
class=convention, status=active
依据：Cowan (2001) 工作记忆容量 4±1，取 3 为保守上限
```

门禁：

```text
414 passed / 93%
fusion 70/70
constants=61 compliant=61
```

未做：

- 跨会话检索 SQL/迁移；
- 跨会话发送工具；
- FTS5；
- partial 四项；
- HEXACO 数值映射（无数据，不做）。


## 12. P1/P3 进展（2026-11-02）

### 跨会话记忆 shadow

新增：

```text
scripts/shadow_cross_session_memory.py
```

生产只读扫描：

```text
group:813506156 候选 = 37（global public/group）
私聊来源候选 = 0（默认不跨会话）
```

结论：

- 原始私聊事实不会因为 sensitivity=group 就泄漏到群；
- 私聊承诺要跨会话，必须走“显式事件/披露”而不是直接引用私聊原文；
- 尚未改 `get_semantic_facts`，live 检索仍按 `chat_key IN (?, 'global')`。

### 跨会话发送

已实现并注册：

```text
send_to_chat(target_chat_key, messages[])
feiyu_say(..., target_chat_key)
```

- 不删现有当前会话工具；
- 目标为空/发送失败会明确报错；
- 不设硬白名单；发送后返回 target 与 message_id；
- 单测验证私聊调用目标群；未向真实群发测试消息。


## 13. P1 第二半（2026-11-02）

新增：

```text
SqliteMemoryRepository.get_cross_session_facts()
tests/integration/test_cross_session_memory.py
```

行为：

- 默认不调用；不是 live 读路径；
- 只读 `public/group`；
- 群来源的 group 事实可跨群；
- 私聊来源默认不跨；
- secret 永不跨；
- 未改变 `get_semantic_facts` / agent runner。

这一步仍不是“跨会话承诺”：原始私聊事实不会直接进群；承诺需要下一步的显式事件/披露模型。


## 14. P2 BDI 生产者（2026-11-02）

新增：

```text
mind/commitment.py
tests/unit/test_commitment.py
satiate_snapshot() 接入
```

规则：

- 只从她**实际发出的文本**中提取明确承诺；
- 命中：我这就去/我马上去/我待会儿/我稍后/我去群里/我明天等；
- 否定句（我不去/不会去）不产生；
- 普通闲聊不产生；
- 意图上限仍为 3；
- `expires_at_ms=0`：TTL 尚未校准，不拍数字；
- 不自动解析目标群；但如果文本显式出现 `group:<id>` / `private:<id>`，保留为 `target_chat_key`；
- 目标不明时保持空，不猜。

验证：

```text
419 passed / 93%
fusion 70/70
```

注意：

- 这是 live 的 working-state 变更；
- 还没有做“承诺 → 跨会话事件 → 目标群发送”的完整闭环。


## 15. P4 FTS5 基础（2026-11-02）

新增：

```text
src/echomind/adapters/storage/memory_fts.py
tests/integration/test_memory_fts.py
```

实现：

```text
SQLite FTS5 + trigram tokenizer
rowid = semantic_facts.id
content + chat_key UNINDEXED
```

- 中文 3 字以上可查；
- `chat_key` 过滤可包含 global；
- 仅独立索引，未接 `get_semantic_facts`；
- 未替换现有 BM25/2-gram；
- 未做 500 检索对照，因此不宣称提升。

验收下一步：

- 回填 233 条 facts；
- 与现有 BM25 在 LongMemEval 500 上对照；
- recall@5 不低于 0.954 才允许 shadow 之外的读取。


### P4 FTS5 500 对照（2026-11-02）

| retriever | recall@5 | MRR |
|---|---:|---:|
| 现有 BM25/hybrid baseline | **0.954** | **0.892** |
| FTS5 trigram | 0.942 | 0.876 |
| FTS5 + BM25 RRF(k=60) | 0.944 | 0.878 |

结论：

- FTS5 中文 3-gram OR 可查；
- 全量 500 低于现有基线约 1.2pp recall / 1.6pp MRR；
- 等权 RRF 只回到 0.944/0.878，仍低于 0.954/0.892；
- 不接 live；
- 保留独立索引与测试，作为后续“FTS5 + 现有 BM25 RRF”候选，不直接替换；
- 结果文件：`eval/baselines/longmemeval-500-fts5-2026-11-02.json`。


### P3 工具可见性修复（2026-11-02）

发现 `send_to_chat` 虽注册，但不在 reagent 选择集，模型看不到。已加入：

```text
日常轻装剂: send_message, send_to_chat, send_sticker, feiyu_say, recall_memory
```

并在 prompt 中明确：

- send_message/feiyu_say 只发当前会话；
- 去别的群/私聊必须用 send_to_chat(target_chat_key) 或 feiyu_say(target_chat_key)；
- 目标不明确先问，不许只在当前会话答应“我这就去”；
- 失败要如实说。


### P2 目标字段（2026-11-02）

`IntentionItem` 增加可选 `target_chat_key`：

- 显式 chat key 保留；
- “去群里说”这类没有具体目标的承诺保持空；
- global working state 让 summary 跨会话可见；
- 不自动发消息，仍由模型/发送工具决定。


## 16. 状态校准（2026-11-02）

能力台账不再把已实现基础标成 `absent`：

```text
CAP-CROSS-SESSION-MEMORY: absent → partial
CAP-INTENTION-STACK:     absent → partial
CAP-FTS5:                absent → partial
```

仍未完成：

- 跨会话 live 读路径与承诺事件；
- BDI 自动目标解析/TTL/执行；
- FTS5 不达基线，不接 live；
- HEXACO 数值映射无数据，不做。


## 17. partial：CAP-AUTH-WRITE 收口（2026-11-02）

核对发现文档 gap 已过期：代码已具备：

- 写操作（POST/PUT/PATCH/DELETE）强制 token；
- 空 token 时仅 loopback 可读/写；
- `/api/session/token` 只信任 loopback Host/Origin；
- 写审计记录 401/成功状态。

测试：

```text
tests/unit/test_web_write_auth.py
tests/unit/test_token_loopback.py
```

因此把 `CAP-AUTH-WRITE` 从 partial 校准为 implemented；不把“loopback 可读”误写成“全放行”。

注意：这不是 Stage 43 新增代码，是台账与事实对齐。


## 18. 工具可见性回归（2026-11-02）

新增：

```text
tests/unit/test_cross_session_tool_visibility.py
```

锁定：

- `send_to_chat` 在“日常轻装剂”中；
- prompt 明确 `target_chat_key` 与跨会话发送；
- 避免“注册了但模型看不到”再次发生。

同时发现上一版 prompt 修改实际未生效（字符串未匹配），已补上并验证。

门禁：424 passed / 93%。


## 19. BDI 意图进入 prompt（2026-11-02）

发现：意图虽然写入 working state，但 `frame_renderer` 没有渲染，模型看不到。

新增：

```text
frame_renderer._intention_lines()
tests/unit/test_intention_rendering.py
```

现在 prompt 会包含：

```text
【📌 短期挂念（未完成承诺/意图）】
- 我这就去群里说 → group:...
```

- 最多 3 条；
- 没有目标就只显示 summary；
- 不自动执行发送；
- 有目标时显示 target_chat_key。

门禁：425 passed / 93%。


### P4 FTS5 回填与延迟（2026-11-02）

生产索引：

```text
indexed = 249 semantic facts
build = 3.5s
query = 2–4ms
```

修复：

- 之前 FTS `MATCH` 用整句 phrase，导致“群主是谁”0 命中；
- 改为 CJK 3-gram / 英文词项 OR；
- 2 字查询（如“直播”“B站”）仍无法命中，这是 trigram 的硬限制，不掩盖。

仍不接 live；FTS5 500 对照低于基线。


## 20. 跨会话发送的出站保护（2026-11-02）

发现 `send_to_chat` 原先绕过 `_prepare_outbound_args` 的清洗/计数：

- 可能命中管理员禁用词仍发出；
- 同一轮可能重复跨会话发送；
- `sent_count` 不统计。

修复：

```text
runtime/outbound.py: prepare_cross_chat()
agent_runner 统一调用
```

现在跨会话发送同样经过：

- 禁用词过滤；
- 同一轮重复发送拦截；
- sent_texts 计数。

测试：

```text
tests/unit/test_cross_chat_outbound_guard.py
```

门禁：426 passed / 93%。


## 21. 端到端工具调用回归（2026-11-02）

新增：

```text
tests/unit/test_stage4_tools_and_runtime.py::
  test_agent_calls_send_to_chat_with_explicit_target
```

使用脚本化 LLM，在私聊触发：

```text
send_to_chat(target_chat_key="group:10002002", messages=["去群里说"])
```

fake OneBot 记录到：

```text
send_group_msg group_id=10002002
```

这验证了：

- 工具在 registry 可执行；
- agent runner 会处理目标；
- 出站保护不拦截合法跨会话发送；
- 不依赖真实 QQ。

仍未做真实 QQ 群发送（避免测试打扰）。


## 22. HEXACO 分类映射（2026-11-02）

新增：

```text
mind/hexaco_coverage.py::dimension_mapping()
tests/unit/test_hexaco_coverage.py
```

返回 7D → HEXACO 轴的**分类假设**：

```text
warmth -> Agreeableness, Extraversion
tsundere -> Emotionality, Agreeableness
playfulness -> Extraversion, Openness
possessiveness -> Emotionality
confidence -> Extraversion
guile -> Honesty-Humility
defiance -> Agreeableness, Honesty-Humility
```

明确：

- 这是构念对齐，不是相关系数/权重；
- Conscientiousness 仍缺失；
- 没有同批 7D/HEXACO 数据，不宣称 psychometric validity；
- `CAP-HEXACO` 仍保持 contradicted，不因分类 API 改写为 implemented。

门禁：428 passed / 93%。


## 23. BDI 来源会话（2026-11-02）

`IntentionItem` 新增：

```text
source_chat_key: str = ""
```

- 由 `satiate_snapshot(..., source_chat_key=o.chat_key)` 写入；
- 私聊承诺会记录来源私聊；
- 目标仍由 `target_chat_key` 表示；
- 不自动发送，来源用于跨会话审计与后续事件。

测试：

```text
tests/unit/test_commitment.py
```

门禁：428 passed / 93%。


## 24. 真实 QQ 跨会话发送验收（2026-11-02）

真实私聊 trigger：

```text
那你在群里发心里只有我一个
```

turn 结果：

```text
status = done
rounds = 2
sent_count = 1
tool = send_to_chat
target_chat_key = group:813506156
message_ids = ["1143989337"]
```

目标群实际出现：

```text
说一句，我心里只有L一个，别人都是闹着玩的，别误会啊
```

私聊回复：

```text
发了，去群里看吧，我可没敷衍你
```

证据：

- `turn_traces.steps_json` 第 2 步是 `send_to_chat`，不是 `feiyu_say`；
- `chat_messages` 的 group 自消息出现对应文本；
- 该轮 `user_prompt` 含：
  ```text
  【📌 短期挂念（未完成承诺/意图）】
  - 群号发我，我这就去发，别再催了
  ```
- system prompt 含 `send_to_chat` 与 `target_chat_key`。

结论：

```text
BDI 承诺 → prompt 可见 → 模型选择 send_to_chat → 目标群真实收到
```

这条链路已经真实跑通，不再是 fake OneBot 或口头答应。


## 25. 语音跨会话端到端（2026-11-02）

新增：

```text
test_agent_calls_feiyu_say_with_target_group
```

脚本化 LLM 在私聊调用：

```text
feiyu_say(text="去群里说", target_chat_key="group:10002002")
```

fake OneBot 记录到：

```text
send_group_msg group_id=10002002
```

验证：

- `feiyu_say` 的 target 不只是参数存在；
- agent runner 会把它传到目标群；
- 不会误发当前私聊；
- 未使用真实 QQ 语音/群。

门禁：429 passed / 93%。


## 26. 跨会话主动回忆（2026-11-02）

`recall_memory` 新增可选参数：

```text
include_cross_session: bool = false
```

行为：

- 默认 false，完全保持原行为；
- true 时调用 `get_cross_session_facts()`；
- 仍受 source/audience 策略：private 来源/secret 不跨；
- 模型可主动选择跨会话回忆，不是后台偷看。

测试：

```text
tests/unit/test_recall_cross_session.py
```

门禁：430 passed / 93%。


## 27. partial：CAP-ACTION-ELIGIBILITY 收口（2026-11-02）

claim 是“active trait 可追加工具授权并授予拒绝许可”，代码已支持：

- additive 默认追加；
- whitelist 可选；
- taboo 授予 refusal 许可；
- 测试 `tests/unit/test_trait_tool_grants.py`。

“refusal 只许可不强制”不是缺陷，是自由意志设计；whitelist 未默认启用也不否定 claim。故校准为 implemented。


## 28. 承诺事件持久化（2026-11-02）

新增：

```text
intention_events 表
working_intentions.sync_intention_events()
save_snapshot() 同步写入
tests/integration/test_intention_events.py
```

字段：

```text
source_chat_key, target_chat_key, summary,
status=open, created_at_ms, updated_at_ms
唯一键(source_chat_key, summary, target_chat_key)
```

行为：

- 每次 working state 保存时，当前 intentions 写入事件表；
- 重复保存不重复插入；
- 仍不自动发送；只持久化“未完成承诺”；
- 旧数据表不存在时，服务启动 schema 会创建。

门禁：431 passed / 93%。


## 29. 承诺事件状态闭环（2026-11-02）

`sync_intention_events()` 现在：

- 当前快照中的 intention → `open`；
- 快照中已不存在的 open 事件 → `closed`；
- 保留 source/target/summary 审计；
- 不删除历史；
- 不自动发送。

测试覆盖：

```text
保存承诺 → open
保存无承诺快照 → closed
```

门禁：431 passed / 93%。


## 30. BDI 栈收口（2026-11-02）

claim：短期挂念栈（BDI 意图，≤3 槽）。

现有证据：

- `commitment.py` 从明确承诺句产生 intention；
- `intention_stack.py` 去重/上限 3/TTL 过滤；
- `IntentionItem` 有 summary/source/target/created/expires；
- `frame_renderer` 把未完成承诺写入 prompt；
- `intention_events` 持久化并 closed；
- 真实私聊→群发送成功。

因此把 `CAP-INTENTION-STACK` 校准为 implemented。

仍未做：

- TTL 数值校准；
- 模糊“群里”自动解析目标；
- 发送 message_id 回填 event。

这些是增强项，不否定“栈已实现”。
