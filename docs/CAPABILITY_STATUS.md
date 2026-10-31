# 能力状态（自动生成，勿手改）

> 由 `scripts/capability_gate.py` 生成。修改请编辑 `docs/capabilities.json`。

| 状态 | 数量 |
|---|---|
| ✅ implemented | 5 |
| ⚠️ partial | 8 |
| ❌ absent | 5 |
| ⛔ contradicted | 3 |

| ID | 能力 | 状态 | 缺口 / 验收 |
|---|---|---|---|
| CAP-PERSONA-SINGLE-SOURCE | 7 维人格默认值与边界只有一处定义 | ✅ implemented | tests/architecture/test_persona_single_source.py::test_storage_defaults_come_from_the_shared_table |
| CAP-ATTACHMENT-CONTINUOUS | 依恋腔调由四象限原型 softmax 连续加权，无硬阈值跳变 | ✅ implemented | tests/unit/test_personality_invariants.py::test_i3b_tone_is_continuous |
| CAP-DYNAMICS-BOUNDED | 人格分两层：慢层基线年净变化 ≤4 分、单日 ≤0.0133、最大偏离 12；快层状态单步 ≤4、幅度 ≤10、半衰期 45 分钟 | ⚠️ partial | 机制已实现并有测试；状态层幅度/单步/半衰期仍是未校准值（ECHOMIND-E1-013/014），年度预算 4 分为产品约定（带 3–6） |
| CAP-STANCE | 关系姿态只影响渲染与显著性，≤8 分且不回写人格本体 | ✅ implemented | tests/unit/test_persona_stance.py::test_stored_personality_is_not_mutated |
| CAP-TRAIT-SCOPE | 词条按类别上限（8/4/4/3）与作用域衰减 | ✅ implemented | tests/integration/test_trait_scope_and_caps.py::test_category_caps_are_enforced |
| CAP-PROBE-DIGEST | 潜意识探针 prompt 携带一行人格摘要 | ✅ implemented | tests/unit/test_probe_persona_summary.py::test_probe_prompt_contains_persona_digest |
| CAP-PARAM-PROVENANCE | 所有可调常数声明来源（src/data/convention/fit_pending） | ⚠️ partial | E0 建立 50 条台账并门禁化；代码内联 param: 标签仍只有少量，多数条目为 fit_pending（实验未做） |
| CAP-TRAIT-GROWTH | 人格会从互动中长出新的习惯/喜好/雷点 | ❌ absent | derive_emergent_trait 只有 5 条固定文案；trait_text 精确去重；last_used_ms 列从未读写 |
| CAP-CLOSED-LOOP | 人格由可观测反馈闭环驱动 | ❌ absent | reward 来自探针自评；探针失败时退化为常数 0.08；全库无延迟反馈/后续消息评估 |
| CAP-SELF-NARRATIVE | 存在跨会话的自我叙事，并参与冲突判定 | ❌ absent | 只有 140 字情绪余波；role_text 静态；冲突优先级是 prompt 内的硬编码段落 |
| CAP-FTS5 | SQLite FTS5 全文检索 | ❌ absent | 全库无 FTS5；召回是 Python 侧中文 2-gram 重叠 |
| CAP-INTENTION-STACK | 短期挂念栈（BDI 意图，≤3 槽） | ❌ absent | IntentionItem 在全库从未被构造；filter_unfulfilled_intentions 永远作用于空元组 |
| CAP-FIVE-SLOTS | 微内核五大扩展槽全部可用 | ⚠️ partial | sensor/tool 已用；facet/proposer/panel 三个槽位零注册实现 |
| CAP-SEVEN-GATES | 7 道自动化质量门禁 | ⚠️ partial | 脚本实际 5 步；hypothesis 未独立成门禁；迁移对账与故障注入缺失（E0 新增了参数/能力两道） |
| CAP-SEMANTIC-EVAL | 对人格一致性/记忆准确率/情绪合理性有语义评测 | ⚠️ partial | 离线三套件（稳定/情绪/召回）+ live 敏感性审计已跑通：6/7 维在盲评中显著优于随机；guile 0.625 未确立；尚无人工盲评与中等幅度敏感性 |
| CAP-HEXACO | 7 维人格对应 HEXACO 六轴 | ⛔ contradicted | 7 维为 warmth/tsundere/playfulness/possessiveness/confidence/guile/defiance，与 HEXACO 无映射矩阵，缺 C/O 轴 |
| CAP-ZERO-LEXICON | 全链路零硬编码词表（Stage 26） | ⛔ contradicted | mind/ 下仍有 40+ 处中文词表与正则（角色冒充词、停用词、机器人关键词） |
| CAP-OPERATOR-NO-PRIVILEGE | operator 只有纠错权限，无情感特权 | ⛔ contradicted | update_sender_bond 对 is_owner 直接置 trust=1.0；且 _check_reactance 对 w_care>=0.85 免除逆反 |
| CAP-MEMORY-EVIDENCE | 事实带来源与时效，冲突可复核 | ⚠️ partial | claims/evidence 表已建但读路径默认关闭（FACTS_V2=off），且转换时 chat_key 被置空 |
| CAP-AUTH-WRITE | 控制台写操作强制 token 并留审计 | ⚠️ partial | auth_key 为空时全放行；/api/session/token 把 token 发给 loopback（隧道下等同公开） |
| CAP-PERSONA-EFFECTIVE | 7 维人格在生成输出上可被盲评识别 | ⚠️ partial | 7/7 维均有证据：极端档 5 维单轮大效应；占有欲专属情境 0.833（单轮试点）；狡黠 R=3 确立 0.708 [0.605,0.812]；温柔 ±15 R=6 确立 0.747 [0.636,0.858]。阈值曲线（±5/10/20/30）仍为单轮试点；自评、无人工盲评、生成方差大 |
