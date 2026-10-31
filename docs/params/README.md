# 参数与能力台账（E0）

本目录是"不拍脑门"的执行基础设施。两个台账 + 两道门禁，让每个常数与每个功能声明都可核对。

## 一、文件

| 文件 | 作用 |
|---|---|
| `ledger.json` | 每个可调常数的来源声明（`src` / `data` / `convention` / `fit_pending`） |
| `baseline.json` | 债务基线：`debt` 只允许下降，不允许上升 |
| `../capabilities.json` | 每个"已实现/部分/缺失/自相矛盾"的功能声明 |
| `../CAPABILITY_STATUS.md` | 由脚本生成的状态表，**不要手改** |

## 二、四类溯源

| class | 必填字段 | 适用 |
|---|---|---|
| `src` | `evidence.doi`、`evidence.locator`、`evidence.derivation` | 论文里能定位到页码/公式的取值 |
| `data` | `evidence.dataset_sha256`、`n`、`estimate`、`ci95`、`script` | 用自有数据拟合的参数 |
| `convention` | `evidence.rationale` | 无自由度的约定（单位换算、内存上限） |
| `fit_pending` | `issue`、`experiment`、`conservative_value` | 暂时无法判定，等实验 |

> `fit_pending` 是**合法状态**，不是免责。它必须带 issue 与实验设计，并在控制台标注"未校准"。

## 三、日常流程

```bash
# 新增或移动常数后：重新扫描并合并（保留已有注释）
python scripts/param_audit.py --write

# 检查（CI 走这条）
python scripts/param_gate.py

# 首次落地或债务已还清后：显式收紧基线
python scripts/param_gate.py --init-baseline

# 能力台账：修改 docs/capabilities.json 后重新生成状态表
python scripts/capability_gate.py
python scripts/capability_gate.py --check   # CI 用，文件过期即失败
```

## 四、规则

1. 新增常数未登记 → 门禁失败（默认落入 `unknown`，债务 +1）。
2. 修改常数但未同步改台账 → 复审拒绝。
3. `fit_pending` 条目在实验完成前，不得用于对外声明或论文结论。
4. `implemented` 的能力必须有可解析的 pytest node；测试被删 → 门禁失败。
5. 文档中的完成度以 `CAPABILITY_STATUS.md` 为准，手写完成度视为无效。

## 五、当前状态（E2 落地时）

- 常驻参数：50 条，其中 `fit_pending` 32 条（实验待做）、`convention` 18 条。
- 能力：20 条，`implemented` 5、`partial` 6、`absent` 6、`contradicted` 3。
- 债务基线：`debt = 0`（所有条目至少完成了分类与字段填写；科学债务由 issue 跟踪）。
