# EchoMind 总账（Master Backlog）：硬编码 · 身份解耦 · 关系模型

> 📚 文档入口：[`docs/README.md`](README.md)（现行契约 / 设计说明 / 历史规划 / 交付纪律）

> **唯一权威**：本文件以 `main` 分支为准。A 线开工前先执行
> `git checkout main -- docs/MASTER_BACKLOG.md` 同步，收工前必须回填状态。
>
> **纪律（防止跑偏）**
> 1. 同一时间只允许 **1 个** 未合并的 A 线分支；开新分支前必须先把当前分支收口或登记为"暂停"。
> 2. 每完成一步，必须在本文对应行把 `⏳` 改为 `✅`，并写上 commit。
> 3. 任何"顺手发现的新问题"先登记到第六节，不当场开工。
> 4. 每次会话结束前，更新第八节「变更日志」。

**图例**：✅ 已完成并上线 ｜ 🚧 进行中 ｜ ⏳ 待开工 ｜ ⛔ 已决策不做 ｜ 🧊 暂停（已登记）

**最后更新**：2026-10-30 ｜ 维护者：架构审计会话

---

## 一、 身份、权限与配置（原「19 项」第 1 类 + owner_qq）

### 1.1 已确定的产品决策

| ID | 决策 | 内容 |
|---|---|---|
| D1 | 不设 anchor | 她认为"特别的人"由关系账本涌现，不硬编码 |
| D2 | 只保留管理员 | `operator` 仅用于纠错（改配置/删错误记忆/封禁），**无情感特权** |
| D3 | 写操作强制 token | 控制台写（POST/PUT/PATCH/DELETE）一律要求 token，取消 loopback 免鉴权 |
| D4 | 旧关系数据清零 | `affinity=9999` / `role=owner` 全部按新规重来 |
| D5 | A 方案 | bond_depth 六项全做（不降级为四项） |

### 1.2 硬编码清单（核实后）

| # | 项 | 位置 | 决策/方案 | 状态 |
|---|---|---|---|---|
| H1 | 主人 QQ `owner_qq` | 99 处 / 17 文件 | 情感特权已移除；`operator_ids` 已落地（禁言改由 operator 触发）；字段删除待续 | 🚧 |
| H2 | 自身 QQ `self_qq` | `config.py:41`、`main.py:155` | 保留但加控制台入口（A5） | ⏳ |
| H3 | 唤醒小名 `keywords` | 两处硬编码已消除：语音唤醒走 `bot_names`，人格保存走配置 `store.keywords` | **双源 bug 已修**，配置加名即生效 | ✅ `907aa56` |
| H4 | 群白名单 `allow.groups` | `config.py:227`、`main.py:156` | 控制台可编辑（A5） | ⏳ |
| H5 | 私聊白名单 `allow.private` | `config.py:228`、`main.py:157` | 控制台可编辑（A5） | ⏳ |
| H6 | 默认冒泡群 | `main.py:56,170` 取 `allowed_groups[0]` | 改为显式配置项；**不要**改成"最在乎的人"（会形成注意力自激环） | ⏳ |
| H7 | NapCat WS/HTTP/Token | `config.py:178-185` | 控制台可改 + 重连（R2）；`http_token` 已于 Stage 28 接线 | 🚧（读取已修，UI 待做） |
| H8 | 潜意识探针模型/开关 | `main.py:136` 固定复用主模型 | 配置化（可指定更便宜的模型） | ⏳ |
| H9 | 控制台写鉴权 | `web/app.py` loopback 免 token | D3：写强制 token + `admin_audit` 审计 + 前端自动取 token | ✅ `rg(A1)` |
| H10 | 3 个 skill 的 `ownerQq` | `data/config.json` → `skills.affinity.ownerQq` / `qzone-mood-showcase.ownerQQ` / `possessive-heart.ownerQq` | 迁 `operatorId` 或删除 | ⏳ |

### 1.3 施工分期（Stage 29-A）

