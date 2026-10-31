# 人格人工校准 v1

- `items.csv`：50 条中文评分表，表头已写清每个维度；直接用 Excel/WPS 打开填写；
- `items.html`：浏览器里看的版本，方便对照阅读；
- `评分说明.md`：1–5 分的含义和填写方法；
- `key.json`：隐藏的答案键（模型名、judge 分数），**不要给评分人看**。

## 流程

1. 评分人只看 `items.csv` / `items.html` 和 `评分说明.md`；
2. 四项填 1–5 整数；
3. 回收后运行 `python scripts/calibrate_persona_judge.py`；
4. 看 `reports/calibration_kappa.json`：kappa ≥ 0.6 才把 judge 分数当门禁。

## 注意

- 不要把 `key.json` 发给评分人；
- 不要按模型名打分；
- 不要修改 `编号` 列，否则无法和答案键对齐。
