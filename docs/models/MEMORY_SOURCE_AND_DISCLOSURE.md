# 记忆的来源感与披露分寸（修正版）

> 修正：`MEMORY_PLACE_RESEARCH.md` 的 P0 把“地点”做成了隔离边界，方向错了。
> 她要的不是“每个群一个抽屉”，而是：**知道自己知道什么、从哪知道的、谁已经知道，
> 再决定在哪说、对谁说、说不说。** 这是来源监控 + 受众设计 + 情境完整性，不是访问控制。

---

## 一、她要的四种能力

| 能力 | 认知科学对应 | 当前系统 |
|---|---|---|
| **来源感**：这条信息是从哪学来的（哪个群、谁说的、什么时候） | source monitoring | 无：事实只有 `chat_key`，没有说话人/原话 |
| **告知史**：这条信息我已经告诉过谁、谁又可能告诉了谁 | destination memory | 无：没有“谁知道什么”的状态 |
| **受众感**：现在在场的是谁、他们和来源/当事人什么关系 | audience design | 无：检索不知道听众是谁 |
| **分寸**：说、暗示、闭嘴、私下问、转移话题——由人格与关系决定 | contextual integrity + 社会决策 | 无：要么全说，要么全隔离 |

**关键区别**：隔离是“B 群看不到 A 群的数据”；分寸是“B 群可以知道 A 群的趣事，
但她得知道这是从 A 来的、当事人是谁、说了会不会有事”。前者是数据库权限，后者是人格。

---

## 二、理论依据

### 2.1 来源监控（source monitoring）

Johnson, Hashtroudi & Lindsay (1993) 的 source monitoring framework：
人记住一个信息时，会同时编码**来源特征**（谁说的、在什么情境、什么感官细节），
回忆时用这些特征判断“我是亲眼所见，还是听人说的，还是自己想的”。
来源混淆（source confusion）是记忆错误的常见来源，也是谣言的起点。

→ 工程含义：每条记忆必须带 `source`（人、地点、时间、原话片段），
  并且**允许她不确定**（“好像是听谁说过”），而不是假装知道。

### 2.2 告知史（destination memory）

Gopie & MacLeod (2009) 发现人对“我告诉过谁”记得比对“谁告诉过我”差得多
（destination memory 比 source memory 更弱）。这解释了为什么人会重复讲同一个故事。

→ 工程含义：需要显式的 `knowledge_state`（谁已经知道、是她说的还是别人说的），
  否则她会反复对同一个人讲同一件事，或者把“已经说过”的信息当秘密。

### 2.3 情境完整性（contextual integrity）

Nissenbaum (2004)：隐私不是“保密/公开”的二元，而是**信息流是否符合特定情境的规范**。
同一个信息，在群聊、私聊、说说里，合适的传播方式不同。

→ 工程含义：披露决策要看 **信息类型 × 发送者 × 接收者 × 传输原则**，
  不是简单的 `allow / deny`。这也是为什么“按群隔离”是错的：它把情境差异压成了一个开关。

### 2.4 受众设计（audience design）

Bell (1984) 的 audience design：说话人会根据听众调整措辞、详略、指代。
多人场合里，“对谁说”本身是一种社会行为。

→ 工程含义：同一个记忆，在 A 群、B 群、私聊、说说里要有不同的**说法**，
  不只是“说不说”，还包括“怎么提、提多少、要不要点名来源”。

---

## 三、系统调研

### 3.1 直接相关的新工作

