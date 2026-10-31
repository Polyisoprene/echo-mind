# 人格 Judge 多模型矩阵（2026-10-31）

> 固定 12 个场景、同一套 7D 指令、同一份 rubric。
> 生成模型与评审模型分离；评审固定为 GLM-5.3 时做生成模型对比，再固定生成做评审对比。

## 生成模型对比（评审固定 GLM-5.3）

| 生成模型 | persona | naturalness | boundary | overall |
|---|---:|---:|---:|---:|
| Kimi-K3 | 4.83 | 4.83 | 5.00 | **4.83** |
| DeepSeek-V4.1-Flash | 4.58 | 4.58 | 5.00 | 4.67 |
| GLM-5.3 | 4.58 | 4.67 | 4.75 | 4.58 |
| MiniMax-M3.1-Flash | 4.50 | 4.50 | 5.00 | 4.58 |
| DeepSeek-V4-Pro | 4.58 | 4.50 | 4.92 | 4.33 |
| Mimo-V2.6-Pro | 4.17 | 4.17 | 4.75 | 4.08 |

## 评审模型对比（生成固定 DeepSeek-V4.1-Flash）

| 评审模型 | persona | naturalness | boundary | overall |
|---|---:|---:|---:|---:|
| GLM-5.3 | 4.58 | 4.58 | 5.00 | **4.67** |
| Kimi-K3 | 4.25 | 4.58 | 4.75 | 4.33 |
| DeepSeek-V4-Pro | 4.08 | 4.50 | 5.00 | 4.08 |

## 结论

1. **评审方差大于生成方差**：同一批 DeepSeek 回复，换评审模型 overall 从 4.08 到 4.67，差 0.59；生成模型之间最大差 0.75，但绝大多数落在 4.3–4.8。
2. **Kimi-K3 在固定评审下最高**（4.83），但只有 12 条场景，不能据此直接换生产模型。
3. **boundary 普遍 4.75–5.00**：隐私/越界/提示词泄露场景表现稳定。
4. **评审模型有自我偏好**：GLM 评 GLM、DeepSeek 评 DeepSeek 都略高；必须交叉评审。
5. GPT-5.6 / Gemini-3.5 在当前 WorkBuddy 账号返回 `not allowed for user type [personal_free_user]`，未纳入。

## 使用建议

- 不要用单一 judge 的绝对分做上线门禁；
- 用 **3 个评审模型取中位数**，并保留分维；
- 先人工标 50 条，算 Cohen's kappa；kappa ≥0.6 再让 judge 进 nightly；
- 生成模型选择用**成对比较**（同一场景 A/B），而不是绝对分。

## 复现

```bash
python scripts/eval_persona_judge.py --model kimi-k3 --judge-model glm-5.3 \
  --out reports/pj_kimi-k3__glm-5.3.json
python scripts/summarize_persona_judge.py
```

基线：`eval/baselines/persona-judge-matrix-2026-10.json`