| 期 | 内容 | 状态 |
|---|---|---|
| A1 | 写鉴权 + 审计 + 前端 token（`operator_ids` 留到 A3b 与聊天内命令一起做） | ✅ |
| A2a | bond_depth 六项算法 + Beta 信任 | ✅ `b1c7ec9` |
| A2b | 事件计数器持久化 + 六特征派生（**尚未接线**） | ✅ `653d0ca`（store 未接线） |
| A2c | 接线：`live_client` 记 impact/betray；历史回填 30 人计数；饱和点按 P95 校准 | ✅ `e2e6ba9` `/` `6c793f8` |
| A3 | 去特权 ✅；`operator_ids` ✅；深度写回 + 清零迁移 ✅ `1464ef3`；剩：删除 `owner_qq` 字段 | 🚧 |
| A4 | 人格语料去硬编码（见第二节） | ⏳ |
| A5 | 身份配置卡：`GET/POST /api/config/identity`，保存即热更新（名字/小名/白名单/默认群/自身QQ）+ 审计 | ✅ `54a4033`/`06a1891` |
| A6 | 验证套件（LOGO、跨群一致性、抗操纵、消融） | ⏳ |

---

## 二、 人格语料硬编码（40 处 / 17 文件）

> 说明：报告中列的 7 处是核心；实际扫描到 **40 处 / 17 个源文件**（含 `cybernetics` / `prompt_composer` / `ext_routers` / `enrichers` / `perceptual_gate` / `migrator`）。

| 批次 | 文件 | 硬编码内容 | 状态 |
|---|---|---|---|
| P1 核心 prompt | probe / hippocampus / agent_runner / frame_renderer / personality / scheduler | **已改为读取 `bot_naming()`**（配置 `botName`+`keywords`） | ✅ `rg(A4)` |

| P1 | `runtime/agent_runner.py:294` | `f"回音(我): …"` | ⏳ |
| P1 | `mind/frame_renderer.py:125`、`mind/personality.py:153`、`runtime/scheduler.py:159` | 「回音此刻的认知…」「请以回音的口吻…」 | ⏳ |
| P1 | `mind/epistemic.py:10`、`mind/drives.py:22` | 正则「回音的主人」「还是回音\|还是尾尾」 | ⏳ |
| P2 前端 | `app.js`、`index.html` | 聊天自称/标题/占位全部读 `bot_name` | ✅ `8806fda`/`51bea06` |
| P3 其它 | 停止词/概念忽略词/默认参数 | 全部改为「基础词 ∪ 配置名」动态构造 | ✅ `db41e3d` |

**做法**：统一改为读取 `bot_name` / `keywords` / `role_text`（模板插值，不引入模板引擎）；P1 完成即"改名后自认知一致"。

---

## 三、 节律 / 门控 / 数值常数（核实值，纠正报告中的 60 秒）

| 常数 | 真实值 | 位置 | 状态 |
|---|---|---|---|
| 防抖窗口 | **2.0 秒** | `main.py:165` | ⏳ |
| 外围插话冷却 | **75 秒** | `perceptual_gate.py:123` | ⏳ |
| 跟聊窗口 | **300 秒**（报告写 60 秒，有误） | `perceptual_gate.py:123` | ⏳ |
| 冷暴力时长 | **900 秒（15 分钟）** | `perceptual_gate.py:152` | ⏳ |
| 作息 | `00:00–07:30` 睡、`13:00–14:00` 午休、"抱着尾巴"文案 | `mind/circadian.py:27-88` | ⏳ |
| 好感吸引子 | 初始 30 / 对手 45 / Dunbar 85 / owner 9999 / 阈值 (50,100,200,500) | `memory_consolidator.py:27-29,64,153` | ⏳（9999 随 D4 清零） |
| 检索上限 | 事实 28 / 情景 8 / 性格 15 | `facade.py:241`、`facade.py:150`、`personality.py` | ⏳ |

---

## 四、 关系模型：Earned Bond Depth

### 4.1 算法（已实现）

$$D_u=100\cdot\sigma\big(1.6(1.0f+1.2v+1.4r+1.0c+1.1i-1.6b-2.6)\big),\quad w_{care}=\mathrm{clamp}\Big(\tfrac{A-38}{70}T(0.45+0.55\tfrac{D}{100}),0,0.97\Big)$$

- 文件：`mind/bond_depth.py`（六项 + `beta_trust_update`）
- 参数溯源：每个常数带 `param: src:|convention:|fit:` 标签，`tests/architecture/test_param_provenance.py` 强制（PARAM-01~04）。
- 现状：**11 个常数仍是 `fit:pending`**（手调），必须由数据替换。

### 4.2 事件采集（已建，未接线）