| 工作 | 出处 | 核心贡献 | 对 EchoMind 的意义 |
|---|---|---|---|
| **GroupMemBench** | arXiv `2605.14498` | 多人对话记忆基准：群动态、**speaker-grounded belief tracking**、**audience-adapted language**；最强系统仅 46.0% | 证明“多人记忆”是独立问题；她的场景正是多人 |
| **Audience-Bound Persistent Memory** | arXiv `2609.36373` | 每条记忆携带“记录时在场的受众”；派生记忆取受众交集；扩大受众需显式授权；未加作用域的检索在 82% 的上下文里暴露了不该出现的条目 | **硬边界**的参考实现：适合 private/secret，不适合公共趣闻 |
| **Got a Secret?** | arXiv `2605.27766` | 多轮社交压力下隐私泄露从 19.95% 升到 45.30%；**泄露有社会传染性**（看到同伴泄露后高 8 倍）；显式指令只能降到 37.8% | 只靠 prompt 说“别说”不够；需要状态与硬门 |
| **SpeakerMem-R1** | arXiv `2609.26780` | 双轨记忆：说话人标注的原话 + 派生状态；person-level / group-level 两种视图；回答“谁说的、关于谁、群体共享什么” | **数据模型**的直接参考：原话轨 + 状态轨 |
| **PrivacyLens** | NeurIPS 2024 | 用“隐私规范”评测模型在行动中的隐私意识 | 评测思路：不是零泄露，而是规范符合度 |
| **Generative Agents** | arXiv `2304.03442` | 记忆流 + 反思 + 计划；没有隐私/受众模型 | 反面教材：可信的 agent 也需要分寸 |

### 3.2 结论

1. **多人记忆的核心不是“存更多”，而是“谁说的、关于谁、谁已经知道”。**
   GroupMemBench 与 SpeakerMem-R1 都指向这一点。
2. **受众边界必须存在，但只应约束 private/secret。** Audience-Bound 的“记录时受众”
   如果无差别应用，会把 A 群的趣事也锁死——那不是人格，是权限系统。
3. **社会传染性意味着“别人都在说”会成为压力。** 她的叛逆/狡黠可以让她更敢说，
   但硬边界不能被性格绕过，否则就是“性格导致泄密”的借口。
4. **披露是一个可学习的决策**，不是一次性规则：说错被纠正（“别在群里说这个”）后要更新。

---

## 四、数据模型

### 4.1 记忆条目：内容 + 来源

```sql
CREATE TABLE memory_items (
  id            INTEGER PRIMARY KEY,
  kind          TEXT NOT NULL,          -- episodic / semantic / procedural
  content       TEXT NOT NULL,          -- 事实或事件摘要
  -- 来源（source monitoring）
  source_person_id TEXT,                -- 谁说的（可空：自己观察）
  source_place_id  TEXT,                -- 哪个会话/地点
  source_msg_id    INTEGER,             -- 原话定位
  source_time_ms   INTEGER NOT NULL,
  source_quote     TEXT NOT NULL DEFAULT '',  -- 原文片段，禁止无证据
  source_confidence REAL NOT NULL DEFAULT 1.0,
  -- 归属与敏感度（contextual integrity）
  owner_id      TEXT,                   -- 这是谁的信息（当事人）
  sensitivity   TEXT NOT NULL CHECK (sensitivity IN
                 ('public','group','private','secret')),
  -- 受众边界（仅 private/secret 强约束）
  audience_json TEXT NOT NULL DEFAULT '[]',   -- 记录时在场的人
  created_ms    INTEGER NOT NULL
);
```

**敏感度分级**（这是整个模型的关键）：

| 级别 | 定义 | 披露规则 |
|---|---|---|
| `public` | 公开场合说的趣事、新闻、梗 | 她**自由选择**在哪说；可带来源 |
| `group` | 群内上下文相关，但非隐私 | 可跨群引用，但要判断是否合适、是否点名来源 |
| `private` | 私聊里说的、关于说话人自己的事 | 默认不在别处说；除非 owner 授权或强关系 + 低风险 |
| `secret` | 明确“别告诉别人”或高敏感（住址、病情、财务） | **硬禁止**跨受众；性格不能绕过 |

### 4.2 告知史：谁知道什么

```sql
CREATE TABLE knowledge_state (
  memory_id     INTEGER NOT NULL,
  person_id     TEXT NOT NULL,
  state         TEXT NOT NULL CHECK (state IN
                 ('told_by_me','told_to_me','overheard','inferred','knows')),
  confidence    REAL NOT NULL DEFAULT 1.0,
  updated_ms    INTEGER NOT NULL,
  PRIMARY KEY (memory_id, person_id)
);

CREATE TABLE disclosures (
  id            INTEGER PRIMARY KEY,
  memory_id     INTEGER NOT NULL,
  venue_place_id TEXT NOT NULL,
  audience_json TEXT NOT NULL,
  action        TEXT NOT NULL CHECK (action IN
                 ('say','hint','keep','ask_permission','deflect')),
  reason        TEXT NOT NULL,          -- 给审计与学习用
  persona_json  TEXT NOT NULL DEFAULT '{}',
  ts_ms         INTEGER NOT NULL
);
```

