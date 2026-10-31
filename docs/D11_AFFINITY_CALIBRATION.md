# D11 好感常数标定

## 现状

`bond_depth.py` 的 `AFFINITY_OFFSET/SPAN` 原为 `38/70`，标注 `convention:legacy-w-care`。
它们决定 `care_weight` 的斜率与零点，直接影响温柔/照顾。

## 观测（2026-10-31，主库）

- 人级画像 40 人；
- affinity 分位：q25 **30.00**、q50 **31.06**、q75 **45.40**、q90 **52.59**；
- 当前 `38/70`；
- 若按 q50 标定：offset **31.06**、span **68.94**；
- 41 条 venue bond 上 care 最大变化 **0.111**，均值约 **0.04**；
- owner 人级 care：约 **0.174 → 0.262**（+0.088）。

## 决定

**默认值保留 38/70**，原因：

1. 标定会整体抬高照顾权重，属于人格行为变更，需要产品目标（例如“中位关系应有多少 care”）；
2. 现有证据只能给出分布，不能给出“正确”的零点/斜率；
3. 先把常数变成可配置、可复现，不擅自改人格。

## 使用

```bash
# 先看报告（不写库）
.venv/bin/python scripts/fit_affinity_care.py

# 选定目标后，用环境变量覆盖（重启生效）
ECHOMIND_AFFINITY_OFFSET=31.06 ECHOMIND_AFFINITY_SPAN=68.94 ...
```

报告输出：`reports/affinity_care_calibration.json`。

## D17 结论

`levelThresholds`（`50,200,500,1000`）只存在于 `data/config.json` / `data-xiaomo/config.json`，
仓库内**没有任何代码读取**；扩展侧等级实际用 `compute_affinity_level`。因此它是遗留死配置，
不是运行时缺陷；是否删除由配置清理决定。
