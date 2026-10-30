# EchoMind 红绿交付与 A/B 双线契约（Engineering Delivery Contract v1.0）
**（Red-Green Delivery & A/B Lane Contract — 强制性工程契约，与 `ARCHITECTURE_CONTRACTS.md` 同级效力）**

> **效力声明**：本文档规定的 **RGR（Red-Green-Refactor）** 与 **AB（Lane Isolation）** 条款，是对 `ARCHITECTURE_CONTRACTS.md` 第六节「七道质量门禁」的**流程性补充**。任何修复类改动若未满足本文档，视为未完成，不得合入 `main`（B 线）。

---

## 一、 术语

| 术语 | 定义 |
|---|---|
| **A 线** | 修复与回放评估车道（worktree + `lane/*` 分支 + 只读快照库 + 录制探针夹具） |
| **B 线** | 生产车道（`main` 分支 + `:3310` 服务 + `data/echomind.db`） |
| **红（Red）** | 一条**因目标缺陷而失败**的测试及其失败输出证据 |
| **绿（Green）** | 同一条测试通过，且全 7 道门禁 Exit 0 |
| **准出（Promotion）** | A 线全绿并通过回放判据后，合入 B 线的动作 |

---

## 二、 红绿交付条款（RGR）

### RGR-01（先红后绿）
任何**行为变更**必须先提交一条失败测试；未提供红证据的修复提交一律拒收。
- 红证据须包含：命令、失败断言原文（含实际值与期望值）、commit 短哈希。
- 纯文档/纯重构（行为不变）可豁免，但须在提交信息标注 `[no-behavior]`。

### RGR-02（红得正确）
红色失败必须**来自目标断言**。以下不算红：语法错误、缺 import、fixture 报错、网络/环境错误。
- 自检：红色 traceback 的行号必须落在目标 `assert` 上。

### RGR-03（最小实现）
单次提交只服务**一个** finding（如 `F1`）。禁止在同一提交里顺手重构无关模块。
- 若确需重构以腾出行数预算（`SRP-01` 300 行上限），重构单独提交并标注 `[refactor-only]`，且必须**单独跑绿**。

### RGR-04（测试不可回改）
转绿后的契约测试受保护：不得为通过而放宽断言。放宽等同于**新增一条红**，须重新走 RGR-01，并在证据表登记「旧断言 → 新断言 + 理由」。

### RGR-05（命名与提交前缀）
- 测试函数：`test_rg_f<N>_<slug>`（例：`test_rg_f1_production_reward_not_constant`）；
- 提交信息：`rg(F<N>): <一句话>`；
- 回放脚本：`scripts/replay_eval.py`；报告：`reports/replay_<ts>.json`。

### RGR-06（生产路径同构）
契约测试必须走**生产同一条调用路径**。
- 反例（当前 F11 的教训）：测试里显式构造 `SubconsciousChordResult` 传给被测函数，而生产调用点根本不传 → 测试全绿但生产失效。
- 判据：测试应调用 `CognitiveCoreFacade.evaluate_incoming` / `on_turn_completed` / `AgentSessionRunner.run_turn` 这一级入口，而非绕过它们直接调纯函数（纯函数另有独立单测算术正确性）。

### RGR-07（回放确定性）
A 线回放必须满足：冻结时钟（`now_ms` 注入）、固定随机种子（`random.seed(0)` / `hypothesis` 关闭自由探索）、探针走**录制夹具**（`ChordFixtureProbe`，不含真实 LLM 调用）。同一输入两次回放，报告 JSON 必须逐字节一致（除 `ts`）。

### RGR-08（双证据入档）
每次红绿完成后，必须在 `docs/plans/STAGE_28_*.md` 第 4.3 表回填：Finding / 测试 ID / 红证据 / 绿证据（含门禁尾行）/ 提交短哈希。

### RGR-09（门禁全绿才可绿）
「绿」的定义不是单测通过，而是：目标测试通过 **且** `./scripts/qa_gate.sh` 7 道门禁全部 Exit 0（Ruff / Radon / Pylint / Mypy / AST 边界 / Pytest+Coverage / Hypothesis）。

### RGR-10（禁止静默降级）
若修复引入超时、降级、开关，必须在同一条测试中断言**降级路径的行为**（例：探针 1.2 s 超时后 `chord is None` 且回合仍可完成），不得只测 happy path。

