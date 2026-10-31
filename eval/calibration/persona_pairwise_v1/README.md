# 人格成对比较 v1

- `pairs.csv`：30 组同场景 A/B，中文表头，用 Excel/WPS 填；
- `pairs.html`：浏览器阅读版；
- `评分说明.md`：怎么选、四个选项的含义；
- `key.json`：隐藏的答案键（A/B 对应的模型和原人工分），**不要给评分人看**。

## 流程

1. 只看 `pairs.csv` / `pairs.html` 和 `评分说明.md`；
2. 每组填「更像真人」「更适合发群」两项；
3. 回收后运行 `python scripts/calibrate_persona_pairwise.py`；
4. 会输出每个模型的胜率，以及你的选择和原绝对分是否一致。

## 注意

- 不要改「编号」；
- 不要把 `key.json` 发给评分人；
- 不要按模型名判断。
