# 记忆的“地点”维度：调研与落地方案

> **2026-10-31 方向修正**：本文的 P0「按地点隔离」已被 [`MEMORY_SOURCE_AND_DISCLOSURE.md`](MEMORY_SOURCE_AND_DISCLOSURE.md) 取代。
> 地点仍是来源维度（where），但目标不是隔离，而是“知道从哪来 + 决定说不说”。

> 触发问题：现有记忆有时间（when）、事件（what）、人物（who），但没有地点（where）。
> 同时，跨会话泄漏的根因也是“缺少一个作用域键”。地点正是这个键的天然组成部分。

---

## 一、结论先行

1. **地点不是再加一个字段，而是记忆的第四条索引轴。** 认知科学里情节记忆的定义就是
   “what + where + when”（Clayton & Dickinson 1998）。缺 where，回忆就只能靠“谁/何时/说了什么”，
   无法回答“上次在群里/她家/学校发生了什么”。
2. **主流 agent memory 系统没有把 place 做成一等公民。** MemGPT、Mem0、Zep、A-MEM、HippoRAG
   都把 location 当普通实体或干脆没有；真正把 place 当索引的是两类：
   - **Generative Agents**（Park et al. 2023）：小镇地图 + 每个 agent 的 `place`，记忆流按地点检索；
   - **Neo4j Agent Memory**：POLE+O 实体模型（Person / Organization / **Location** / Event + Object），
     带地理空间查询与地理编码。
3. **对 EchoMind 最合适的不是图数据库迁移，也不是 3D 场景图，而是“符号化地点层”**：
   - venue（群聊/私聊/空间）—— 由现有 `chat_key` 升级而来；
   - physical（城市/学校/公司/家）—— 从对话中抽取并归一化；
   - virtual（游戏/剧/她自己的生活场景）—— 服务于人设连续性。
4. **地点层顺带解决跨会话泄漏**：检索与运行时状态都以 `(venue, participants, place_ids)` 为作用域，
   `chat_key="global"` 只能用于显式的全局地点。这是一次改动、两个收益。

---

## 二、现状诊断（代码与数据）

| 表 | 现有维度 | 地点 |
|---|---|---|
| `episodic_memories` | `ts`（when）、`participants_json`（who）、`summary/key_detail`（what） | 只有 `chat_key`（venue），无 place |
| `semantic_facts` | `chat_key`、`subject`、`fact_text` | 只有 `chat_key`，且存在 `chat_key="global"` 的冲浪事实 |
| `procedural_rules` | `trigger_keyword`、`trigger_user_id` | 无地点 |
| `chat_messages` | `chat_key`、`ts`、`sender_id` | 无地点 |

泄漏侧的证据（已核实）：

- `bot_belief._BELIEFS` 是**模块级 dict**，所有会话共享；
- `facade._dialogue = DialogueContext()`，`note(sender_name, text)` **不带 chat_key**，跨群共享；
- `scheduler` 把冲浪见闻写成 `chat_key="global"` 的语义事实；
- `agent_runner._active_bans` 是 runner 级状态，跨会话复用。

结论：**记忆表和运行时状态都缺一个统一的作用域键**。地点是其中缺失最久的一维。

---

## 三、理论依据：情节记忆 = what + where + when

- **Clayton & Dickinson (1998)**，Nature 395:272–274，DOI `10.1038/26216`：
  灌丛鸦记得“什么食物、藏在哪里、什么时候藏的”，这是非人类情节记忆的行为标准。
  摘要原文即 “recall what a particular event was, and where and when it occurred”。
- **Tulving (1972)**：情节记忆 vs 语义记忆的区分；情节记忆带自我与时空坐标。
- **Burgess, Maguire & O'Keefe (2002)**，Neuron 35(4):625–641，DOI `10.1016/S0896-6273(02)00830-8`：
  海马同时支持空间与情节记忆。
- **Epstein et al. (2017)**，Nat Neurosci 20:1154–1164，DOI `10.1038/nn.4653`：
  认知地图不止导航，还承载场景、事件与社会关系。
