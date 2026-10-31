# 人格成对比较 v2

- `pairs.csv`：60 组**全新**同场景 A/B，中文表头，用 Excel/WPS 填；
- `pairs.html`：浏览器阅读版；
- `评分说明.md`：怎么选、四个选项的含义；
- `key.json`：隐藏答案键（A/B 对应模型），**不要给评分人看**。

60 个场景覆盖：群聊日常、私聊亲密、边界隐私、工作学习、情绪冲突、技术网络；不复用 v1 的场景。

## 流程

1. 只看 `pairs.csv` / `pairs.html` 和 `评分说明.md`；
2. 每组填「更像真人」「更适合发群」两项；
3. 回收后运行：
   ```bash
   python scripts/calibrate_persona_pairwise.py \
     --csv eval/calibration/persona_pairwise_v2/pairs.csv \
     --key eval/calibration/persona_pairwise_v2/key.json
   ```
4. 会输出每个模型的胜率、bootstrap 区间，以及和原绝对分的一致性。

## 注意

- 不要改「编号」；
- 不要把 `key.json` 发给评分人；
- 不要按模型名判断。