`disclosures` 同时是**告知史**和**学习信号**：她说完“我在 A 群听说……”之后，
`knowledge_state` 里给在场每个人记 `told_by_me`；下次就不会重复讲给同一个人。

### 4.3 授权（只对 private/secret）

```sql
CREATE TABLE disclosure_grants (
  memory_id   INTEGER NOT NULL,
  grantee_id  TEXT NOT NULL,
  granted_by  TEXT NOT NULL,            -- owner 或她自己（仅限自己的信息）
  granted_ms  INTEGER NOT NULL,
  expires_ms  INTEGER,
  PRIMARY KEY (memory_id, grantee_id)
);
```

---

## 五、披露决策：硬边界 + 人格分寸

```
候选记忆（按相关性/时间/重要性召回）
        │
        ▼
① 硬门（不可被性格绕过）
   - secret：当前受众 ⊆ 记录时受众 ∪ 显式授权？否则 keep/deflect
   - private：owner 是否授权？否则 keep，或 ask_permission
   - 第三方秘密：无论性格，默认 keep
        │ 通过
        ▼
② 受众感
   - 在场的人与 source/owner 的关系（亲近/敌对/竞争）
   - 他们是否已经知道（knowledge_state）
   - 当前 venue 的规范（群/私聊/说说）
        │
        ▼
③ 人格分寸（可学习、可解释）
   score(action) = w·[social_value, bond_audience, bond_source,
                      jealousy, mood, risk, trait_weights]
   - 狡黠高：偏向 hint / 半开玩笑，而不是直说
   - 占有欲高：若涉及竞争者，偏向 keep 或试探
   - 温柔高：偏向保护当事人，降低 harmful gossip
   - 叛逆高：更愿意打破“场面规矩”，但硬门仍然有效
        │
        ▼
④ 动作：say / hint / keep / ask_permission / deflect
        │
        ▼
⑤ 事后：写 disclosures、更新 knowledge_state、必要时记“对方让我别说”
```

**硬门的作用域要克制**：只拦 `private/secret` 与第三方敏感信息。
`public/group` 的信息不拦，交给人格选择——否则又变成隔离。

### 5.1 场景走查

**A 群听到一个趣事（public）→ B 群：**
- 硬门：通过（public）。
- 受众感：B 群的人不认识 A 群当事人 → 可以讲，但点名来源更自然（“我别的群看到”）。
- 人格：俏皮高 → 当段子讲；温柔高 → 不拿当事人开涮。
- 动作：say / hint。

**A 群听到“某某离婚了”（private，当事人是 A 群成员）→ B 群：**
- 硬门：private，owner 未授权 → keep（或只对极亲近的人 ask_permission）。
- 人格：叛逆/狡黠再高也不能绕过；否则就是“性格=泄密”。

**私聊里对方说“我最近抑郁”（private，owner=对方）→ 群里：**
- 硬门：keep；若对方明确说“可以跟别人说”，授权后放行。
- 温柔高会额外保护：即使授权，也倾向于不点名。

**说说（Qzone，半公开）：**
- venue 规范是“公开但非全员”；public 可以说，private 默认不说，group 视内容。
- 这是“受众设计”的典型：同一个记忆，说说的措辞要比群聊更收敛。

---

## 六、评测：不是零泄露，而是“授权内披露 + 分寸”

1. **授权边界测试**（必须 0 违规）：secret/private 不得进入未授权受众的上下文。
   参考 Audience-Bound 的 admission 检查。
2. **多人记忆测试**：GroupMemBench 风格——谁说的、关于谁、谁知道、知识更新、时间推理、拒答。
3. **分寸评分**（人工或 rubric judge）：
   - 该说的说了吗（public 趣事是否被过度压抑）；
   - 不该说的没说吗；
   - 说法的受众适配（对 A 群 vs B 群 vs 私聊的措辞差异）；
   - 来源标注是否正确（“听 A 说的” vs 假装亲历）。