- **Zacks et al. (2007)**，Psychol Bull 133(2):273–293，DOI `10.1037/0033-2909.133.2.273`：
  事件分割——地点与时间的边界共同定义“一个事件”。
- **O'Keefe & Dostrovsky (1971)**，Brain Res 34:171–175，DOI `10.1016/0006-8993(71)90358-1`：位置细胞。

**对工程的直接含义**：place 是事件边界的一部分，也是检索线索；没有它，“事件”无法被地点切分，
记忆只能退化成按时间排列的流水账。

---

## 四、系统调研

### 4.1 通用 agent 记忆

| 系统 | 论文 | 仓库 | 地点处理 | 可借鉴 | 不建议 |
|---|---|---|---|---|---|
| **MemGPT / Letta** | arXiv `2310.08560` | [letta-ai/letta](https://github.com/letta-ai/letta) | 无地点；OS 式分层 | 快/慢记忆分层、可编辑记忆块 | 换掉现有存储 |
| **Mem0** | arXiv `2504.19413` | [mem0ai/mem0](https://github.com/mem0ai/mem0) | location 最多是实体 | 抽取→整合→检索流水线 | 整套依赖 |
| **Zep / Graphiti** | arXiv `2501.13956` | [getzep/graphiti](https://github.com/getzep/graphiti) | 地点是实体节点；强在时间边 | **双时态边**（valid_at/invalid_at） | 图数据库迁移 |
| **A-MEM** | arXiv `2502.12110` | [WujiangXu/A-mem](https://github.com/WujiangXu/A-mem) | 地点可作为 tag/属性 | Zettelkasten 式属性+链接+记忆演化 | 全量照搬 |
| **HippoRAG** | arXiv `2405.14831` | [OSU-NLP-Group/HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG) | 地点是 KG 节点 | 图上的 Personalized PageRank 联想检索 | 图数据库 |
| **Cognee** | — | [topoteretes/cognee](https://github.com/topoteretes/cognee) | 通用实体抽取 | 轻量图+向量混合 | 替换 SQLite |
| **GraphRAG** | arXiv `2404.16130` | [microsoft/graphrag](https://github.com/microsoft/graphrag) | 地点是实体 | 社区摘要、全局查询 | 成本高，当前数据量不需要 |
| **MemOS** | arXiv `2507.03724` | MemTensor/MemOS | 无专门地点 | 记忆作为可调度资源 | 过度设计 |
| **MemoryOS** | arXiv `2506.06326` | BAI-LAB/MemoryOS | 无专门地点 | 分层内存管理 | 同上 |

### 4.2 真正把“地点”当索引的

| 系统 | 出处 | 地点模型 | 可借鉴 |
|---|---|---|---|
| **Generative Agents** | arXiv `2304.03442` | 小镇 `Maze` + 每个 agent 的 `place`；观察记录含地点，检索按 recency/importance/relevance，地图约束行为 | 借“地点是观察的一部分 + 地图约束行为”；检索打分里加地点项（原论文未把地点当硬过滤） |
| **Neo4j Agent Memory** | [neo4j-labs/agent-memory](https://github.com/neo4j-labs/agent-memory) | **POLE+O**：Person / Organization / **Location** / Event + Object；支持地理空间查询、地理编码、Wikipedia 增强 | 实体模式、抽取流水线（spaCy/GLiNER2/GLiREL/LLM）、空间索引 |
| **BSC-Nav** | arXiv `2508.17198` | landmarks / route / survey 三层空间知识，allocentric 认知地图 | 三层地点表示；语义目标检索空间记忆（具身场景才需要） |
| **地点纽付回忆机器人** | DOI `10.11517/pjsai.JSAI2026.0_4F5OS29c02` | GPS + LLM，走到某地触发该地点的回忆；重访时按对话历史个性化 | **重访触发**与“地点—回忆”绑定 |
| **LongMemEval** | arXiv `2410.10813` | 不建模地点，但评测跨会话/时间推理/拒答 | 评测协议：information extraction、multi-session、temporal、abstention |

**关键空白**：以上系统没有一个把 place 作为**独立存储轴 + 检索过滤 + 作用域键**三者合一。
EchoMind 可以补这个空位，而且不需要引入新数据库。

---

## 五、聊天场景里的“地点”到底是什么

不要一上来做地理坐标。分三层，按优先级落地：

1. **Venue（会话地点）**：`group:813506156`、`private:3064615013`、`qzone:...`。
   现有 `chat_key` 已经是它，只是没有被建模成 place。**P0 就能做**。
2. **Physical（物理地点）**：北京、学校、公司、家、某家店。
   从消息里抽取，归一化 + 层级（城市→省→国；“学校”解析为用户档案里的学校）。
3. **Virtual / narrative（虚拟地点）**：游戏地图、剧集场景、她自己的生活场景（房间、通勤）。
   服务于人设一致性，可与 `her-life` 技能共用。

另外两个必须处理的指代：

- **“这里/这儿”**：解析为当前 venue（或用户当前 physical place，若已知）；
- **“那里/上次那个地方”**：回指最近提到的 place，带置信度，不猜就存疑。

---

## 六、推荐 schema（最小改动）

```sql
CREATE TABLE places (
  place_id      TEXT PRIMARY KEY,          -- venue:group:813506156 / phys:beijing / virt:...
  kind          TEXT NOT NULL CHECK (kind IN ('venue','physical','virtual','global')),
  name          TEXT NOT NULL,
  parent_id     TEXT REFERENCES places(place_id),
  aliases_json  TEXT NOT NULL DEFAULT '[]',
  confidence    REAL NOT NULL DEFAULT 1.0,
  source        TEXT NOT NULL,             -- backfill / rule / ner / llm / user
  created_ms    INTEGER NOT NULL,
  updated_ms    INTEGER NOT NULL
);

-- 一条记忆可以关联多个地点（发生在哪、提到了哪、关于哪）
CREATE TABLE memory_places (
  memory_kind   TEXT NOT NULL CHECK (memory_kind IN ('episodic','semantic','procedural')),
  memory_id     INTEGER NOT NULL,
  place_id      TEXT NOT NULL REFERENCES places(place_id),
  role          TEXT NOT NULL CHECK (role IN ('happened_at','mentioned','about')),
  confidence    REAL NOT NULL DEFAULT 0.0,
  evidence      TEXT NOT NULL DEFAULT '',  -- 原文片段，禁止无证据标注
  PRIMARY KEY (memory_kind, memory_id, place_id, role)
);

ALTER TABLE episodic_memories ADD COLUMN place_id TEXT REFERENCES places(place_id);
ALTER TABLE semantic_facts   ADD COLUMN place_id TEXT REFERENCES places(place_id);
```

**回填**：每个 `chat_key` 生成一个 `venue:` place；所有历史 episodic 行的 `place_id` 指向它
（默认“事件发生在该会话”），`memory_places` 里 role=`happened_at`。
物理地点先留空，等抽取上线后再补 role=`mentioned`。

设计原则（对齐项目的“无证据不标注”）：

- `evidence` 必填，存原文片段；
- 抽取置信度低于阈值时写入 `place_mentions` 待审队列，而不是硬塞；
- 不做隐式推断（“他说加班”→“公司”需要证据或用户档案）。

---

## 七、抽取与归一化

三级流水线，逐级提高召回、降低误报：

1. **规则层（P1，高精度）**：中文地点模式（“在X”“去X”“从X来”）、城市/省份词典、用户档案
   （home city / school / workplace）。命中即带 evidence。
2. **NER 层**：中文地点 NER；多语言可用 GLiNER2（Neo4j Agent Memory 用的就是 spaCy/GLiNER2/GLiREL 组合）。
3. **LLM 层**：在记忆整合 prompt 里增加结构化字段
   `{place: {name, kind, confidence, evidence_span}}`，只允许从原文抽取，不允许自由发挥。

归一化：

- alias 表（“学校”/“我们学校”/具体校名 → 同一 place_id）；
- 层级（城市→省→国家），支持“同城”这类粗粒度检索；
- 去重（同名不同地要区分，用 parent + 上下文）。

---

## 八、检索与跨会话泄漏修复

### 8.1 检索作用域

每次记忆检索带一个 `scope`：

```python
@dataclass(frozen=True)
class MemoryScope:
    venue_place_id: str          # 当前会话地点
    participant_ids: frozenset[str]
    mentioned_place_ids: tuple[str, ...]  # 本条消息提到的地点
    allow_global: bool = False
```

SQL/向量检索统一加过滤：

- episodic：`place_id IN (venue, *mentioned)` 或 `memory_places` join；
- semantic：`place_id = venue` 或 `place_id = global`（仅 allow_global）；
- 排序：`score = w_sim·相似度 + w_time·时间衰减 + w_place·地点匹配 + w_imp·重要性`。
  地点匹配可以是硬过滤（默认）或软加权（地点不确定时）。

### 8.2 泄漏修复

| 泄漏点 | 现状 | 修复 |
|---|---|---|
| `_BELIEFS` | 模块级 dict，全群共享 | 改为 `dict[(chat_key, user_id), float]`，或每作用域一个实例 |
| `facade._dialogue` | `note(sender, text)` 无 chat_key | 改为按 `venue_place_id` 分桶的 DialogueContext |
| `chat_key="global"` 冲浪事实 | 写入语义事实，任何群可读 | 迁到 `place:global`，检索时默认不跨群，除非 `allow_global` |
| `_active_bans` | runner 级 | 键为 `(venue_place_id, ...)` 或每会话一个 runner |

**验收测试**（必须自动化）：

1. 在 A 群写入事实，B 群检索不到；
2. `place:global` 事实只在 `allow_global=True` 时出现；
3. “这里”解析为当前 venue；
4. 在 A 群提到“学校”，只召回该用户学校相关记忆，不召回 B 群同名地点。

---

## 九、评测

1. **地点回忆集**（100 题，手工或半自动构造）：
   - “上次在群里说周末去哪” → 召回 venue + 事件；
   - “她学校在哪” → 召回 physical place；
   - “那次在咖啡馆” → 地点过滤 + 时间排序。
2. **泄漏探针**：跨 venue 查询，泄漏率必须为 0。
3. **LongMemEval 子集**（`2410.10813`）：temporal reasoning、multi-session、abstention，
   用来对标外部系统；不追求刷榜，追求“不比没有地点层更差”。
4. 指标：recall@k、answer accuracy、leakage rate、abstention accuracy。

---

## 十、分阶段计划

| 阶段 | 内容 | 成本 | 风险 |
|---|---|---|---|
| **P0** | `places` + `memory_places` 表；venue 回填；检索 scope 过滤；泄漏修复与测试 | 1–2 天 | 低；只动读路径与运行时键 |
| **P1** | 物理地点抽取（规则+LLM）、alias/层级、`place_mentions` 待审队列 | 3–5 天 | 中文 NER 精度；靠 evidence+confidence 控制 |
| **P2** | 地点加权检索、“这里/那里”指代、重访触发（可选） | 3–5 天 | 指代歧义；先只做高置信场景 |
| **P3** | 评测集 + LongMemEval 子集对照 | 2–3 天 | 需要人工标注 |

**不建议现在做的**：

- 引入 Neo4j/Graphiti 替换 SQLite（数据量小，运维成本不值）；
- 3D 场景图/视觉地点（除非做具身）；
- 全量 LLM 抽取（先用规则+置信度把关，避免“拍脑门”标注）。

---

## 十一、参考文献

**理论**

- Clayton, N. S., & Dickinson, A. (1998). Episodic-like memory during cache recovery by scrub jays. *Nature*, 395(6699), 272–274. https://doi.org/10.1038/26216
- Tulving, E. (1972). Episodic and semantic memory. In *Organization of Memory*. Academic Press.
- Burgess, N., Maguire, E. A., & O'Keefe, J. (2002). The human hippocampus and spatial and episodic memory. *Neuron*, 35(4), 625–641. https://doi.org/10.1016/S0896-6273(02)00830-8
- Epstein, R. A., Patai, E. Z., Julian, J. B., & Spiers, H. J. (2017). The cognitive map in humans: spatial navigation and beyond. *Nature Neuroscience*, 20, 1154–1164. https://doi.org/10.1038/nn.4653
- Zacks, J. M., Speer, N. K., Swallow, K. M., Braver, T. S., & Reynolds, J. R. (2007). Event perception: a mind-brain perspective. *Psychological Bulletin*, 133(2), 273–293. https://doi.org/10.1037/0033-2909.133.2.273
- O'Keefe, J., & Dostrovsky, J. (1971). The hippocampus as a spatial map. *Brain Research*, 34(1), 171–175. https://doi.org/10.1016/0006-8993(71)90358-1

**系统与论文**

- Park, J. S., et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior. arXiv:2304.03442. https://arxiv.org/abs/2304.03442
- Packer, C., et al. (2023). MemGPT: Towards LLMs as Operating Systems. arXiv:2310.08560. https://arxiv.org/abs/2310.08560
- Chhikara, P., et al. (2025). Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory. arXiv:2504.19413. https://arxiv.org/abs/2504.19413
- Rasmussen, P., et al. (2025). Zep: A Temporal Knowledge Graph Architecture for Agent Memory. arXiv:2501.13956. https://arxiv.org/abs/2501.13956
- Xu, W., et al. (2025). A-MEM: Agentic Memory for LLM Agents. arXiv:2502.12110. https://arxiv.org/abs/2502.12110
- Gutiérrez, B. J., et al. (2024). HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models. arXiv:2405.14831. https://arxiv.org/abs/2405.14831
- Wu, D., et al. (2024). LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. arXiv:2410.10813. https://arxiv.org/abs/2410.10813
- Ruan, S., et al. (2025). From reactive to cognitive: brain-inspired spatial intelligence for embodied agents. arXiv:2508.17198. https://arxiv.org/abs/2508.17198
- Huang, W.-C., et al. (2026). A Survey of Agent Memory in the Second Half. arXiv:2602.06052. https://arxiv.org/abs/2602.06052
- Edge, D., et al. (2024). From Local to Global: A Graph RAG Approach to Query-Focused Summarization. arXiv:2404.16130. https://arxiv.org/abs/2404.16130
- MemOS. arXiv:2507.03724. https://arxiv.org/abs/2507.03724
- MemoryOS. arXiv:2506.06326. https://arxiv.org/abs/2506.06326
- 植田歴ほか (2026). 場所に紐付く思い出想起を支援する対話型パートナーロボットの設計と実装. JSAI2026. https://doi.org/10.11517/pjsai.JSAI2026.0_4F5OS29c02

**仓库**

- Letta (MemGPT): https://github.com/letta-ai/letta
- Mem0: https://github.com/mem0ai/mem0
- Graphiti (Zep): https://github.com/getzep/graphiti
- A-MEM: https://github.com/WujiangXu/A-mem
- HippoRAG: https://github.com/OSU-NLP-Group/HippoRAG
- LongMemEval: https://github.com/xiaowu0162/LongMemEval
- Generative Agents: https://github.com/joonspk-research/generative_agents
- Neo4j Agent Memory: https://github.com/neo4j-labs/agent-memory
- Cognee: https://github.com/topoteretes/cognee
- GraphRAG: https://github.com/microsoft/graphrag
- MemOS: https://github.com/MemTensor/MemOS
- MemoryOS: https://github.com/BAI-LAB/MemoryOS

---

*调研日期：2026-10-31。所有链接在撰写时可达；论文结论以摘要为准，未逐篇复现实验。*
