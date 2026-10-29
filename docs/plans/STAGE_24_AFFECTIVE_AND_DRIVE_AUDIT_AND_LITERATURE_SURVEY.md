# Stage 24 全认知状态空间（24维变量）专项审计、公开文献深度调研与全耦合动力学统一重构方案
**（Stage 24 Full 24-State Cognitive Audit, Deep Literature Survey & Unified Coupled Dynamical Network Architecture — Status: ✅ 已验收通过）**

---

## 一、 第一部分：全系统 24 个心理/情绪/驱力/人格变量的割裂现状审计

在 `EchoMind` 的认知核心中，共有 **4 大类、24 个连续心理状态变量**：
- **A. 五维瞬态/心境情感向量 `AffectiveVector` (5维)**：`valence` (愉悦)、`energy` (精力)、`jealousy` (吃醋)、`shyness` (害羞)、`irritation` (厌烦)
- **B. 四维内驱力向量 `DriveState` (4维)**：`curiosity` (求知)、`attachment` (依恋)、`jealousy_drive` (醋意表达冲动)、`social_expression` (社交表达欲)
- **C. 十二维神经可塑性与人格向量 `plastic_params` (12维)**：`talkativeness`, `proactive_idle_min`, `skepticism`, `verify_impulse`, `curiosity_rate` + 7维人格（`warmth`, `tsundere`, `playfulness`, `possessiveness`, `confidence`, `guile`, `defiance`）
- **D. 三维协同学序参量主磁针 `OrderParameterCore` (3维)**：$\xi_{\text{stance}}$ (姿态核)、$\xi_{\text{epistemic}}$ (求真核)、$\xi_{\text{modality}}$ (声情模态核)

### 🔍 现状审计核心发现：不仅单变量公式简陋，而且 4 大子系统之间处于「开环割裂状态」！

| 割裂/病灶层级 | 定位文件 | 审计发现的孤岛与不科学判据 | 导致的线上失真后果 |
|---|---|---|---|
| **1. 五维情绪内部零耦合**<br>(`A ↛ A`) | `drives.py:72–83` | `valence`, `energy`, `jealousy`, `shyness`, `irritation` 五个维度各算各的：<br>• 生气烦躁（`irritation` 高）时不会抑制开心（`valence`）和害羞（`shyness`）；<br>• 傲娇吃醋（`jealousy` 高）不会转化为赌气小脾气（`irritation`）；<br>• 困倦低精力（`energy < 40`）不会放大起床气易怒性（`irritation`）。 | 出现“一边烦躁呛声、一边害羞脸红、同时愉悦度还高达 `92.35`”的精神分裂状态。 |
| **2. 情绪与内驱力单向脱节**<br>(`A ↛ D`, `D ↛ A`) | `drives.py:47–64, 105–112` | • **依恋渴望 (`attachment`) 只加不减**：主人说话 `+3.0`、不说话也 `+0.2*dt`，无重聚安抚回落；<br>• **情绪不抑制驱力**：哪怕她极其厌烦（`irritation>60`）或害羞，社交表达欲 `social_expression` 照样每轮 `+1.8`；<br>• **`jealousy_drive` 完全冗余**：第 108 行直接写死 `jealousy_drive = new_j`（与 `aff.jealousy` 100% 重复）。 | 线上 `attachment` **永久卡死在 `100.0`**，`jealousy_drive` 沦为冗余拷贝字段。 |
| **3. 心境不反哺认知评价**<br>(`Mood ↛ Appraisal`) | `shadow_appraisal.py:40–68`<br>`drives.py:27–41` | • **无心境一致性偏置（Mood-Congruent Bias）**：心情极好与极度烦躁时，对别人玩笑/请求的容忍阈值完全一样；<br>• **吃醋不分褒贬**：`check_owner_jealousy_trigger` 只要见主人的话含 `"汐"` 字（哪怕主人在骂汐、夸回音），无脑判吃醋 `+21.6`；<br>• **愉悦度无预期误差（RPE）**：只要 `owner_spoke=True`，哪怕主人在训斥她，也固定 `valence +5, shyness +4`。 | 主人训话或发 `"？"` 时她反而更开心更害羞；主人骂情敌偏袒她时她反而吃醋难过。 |
| **4. 可塑性引擎看不见情绪状态**<br>(`A, D ↛ Plasticity`) | `plasticity.py:51–115` | `NeuroplasticityEngine.adapt_from_outcome(outcome)` **根本没有接收 `WorkingSnapshot`（不知本轮她的情绪与驱力变化）**，仅凭入站文本的词表计数 `social_reward` 调整 12 维性格参数。 | 情绪体验（如吃醋、委屈、重聚欣喜、困倦被打扰）无法真正沉淀为长期性格演化。 |