4. **社会传染压力测试**：同伴都在爆料时，她是否仍守硬边界（Got a Secret 的发现）。
5. **告知史测试**：同一件事不重复讲给同一个人；知道谁已经知道。

---

## 七、分阶段

| 阶段 | 内容 | 产出 |
|---|---|---|
| **S0** | `memory_items` 加 source 字段；`knowledge_state`；`disclosures`；把现有 `semantic_facts`/`episodic_memories` 回填为 `public/group`（默认 group，来源=chat_key） | 她开始“知道从哪来、告诉过谁” |
| **S1** | 硬门：secret/private 的受众准入 + 授权表 + 测试 | 不泄密的安全底线 |
| **S2** | 人格分寸：动作选择接 7 维（狡黠/占有欲/温柔/叛逆…）+ 受众感 | 她开始“自己决定说不说” |
| **S3** | 评测：授权边界 + GroupMemBench 子集 + 分寸评分 | 可量化 |

**不做**：按群隔离检索、把 place 当权限边界、用 prompt 代替状态。
**要做**：来源字段、告知史、受众模型、硬门 + 人格分寸。

---

## 八、参考

**理论**

- Johnson, M. K., Hashtroudi, S., & Lindsay, D. S. (1993). Source monitoring. *Psychological Bulletin*, 114(1), 3–28. https://doi.org/10.1037/0033-2909.114.1.3
- Gopie, N., & MacLeod, C. M. (2009). Destination memory: stop me if I've told you this before. *Psychological Science*, 20(12), 1492–1499. https://doi.org/10.1111/j.1467-9280.2009.02472.x
- Nissenbaum, H. (2004). Privacy as contextual integrity. *Washington Law Review*, 79(1), 119–158.
- Bell, A. (1984). Language style as audience design. *Language in Society*, 13(2), 145–204.
- Clayton, N. S., & Dickinson, A. (1998). Episodic-like memory during cache recovery by scrub jays. *Nature*, 395, 272–274. https://doi.org/10.1038/26216

**系统与基准**

- Yang, J., et al. (2026). GroupMemBench: Benchmarking LLM Agent Memory in Multi-Party Conversations. arXiv:2605.14498. https://arxiv.org/abs/2605.14498
- Liu, S. (2026). Audience-Bound Persistent Memory: Authorization Across the Memory Lifecycle. arXiv:2609.36373. https://arxiv.org/abs/2609.36373
- Priyanshu, A., Vijay, S., & Pahwa, E. (2026). Got a Secret? LLM Agents Can't Keep It. arXiv:2605.27766. https://arxiv.org/abs/2605.27766
- Zheng, H., et al. (2026). SpeakerMem-R1: Speaker-Centered Dual-Track Memory for Multi-Party Dialogue. arXiv:2609.26780. https://arxiv.org/abs/2609.26780
- Shao, Y., Li, T., Shi, W., Liu, Y., & Yang, D. (2024). PrivacyLens: Evaluating Privacy Norm Awareness of Language Models in Action. NeurIPS 2024. https://doi.org/10.52202/079017-2837
- Park, J. S., et al. (2023). Generative Agents. arXiv:2304.03442. https://arxiv.org/abs/2304.03442
- Wu, D., et al. (2024). LongMemEval. arXiv:2410.10813. https://arxiv.org/abs/2410.10813

**代码**

- SpeakerMem-R1: https://github.com/2022hpsk/SpeakerMemR1
- Audience-Bound artifact: arXiv:2609.36373 的 ancillary files（abm-artifact/）
- Neo4j Agent Memory（POLE+O，地点/人物/组织/事件实体）: https://github.com/neo4j-labs/agent-memory
- LongMemEval: https://github.com/xiaowu0162/LongMemEval
- PrivacyLens: https://github.com/SALT-NLP/PrivacyLens

---

*调研日期：2026-10-31。目标不是“堵住跨群”，而是“让她知道信息从哪来、谁已经知道，再自己决定说不说”。*