| 组件 | 文件 | 状态 |
|---|---|---|
| 计数器值对象 | `domain/bond_stats.py`（`BondDepthStats` / `BondFeatures`） | ✅ |
| 端口 | `domain/ports.py` → `IBondDepthStore` | ✅ |
| SQLite 适配器 | `adapters/storage/bond_depth_repo.py` | ✅ |
| 六特征派生 | `mind/bond_features.py` | ✅ |
| **接线**（msg / 回话 / impact / betray） | `live_client.py`、`bootstrap.py` | ✅ `e2e6ba9` |
| 深度入 `w_care`（读取时注入） | `bond_scoring.py` → `drives.compute_care_weight` | ✅ `dad7a56` |
| 深度**持久化**到 `social_bonds.bond_depth` | `bond_scoring` 写回 + `set_bond_depth` | ✅ `1464ef3` |

### 4.3 跨群自适应（B 系列，待做）

| 层 | 内容 | 依据 | 状态 |
|---|---|---|---|
| L1 | 群内分位归一化（替代绝对计数） | TF-IDF/BM25 思想 | ✅ `bond_adapt.normalize_group`（未接线） |
| L2 | 群内仿射校准（绝对深度 → 群内分位） | Platt 1999；Zadrozny & Elkan 2002 | ✅ 已接入 `bond_scoring._calibrate` |
| L3 | 经验贝叶斯收缩（小群退回恒等校准） | Gelman & Hill 2007；Efron & Morris 1975 | ✅ 已接入（τ=2，按群人数收缩） |
| L4 | 漂移检测（Page–Hinkley），只告警不自动改 | Page 1954 | ✅ 已接入 `observe_group_drift`（每群一个检测器，报警写日志） |
| 验证 | 留一群交叉验证（LOGO）+ 跨群一致性 | 域泛化惯例 | ⏳ |

### 4.4 拟合数据（人工标注暂缓）

- 已导出 `data/stage29_labels.csv`（29 人）与盲评表（本地、gitignore）；
- 决策：**不依赖人工标注**，改用"跨群同一人配对一致性 + 对方投资行为 + 极端锚点"弱监督；
- 结论：先做 L1/L2（无需标签），再做 L3。

---

## 五、 已完成（Stage 28，供追溯）

| 项 | 内容 | 提交 |
|---|---|---|
| F1 | 生产链路 `social_reward` 改由 6D 和弦反推 | `e023da4` |
| F6 | 和弦缓存上界 256 | `9bdcc80` |
| F4 | 情绪单次应用 | `720b671` |
| F2/F9 | tier-1 补探针 / 上下文按群隔离 | `dd0255a` / `8cb91e9` |
| F5 | 冷却传参 + chord 唤醒武装冷却 | `1bedd35` |
| F3 | 突发探针 1.5 秒合流 | `4476cb2` |
| F7 | HTTP Token 接线 | `7240f9f` |
| F8/F8b | 视觉端口化 / enricher 故障隔离 | `a0827cb` / `8bb9ea7` |
| F10 | 删除 taboo 死分支 | `44ea6db` |
| C1 | 拆 `ports_media.py` + `cache_media_description` 端口化 | `1019a8d` + `43bca5b` |
| 契约 | RGR-01~10 + AB-01~08 + Stage 28 评估报告 | `335fb9c` 等 |

---

## 六、 新发现待登记（不立刻开工）

| ID | 发现 | 处理建议 |
|---|---|---|
| N1 | `w_aversion` 完全不看 depth，只对 owner 打 0.35 折 | A3 时改为纯关系推导（她会真的对在乎的人发火） |
| N2 | 7 维人格无"逐日涨幅上限" | 加阻尼（每日 ≤ ±6），防独占焦虑饱和 |
| N3 | `derive_emergent_trait` 的 taboo 文案固定、不去重 | 去重 + 语义合并，最多 3 条 |
| N4 | `betrayal` 若把拌嘴计入会与吃醋形成振荡环 | 白名单：仅欺骗/冲突/食言计入 |
| N5 | `ports.py` 已 234 行、`facade.py` 300 行，长期贴顶 | 继续按域拆分（参照 C1） |
| N6 | `data/echomind.db` 仅 2 天历史（4116 条） | 深度模型短期内只能"浅层生效"，需时间积累 |

---

## 七、 分支与提交状态

| 线 | 分支 | HEAD | 状态 |
|---|---|---|---|
| B（生产） | `main` | `3689d9b` | 服务 :3310 运行中；领先 `origin/main` **3** 个提交（未推送） |
| A（修复） | `lane/a-stage29` | `653d0ca` | 领先 `main` **6** 个提交，全部门禁绿（99 passed / Cov 90.92%） |