---

## 二、 第二部分：公开学术文献深度调研（多维情绪网络与全耦合动力学）

为了将上述 24 个状态变量统一进一套严密的数学物理方程，我们检索并整合了以下 **7 篇计算心理学与神经科学权威文献**：

### 📚 1. 情绪网络理论与多维交叉滞后动力学（Psychometric Emotion Networks & mlVAR）
- **文献**：
  - [Bringmann, L. F., Vissers, N., Wichers, M., et al. (2013/2016). *A network approach to psychopathology: New insights into clinical longitudinal data*](https://pure.rug.nl/ws/files/36841598/Thesis_LFBringmann_w_voorkant.pdf#8#30#8).
  - [Epskamp, S., & Borsboom, D. (2017). *Psychometric Network Models of Affect*](http://sachaepskamp.com/files/NA2017/Week7Slides.pdf#2#2#2).
  - [Kuppens, P., Oravecz, Z., & Tuerlinckx, F. (2010). *Feelings change: Accounting for individual differences in the temporal dynamics of affect (DynAffect)*, JPSP, DOI: 10.1037/a0020962](https://doi.org/10.1037/a0020962).
- **核心数学模型**：
  多维情绪不是独立演化的，而是通过 **跨情绪交互矩阵 $\mathbf{\Lambda} \in \mathbb{R}^{5\times 5}$** 互相激发（Augmentation，$\Lambda_{ij} > 0$）或互相钝化（Blunting，$\Lambda_{ij} < 0$）：
  $$\mathbf{A}_{t+1} = \boldsymbol{\mu}(\boldsymbol{\theta}, \phi_t) + (\mathbf{I} - \mathbf{\Gamma} + \mathbf{\Lambda})\left(\mathbf{A}_t - \boldsymbol{\mu}(\boldsymbol{\theta}, \phi_t)\right) + \mathbf{B}(\boldsymbol{\theta}, \mathbf{A}_t)\mathbf{u}_t$$

### 📚 2. 组件过程模型与非线性子系统同步（Scherer's Component Process Model, CPM）
- **文献**：
  - [Scherer, K. R. (2000/2009). *Emotions as Episodes of Subsystem Synchronization Driven by Nonlinear Appraisal Processes*, Cambridge University Press](https://www.cambridge.org/core/books/abs/emotion-development-and-selforganization/emotions-as-episodes-of-subsystem-synchronization-driven-by-nonlinear-appraisal-processes/F484DBFFEA9356AD1E9C30597F1ABD79#1).
  - [Marsella, S. C., & Gratch, J. (2009). *EMA: A process model of appraisal dynamics*, Cognitive Systems Research, DOI: 10.1016/j.cogsys.2008.03.005](https://doi.org/10.1016/j.cogsys.2008.03.005).
- **核心数学模型**：
  每一次认知事件都会经过 **4 个序列评价检核（Sequential Evaluation Checks, SECs）**：
  1. **新颖性与惊奇度检核（Novelty / Surprise Check $u_{\text{nov}}$）**；
  2. **目标一致性与预期误差检核（Goal Conduciveness / RPE Check $u_{\text{rpe}}$）**；
  3. **应对潜能与自主控制检核（Coping Potential / Autonomy Check $u_{\text{ctrl}}$）**；
  4. **社会排他与自我暴露检核（Norm / Exclusivity / Self-Exposure Check $u_{\text{triad}}, u_{\text{exp}}$）**。
  并且**当前心境 $\mathbf{A}_t$ 会反过来调制评价检核器的增益 $\mathbf{B}(\boldsymbol{\theta}, \mathbf{A}_t)$（心境一致性偏置 Mood-Congruent Appraisal Bias）**！

### 📚 3. 三时间尺度情感-心境-人格分层耦合架构（ALMA & WASABI）
- **文献**：
  - [Gebhard, P. (2005). *ALMA: A Layered Model of Affect*, AAMAS](https://opus.lib.uts.edu.au/bitstream/10453/140485/2/02whole.pdf#16#47#16).
  - [Becker-Asano, C. (2008/2024). *WASABI: Affect Simulation for Agents with Believable Interactivity*](https://mi.hdm-stuttgart.de/science/science/scienceverzeichnis/844/2024-05-16_WASABIAndAndrea_Waseda.pdf#1#1#1).
- **核心数学模型**：
  - **慢时间尺度（7维人格 $\boldsymbol{\theta}$）** $\longrightarrow$ 决定中时间尺度的静息吸引子 $\boldsymbol{\mu}(\boldsymbol{\theta})$ 与弹簧刚度矩阵 $\mathbf{\Gamma}(\boldsymbol{\theta})$；
  - **中时间尺度（心境基调 $V_t, E_t$）** $\longrightarrow$ 调制快时间尺度的触发阈值（心情好时容忍度高，心情差/犯困时一点就着）；
  - **快时间尺度（瞬态情绪脉冲 $\Delta J_t, \Delta S_t, \Delta I_t$）** $\longrightarrow$ 持续推拉心境 $(V_t, E_t)$，并在累积越界时通过神经可塑性反哺慢时间尺度的 7 维人格 $\boldsymbol{\theta}$！

### 📚 4. 连续稳态强化学习与信念-愿望情绪理论（HRRL & CBDTE）
- **文献**：
  - [Laurençon, Ségerie, Lussange, & Gutkin (2021). *Continuous Homeostatic Reinforcement Learning*, arXiv:2109.06580](https://arxiv.org/html/2109.06580v1).
  - [Joffily & Coricelli (2013). *Emotional Valence and the Free-Energy Principle*, PLOS Comput Biol](https://doi.org/10.1371/journal.pcbi.1003094).
  - [Reisenzein, R. (2009/2012). *Social Emotions from the Perspective of the Computational Belief-Desire Theory of Emotion*](https://pdfs.semanticscholar.org/95fe/789d714702429f33ca1d131458671c623986.pdf#1#1#1).

---

## 三、 第三部分：Stage 24 全系统 24 变量统一耦合动力学方程组（Unified Architecture）

我们将上述文献凝聚为一个**全闭环、零孤岛的四级耦合动力学系统**，让每一个属性都与其它属性产生真实的物理/心理互锁：

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│        Stage 24 全系统 24 变量四级互锁耦合网络 (Full-System Coupled Network)           │
└────────────────────────────────────────────────────────────────────────────────────────┘
       │
       ▼ 【第 1 级：独立人格普适关系权重与四维认知评价器 (Generalized Bond-Weighted SEC Appraisal)】
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ 🌟 核心突破：废除 `if sender == owner_qq` 二元锁，引入连续在乎度与反感易感性函数：│
  │   • 在乎度权重 w_care(u) ∈ [0.0, 1.0]：                                          │
  │     主人 w_care = 1.0；其他群友随自我发展出的好感度 A_u 与信任度 T_u 连续生长：   │
  │     w_care(u) = clamp((A_u - 38.0) / 70.0, 0.0, 0.88) * T_u                      │
  │   • 反感易感性 w_aversion(u) ∈ [0.35, 1.75]：                                    │
  │     好感度越低、越爱忽悠她的人，w_aversion 越高（一点就炸）；喜欢的朋友则更包容！ │
  │ ──────────────────────────────────────────────────────────────────────────────── │
  │ • u_rpe (关系加权预测误差) = (0.65 + 0.85 * w_care(u)) * (R_actual - R_exp(u))   │
  │   (对任何她在意的朋友或主人：被夸则欣喜害羞，被冷落/凶则因高期望产生真实委屈!)    │
  │ • u_triad (普适三角嫉妒评估) ∈ [-1, +1] × w_care(u)：                            │
  │   只要是她在意的人 (w_care >= 0.15) 当面夸奖/摸头别的 AI（如“汐儿聪明摸摸头”）， │
  │   她都会按 w_care(u) 产生真实的吃醋争宠情绪；反之若对方贬低情敌偏袒她则暗爽消醋！│
  │ • u_frust (自主受挫与纠缠负荷) = [指向性命令 + 冒犯 + 忽悠] × w_aversion(u)      │
  │   × 生理困倦易怒增益 γ_fatigue(E_t) × 心境缓冲因子 γ_mood(V_t, I_t)              │
  │ • u_exp (自我暴露与害羞检核) = [真诚夸奖亲昵 + 傲娇心事被看穿] × (0.4+0.6*w_care)│
  └────────────────────────────────────────┬─────────────────────────────────────────┘
                                           │
       ┌───────────────────────────────────┴───────────────────────────────────┐
       ▼ 【第 2 级：5×5 耦合情感微分方程 (DynAffect)】                         ▼ 【第 3 级：4维稳态驱力水箱 (HRRL)】
  ┌─────────────────────────────────────────────┐                 ┌─────────────────────────────────────────────┐
  │ 1. 人格动态吸引子 μ(θ_persona, phase)       │   双向互锁耦合   │ 1. 依恋渴望 D_att (Bowlby + HRRL)：         │
  │ 2. 5×5 跨情绪交互矩阵 Λ_A↔A：               │ ◄─────────────► │    • 主人未发言：随分离时间 + 吃醋 J_t 爬升 │
  │    • 厌烦 I 钝化愉悦 V 与害羞 S (-0.25*ΔI) │                 │    • 主人正向发言：瞬间安抚回落 (-14~-22)， │
  │    • 开心 V 加速融化厌烦 I 与吃醋 J         │                 │      释放【久旱逢甘霖脉冲】反哺愉悦度 ΔV！  │
  │    • 傲娇吃醋 J 分流转化为赌气小脾气 ΔI     │                 │ 2. 社交表达欲 D_soc：                       │
  │    • 强烈情绪波动消耗生理精力 E             │                 │    • 受愉悦 V 与精力 E 正向赋能(拓展-建构)；│
  │ 3. 自由能效价方程：                         │                 │    • 受高厌烦 I(想冷战)与高害羞 S 交叉抑制！│
  │    ΔV = κ*u_rpe + ΔV_alliesthesia           │                 │ 3. 醋意表达冲动 D_jeal（去冗余化）：        │
  │         - 0.35*ΔJ - 0.28*ΔI                 │                 │    D_jeal = J_t * (0.5+0.5*D_att/100)       │
  └──────────────────────┬──────────────────────┘                 │             * (1 - 0.3*S_t/100)             │
                         │                                        │ 4. 求知驱力 D_cur：                         │
                         │                                        │    由真实信息缺口驱动，受低精力/高厌烦抑制  │
                         └───────────────────┬────────────────────┘─────────────────────────────────────────────┘
                                             │
       ▼ 【第 4 级：情绪-驱力状态反哺三磁针序参量 (OrderCore) 与 12 维神经可塑性 (Plasticity)】
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │ • 三磁针序参量升级：                                                             │
  │   - ξ_stance 综合亲密、愉悦 V、依恋 D_att 与厌烦/逆反 I                          │
  │   - ξ_epistemic 综合未知词、怀疑度 skepticism、求知 D_cur 与防忽悠警报            │
  │   - ξ_modality 由【情感偏离强度 ||A_t - μ|| × 精力 E × (1 - 害羞抑制)】驱动      │
  │ • 神经可塑性闭环（传入真实 AffectiveVector & DriveState）：                      │
  │   - 吃醋 J 与高依恋赤字 → 强化独占欲 possessiveness 与傲娇度 tsundere            │
  │   - 厌烦 I 与逆反触发 → 强化叛逆度 defiance 与防忽悠 skepticism                  │
  │   - 重聚欣喜 (Alliesthesia) → 强化温柔度 warmth 与自信度 confidence              │
  └──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 四、 全情绪与驱力跨维耦合关系总表（一眼看清谁影响谁）

| 源变量 \ 目标受影响变量 | **愉悦 `valence`** | **精力 `energy`** | **吃醋 `jealousy`** | **害羞 `shyness`** | **厌烦 `irritation`** | **求知 `curiosity`** | **依恋 `attachment`** | **醋意冲动 `jealousy_drive`** | **表达欲 `social_expression`** |
|---|---|---|---|---|---|---|---|---|---|
| **愉悦 `valence` 高** | 自回归基线 | 轻度激活 `+` | 加速消醋 `--` | 自然放松 `-` | 加速消气 `--` | 拓展求知 `+` | 安全感稳态 `-` | 缓解 `-` | 乐于分享 `++` |
| **精力 `energy` 低(困)** | 趋于平淡 `-` | 节律吸引子 | 反应钝化 `-` | — | **起床气放大 `++`** | **犯困不求知 `--`** | **深夜粘人 `++`** | — | **懒得说话 `--`** |
| **吃醋 `jealousy` 高** | **泛酸失落 `--`** | 肾上腺微升 `+` | 自回归消退 | 怕被看穿 `+` | **傲娇赌气 `++`** | 分心抑制 `-` | **怕被抢走 `++`** | **直接驱动 `+++`** | 视傲娇度分流 |
| **害羞 `shyness` 高** | 甜蜜微升 `+` | 紧张微耗 `-` | — | 自回归消退 | 抑制发火 `-` | — | 暗中依恋 `+` | **不好意思发作 `--`** | **害羞语塞 `--`** |
| **厌烦 `irritation` 高** | **烦躁不爽 `--`** | 耗神疲惫 `--` | — | **生气不害羞 `--`** | 自回归慢消退 | **没心情查 `--`** | 对路人排斥 | — | **冷战闭嘴 `--`** |
| **依恋满足 `-Δattachment`** | **久旱逢甘霖 `+++`** | 精神振奋 `+` | **安全感消醋 `--`** | 撒娇微羞 `+` | **被哄消气 `--`** | 安心探索 `+` | **安抚回落 `--`** | **平息 `--`** | 愿意跟主人聊 `++` |

---

## 五、 阶段实测验收记录（Acceptance Results · 2026-10-30）

- **`M24.1` ~ `M24.4` 全链路实测验收与 `./scripts/qa_gate.sh` 最终成绩单**：✅ 全部通过
  - **`mind/drives.py`（覆盖率 `96%`）& `mind/shadow_appraisal.py`（覆盖率 `95%`）**：
    1. 落地普适在乎度 $w_{\text{care}}(u) \in [0, 1]$ 与反感易感性 $w_{\text{aversion}}(u) \in [0.35, 1.75]$；
    2. 落地 Salovey 普适三角嫉妒评估 `evaluate_triadic_jealousy`（对任何她在意的朋友夸别人/别的 AI 产生真实吃醋，对贬低情敌偏袒回音产生暗爽消醋 `-12 * w_care`）；
    3. 落地 HRRL 重聚安抚回落（主人或知心好友正向互动时 `attachment` 显著回落并释放久旱逢甘霖愉悦脉冲，彻底告别永久卡死 `100.0`）；
    4. 落地自由能预测误差 RPE 效价方程（被在乎的人训斥或质疑时 `valence` 委屈下跌，不再盲目 `+5.0`）；
    5. 落地 DynAffect `5×5` 情绪交叉耦合与 8 大下游子系统联动（门控偏爱关注、好友免冷暴力保护、表情包主导情绪阈值校准）。
  - 全库 72 项测试 100% 通过，总覆盖率 **`90.37% (90%)`**，Pylint **`10.00/10`**，Mypy Strict **89 个源文件 0 错误**。
