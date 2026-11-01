# 能力状态（自动生成，勿手改）

> 由 `scripts/capability_gate.py` 生成。修改请编辑 `docs/capabilities.json`。

| 状态 | 数量 |
|---|---|
| ✅ implemented | 7 |
| ⚠️ partial | 14 |
| ❌ absent | 2 |
| ⛔ contradicted | 3 |

| ID | 能力 | 状态 | 缺口 / 验收 |
|---|---|---|---|
| CAP-PERSONA-SINGLE-SOURCE | 7 维人格默认值与边界只有一处定义 | ✅ implemented | tests/architecture/test_persona_single_source.py::test_storage_defaults_come_from_the_shared_table |
| CAP-ATTACHMENT-CONTINUOUS | 依恋腔调由四象限原型 softmax 连续加权，无硬阈值跳变 | ✅ implemented | tests/unit/test_personality_invariants.py::test_i3b_tone_is_continuous |
| CAP-DYNAMICS-BOUNDED | 人格分两层：慢层基线年净变化 ≤4 分、单日 ≤0.0133、最大偏离 12；快层状态单步 ≤4、幅度 ≤10、半衰期 45 分钟 | ⚠️ partial | 机制已实现并有测试；状态层幅度/单步/半衰期仍是未校准值（ECHOMIND-E1-013/014），年度预算 4 分为产品约定（带 3–6） |
| CAP-STANCE | 关系姿态只影响渲染与显著性，≤8 分且不回写人格本体 | ✅ implemented | tests/unit/test_persona_stance.py::test_stored_personality_is_not_mutated |
| CAP-TRAIT-SCOPE | 词条按类别上限（8/4/4/3）与作用域衰减 | ✅ implemented | tests/integration/test_trait_scope_and_caps.py::test_category_caps_are_enforced |
| CAP-PROBE-DIGEST | 潜意识探针 prompt 携带一行人格摘要 | ✅ implemented | tests/unit/test_probe_persona_summary.py::test_probe_prompt_contains_persona_digest |
| CAP-PARAM-PROVENANCE | 所有可调常数声明来源（src/data/convention/fit_pending） | ⚠️ partial | 59 条 ledger compliant；仍有 fit_pending/未校准项，不能把 pending 当 fit |
| CAP-TRAIT-GROWTH | 人格会从互动中长出新的习惯/喜好/雷点 | ⚠️ partial | 已具备 evidence 账本、Beta+独立 context 生命周期、active-only；derive_emergent_trait 仍是固定文案，自动 support/candidate 流仍稀疏 |
| CAP-CLOSED-LOOP | 人格由可观测反馈闭环驱动 | ⚠️ partial | 真实回合→evidence→support→ranker 已闭环；自动 support 仍稀有，主要靠手动确认；reward 仍含探针自评 |
| CAP-SELF-NARRATIVE | 存在跨会话的自我叙事，并参与冲突判定 | ⚠️ partial | 已有 evidence-bound 只读叙事投影；A/B 无稳定风格收益，未接 prompt，也未参与冲突判定 |
| CAP-FTS5 | SQLite FTS5 全文检索 | ❌ absent | 全库无 FTS5；召回是 Python 侧中文 2-gram 重叠 |
| CAP-INTENTION-STACK | 短期挂念栈（BDI 意图，≤3 槽） | ❌ absent | IntentionItem 在全库从未被构造；filter_unfulfilled_intentions 永远作用于空元组 |
| CAP-FIVE-SLOTS | 微内核五大扩展槽全部可用 | ⚠️ partial | sensor/tool 已用；facet/proposer/panel 三个槽位零注册实现 |
| CAP-SEVEN-GATES | 7 道自动化质量门禁 | ⚠️ partial | 脚本实际 5 步；hypothesis 未独立成门禁；迁移对账与故障注入缺失（E0 新增了参数/能力两道） |
| CAP-SEMANTIC-EVAL | 对人格一致性/记忆准确率/情绪合理性有语义评测 | ⚠️ partial | 内部 70/70；LongMemEval 500 retrieval 95.4%/MRR .892；QA 417/500（CoT 431，top10 430）；GroupMemBench Finance BM25 40.7/dense 37.4/hybrid 41.1、Technology 39.9；缺 CharacterEval |
| CAP-HEXACO | 7 维人格对应 HEXACO 六轴 | ⛔ contradicted | 7 维为 warmth/tsundere/playfulness/possessiveness/confidence/guile/defiance，与 HEXACO 无映射矩阵，缺 C/O 轴 |
| CAP-ZERO-LEXICON | 全链路零硬编码词表（Stage 26） | ⛔ contradicted | mind/ 下仍有 40+ 处中文词表与正则（角色冒充词、停用词、机器人关键词） |
| CAP-OPERATOR-NO-PRIVILEGE | operator 只有纠错权限，无情感特权 | ⛔ contradicted | update_sender_bond 对 is_owner 直接置 trust=1.0；且 _check_reactance 对 w_care>=0.85 免除逆反 |
| CAP-MEMORY-EVIDENCE | 事实带来源与时效，冲突可复核 | ⚠️ partial | claims 已有 provenance/隐私读路径与 valid_to；FACTS_V2 默认仍 off，线上仍读 legacy facts |
| CAP-AUTH-WRITE | 控制台写操作强制 token 并留审计 | ⚠️ partial | auth_key 为空时全放行；/api/session/token 把 token 发给 loopback（隧道下等同公开） |
| CAP-PERSONA-EFFECTIVE | 7 维人格在生成输出上可被盲评识别 | ⚠️ partial | 历史人工总体 3.24/5；当前 24h 风格约 28 字、长句率 14%；无新人工盲评，真人感未达标 |
| CAP-ACTIVE-ONLY-PROMPT | prompt 只渲染 active trait | ✅ implemented | tests/unit/test_personality_invariants.py::test_only_active_traits_reach_the_prompt |
| CAP-TRAIT-EVIDENCE | 每条 active trait 有可审计 quote/context 证据 | ✅ implemented | tests/integration/test_trait_evidence_ledger.py::test_evidence_roundtrip_and_turn_dedupe |
| CAP-TRAIT-MEMORY | active trait 的 support 能影响记忆检索排序 | ⚠️ partial | 手动 support 6 条已生效；自动 support 稀有，门控仅 BM25>0 |
| CAP-ACTION-ELIGIBILITY | active trait 可追加工具授权并授予拒绝许可 | ⚠️ partial | 默认 additive；whitelist 模式已实现但未启用；refusal 只许可不强制 |
| CAP-RESPONSE-ATTRIBUTION | 记录她的消息之后的回应归因（mention/temporal） | ⚠️ partial | shadow only：不接 trait/ranker/prompt；tier A quote 元数据当前不可用 |