A 线未合并提交：`b1c7ec9`(A2a) · `5c04e03`(计划) · `a21fa53`(参数溯源) · `1755e45`(文档) · `171ffa6`(gitignore) · `653d0ca`(A2b)

---

## 八、 建议执行顺序（下一步只做这个）

| 顺序 | 任务 | 验收 |
|---|---|---|
| 1 | **A2c 接线**（`chord_gateway` 记 impact/betray；`live_client` 记 msg/responded；bootstrap 注入） | 回放后 `bond_depth_stats` 有数据；红绿测试 |
| 2 | **回填脚本**（从 `chat_messages` 回填 msgs/replies/responses/sessions） | 29 个联系人计数与手工核对一致 |
| 3 | **B1 群内归一化** | LOGO 跨群一致性中位差 ≤ 8 分 |
| 4 | **B2 校准表** | 校准斜率 0.8–1.2 |
| 5 | **A1 写鉴权** | ✅ 无 token 写 → 401；有 token → 200 + 审计 |
| 6 | **A3 删除 owner_qq** | 无 owner 时嫉妒仍触发；`w_care` 连续 |
| 7 | **A4 语料去硬编码** | 改名后自认知一致（回放 + 前端） |
| 8 | **A5 配置卡** | ✅ 控制台可改、保存即热生效、写操作留审计 |

---

## 九、 变更日志