---

## 三、 A/B 双线隔离条款（AB）

### AB-01（写隔离）
A 线禁止写 `data/echomind.db` 与 `data/config.json`；回放只读 `data/replay-snapshot.db`，写入落 `data/a-sandbox.db`。

### AB-02（探针隔离）
A 线默认注入 `ChordFixtureProbe`（录制 JSON）。仅当显式 `--live-llm` 且 Token 预算 `> 0` 时允许真实调用，预算耗尽立即中止回放并标记报告 `partial: true`。

### AB-03（分支隔离）
B 线在 A 线准出前不接受修复提交。A 线分支命名 `lane/a-stage<N>`；B 线为 `main`。

### AB-04（准出通道）
A→B 只允许 `git cherry-pick <green-commits>` 或 fast-forward merge；禁止把 A 线的实验性提交（含 `[refactor-only]` 未跑绿者）带入 `main`。

### AB-05（回滚闸）
合入 B 线前必须打 tag（`pre-stage<N>`）；合入后 24 h 观察期内出现以下任一情况即 `git revert`：
1. 探针调用/回合 > 1.2；
2. 新增异常日志 ≥ 1 类；
3. 挑衅型群友信任度未出现下降趋势；
4. `qa_gate.sh` 在 B 线失败。

### AB-06（服务隔离）
A 线需要联调时使用 `:3311`（`ECHOMIND_PORT=3311 ./scripts/service.sh restart`），禁止占用 `:3310`。B 线服务仅由准出流程重启。

### AB-07（数据回溯）
回放快照必须由 `scripts/snapshot_db.sh`（或等价命令）从 B 线库**只读复制**生成，并在报告里记录快照哈希，保证可追溯。

### AB-08（契约守卫）
`tests/architecture/test_delivery_contract.py` 负责机器校验：
- 每个 `F<N>` 在计划文档 4.3 表里都有非 `📋` 的红/绿证据与 commit；
- 提交信息前缀符合 `rg(F<N>):` 或带 `[no-behavior]` / `[refactor-only]`；
- `reports/` 下最新回放报告满足第二节判据阈值。

> 该守卫测试自身也遵循 RGR：先以「表里有 `📋`」为红，施工完成后转绿。

---

## 四、 一页速查（执行时贴在手边）

```bash
# A 线准备
git worktree add ../echo-mind-a -b lane/a-stage28
cd ../echo-mind-a && uv sync
sqlite3 ../echo-mind/data/echomind.db ".backup data/replay-snapshot.db"   # 只读快照

# 每个 finding 的红绿循环
uv run pytest -k test_rg_f1 -q            # 期望 FAIL（贴入证据表）
# ... 最小实现 ...
uv run pytest -k test_rg_f1 -q            # 期望 PASS
uv run pytest -k "stage2 or stage3 or stage4" -q
./scripts/qa_gate.sh                      # 7 道门禁全绿
git commit -m "rg(F1): derive social_reward from cached 6D chord"

# 回放评估（确定性）
uv run python scripts/replay_eval.py --db data/replay-snapshot.db \
    --fixture tests/fixtures/chords_stage28.json --turns 200 --out reports/

# 准出
git tag pre-stage28 && git cherry-pick <green-commits>
ECHOMIND_PORT=3310 ./scripts/service.sh restart
```

---

## 八、 追加纪律（Stage 30 复盘，AB-09 ~ AB-11）

| 编号 | 纪律 | 触发场景 |
|---|---|---|
| **AB-09** | 测试禁止写生产数据：任何测试若需要配置文件，必须使用 `tmp_path`；`tests/conftest.py` 会在会话结束比对 `data/config.json` 字节，被改即失败 | 曾出现 `qa_gate` 把生产人设改成「设定」 |
| **AB-10** | 准出必须走 `scripts/promote.sh`（按 patch-id 过滤，避免重复应用已合入提交）；禁止手工 cherry-pick | 曾出现空提交卡死 cherry-pick |
| **AB-11** | **未经确认不重启生产**；每完成一个子阶段不等于"可以上线"，合并节奏由负责人决定 | Stage 30 曾逐子阶段上线并反复重启 |