| 日期 | 变更 |
|---|---|
| 2026-10-31 | **注入位置对照**：同一温柔阶梯改放 system。±5 无变化（0.438→0.458），±15 由 0.667（不显著）升到 **0.750（显著）**，±20/30 未测。两次运行的差异 +0.083、标准误约 0.13，**在噪声内**——只能说 system 至少不差、可能把阈值从 ~20 降到 ~15，确认需配对设计。已写入敏感性报告与能力台账。分支 `lane/a-stage46`。 |
| 2026-10-31 | **人格可辨阈值**：温柔维阶梯（n=24/档）±5→0.438、±15→0.667、±20→**0.854**、±25/±30→0.875；单条回复阈值约 **17–20 分**。结论：状态层 ±10 在单条上低于阈值（微妙而非变脸），年度基线 4 分只能靠长期/并排对比感知——要“被感觉到”应改表达层（A3），不是加大幅度。runner 新增 `--delta` 对称带宽模式；报告已更新。分支 `lane/a-stage46`。 |
| 2026-10-31 | **人格敏感性审计完成**：7 维 × 极端档 × 成对盲评（Wilson 下界判据）。通用情境 5/7 显著（confidence 0.896、defiance 0.833、warmth/tsundere/playfulness 0.750）；占有欲改用专属触发情境后 0.604→**0.833**（证明是条件性特质）；guile 补到 24 条仍 0.625，未确立，且失败模式显示“替自己开脱会狡黠、替别人撒谎不狡黠”。报告 `docs/PERSONA_SENSITIVITY_REPORT.md`。期间修掉评测器 A/B 映射反向的 bug（否则会误判为人格无效），补回归测试 `test_sensitivity_verdict_mapping.py`。分支 `lane/a-stage46`。 |
| 2026-10-31 | **敏感性审计 runner（P6e-live）**：`scripts/persona_sensitivity.py` 实现7 维 × 3 档（低/基准/高，仅变动目标维）× 24 情境的生成 + 成对盲评；判据改为统计性的「Wilson 下界 > 0.5，且 ≥5/7 维通过」，不再用拍的 70%。默认 `--dry-run` 零成本核对（336 生成 + 168 盲评），`--scenarios 4` 可先小样本试跑；镜像生产把人格块放在 user 消息的位置。尚未实际调用模型。分支 `lane/a-stage46`。 |
| 2026-10-31 | **修复安抚棘轮（P6e 发现）**：`soothing` 原先对每次非负评价触发，中性聊天也会把效价抬高 +3.98；现改为仅当距上次接触 ≥30 分钟（`REUNION_GAP_MIN`，在实测间隔 p99 之外）才触发。情绪方向评测 4/5 → **5/5**。同时按职责拆分 `drives.py`（292→251 行）：时序演化移入 `mind/drives_temporal.py`，评价上下文收为 `_appraisal_context`。分支 `lane/a-stage46`。 |
| 2026-10-31 | **P6e 评测骨架落地**：`scripts/eval_persona.py` 三套离线评测（稳定/情绪/召回）＋敏感性 live 占位。实测：365 天基线净变化 **+3.991**（预算 4，无饱和）；情绪方向 4/5；记忆召回直接 **100%**、改写 **50%**——与随机基线 50% 持平，量化了词面召回的上限。同时修掉一个实现缺陷：结算时间戳原先从 `plastic_logs` 推断，模拟/真实时钟错位会让回归反向；现改为 `persona_settlement` 显式记录。发现：中性互动仍抬高效价 +3.98（安抚分支对所有非负评价触发），已登记为能力缺口。分支 `lane/a-stage46`。 |
| 2026-10-31 | **E2 两层人格落地（C 方案）**：慢层基线（年净变化 ≤4 分、日推 0.01333、最大偏离 12、回归 0.00111/天，半衰期 ≈624 天）+ 快层状态（单步 ≤4、幅度 ≤10、半衰期 45 分钟）。回合不再写基线，改为记录状态与观察、次日结算（`persona_state` / `persona_pending` 表 + `IPersonaLayerStore`）；控制台展示 `基线+状态` 的有效值。红测试 `test_persona_two_layers.py`（65→67）已转绿；注册 `ECHOMIND-E1-013/014`（状态层幅度/半衰期待校准）。分支 `lane/a-stage46`。 |
| 2026-10-31 | **E0 证据基座落地**：参数台账 `docs/params/ledger.json`（45 条，四类溯源 + 债务棘轮，`scripts/param_gate.py`）与能力台账 `docs/capabilities.json`（20 条，状态/缺口/验收，`scripts/capability_gate.py`）；两道门禁接入 `qa_gate.sh`（5 步 → 7 步）；新增 `tests/architecture/test_evidence_ledger.py`（2 例）。登记首个可判定矛盾：人格动力学稳态偏移 `D/r=600` 远超量程，持续正向互动必然饱和（`ECHOMIND-E1-002`）。分支 `lane/a-stage46`，未合并 `main`。 |
| 2026-10-30 | B2–B4 接入评分链路：`attach_bond_depth` 现在执行「绝对深度 → L2 仿射校准 → L3 按群人数收缩 → 与 L1 分位融合」，并对每群均值跑 Page–Hinkley 漂移告警（实测：31 人，原始 88.6/72.7/84.3 → 校准后 89.3/81.3/72.1，排序更贴近群内相对位置）；A5 完成：控制台「👑 身份与群聊绑定」卡（名字/小名/自身QQ/群白名单/私聊白名单/默认群），保存经 `POST /api/config/identity` 落盘并热更新 naming/allowlists；修掉外层 ASGI app 中间件拿不到 db 导致审计缺失的 bug；A4 收尾：前端（标题/聊天自称/占位）、停止词、概念忽略词、默认参数全部跟随配置名；全库仅剩 `naming.py` 的默认值；A4-3：唤醒小名统一走配置（修复双源硬编码），`bot_names` 注入 runtime；A4-1：prompt 去「主人」化（中性措辞）；A4-2：新增 `BotNaming`，probe/hippocampus/renderer/scheduler/personality 全部按配置名渲染（默认仍是回音，改名即生效）；**D4 已执行**：备份 `data/backup_pre_d4_20261030_160722.db`；3 行 9999/owner → `A=30/T=.75/member/D=0`；`bond_depth_stats` 清空；`w_care(前主人)` 0.970 → 0.000；A3b-2/3：深度写回 `social_bonds.bond_depth`；新增清零迁移 `reset_privileged_bonds`（dry-run 演练：3 行，清洗后 owner 变回普通成员、`w_care=0`）；A3b-1：新增 `operator_ids`（config 解析 + 容器注入），禁言改由 operator 触发，普通群友无法再下禁令；A3 去特权：`w_care` 不再对 owner 短路、`w_aversion` 不再打 0.35 折、奖励不再 ×1.12、嫉妒/立场/显著性不再有 owner 分支（`555a03a`）；4 条相关测试改为「先有 bond 才有关爱」；A1 落地：API 写操作强制 token、`admin_audit` 审计、前端自动获取/提示 token（`operator_ids` 推迟到 A3b）；A2c 接线 + 回填 + P95 校准（`e2e6ba9`/`6c793f8`）；深度接入 `w_care`（`dad7a56`，读取时注入）；B1–B4 四层自适应算法落地（`bond_adapt.py`，6 条测试，未接线）；建立本总账；登记 H1–H10、P1–P3、时序常数、bond_depth 现状（A2a/A2b）、B1–B4 自适应计划、N1–N6 新发现、A/B 线状态 |
