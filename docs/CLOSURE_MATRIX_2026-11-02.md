# EchoMind 闭环矩阵（2026-11-02）

> 目的：把“已完成、已验证、被外部资源阻塞”的项集中列出，作为当前收口依据。
> 当前门禁：396 passed / 93%，fusion 70/70。

## 1. 已完成并有工程数字

| 项 | 结果 | 证据 |
|---|---|---|
| Response attribution | 1,654 outcomes；1,333 mention / 321 temporal | shadow 表 + 脚本 |
| LongMemEval 500 retrieval | recall@5 0.954 / MRR 0.892 | `eval/baselines/longmemeval-500-*` |
| LongMemEval 500 QA | 417/500 = 83.4% | `longmemeval-qa-500-final` |
| CoT 500 | 431/500 = 86.2% | `longmemeval-qa-500-cot` |
| top10 500 | 430/500 = 86.0% | `longmemeval-qa-500-top10` |
| GroupMemBench metadata | 48.6 / 52.6 / 48.3 / 57.8 | 四域 JSON |
| GroupMemBench KU change-only | 0.688 / 0.833 / 0.765 / 0.727 | 四域 KU JSON |
| B4 claims read path | provenance/privacy，默认 off | 测试 |
| B5 disclosure knowledge | told_by_me/hinted | 测试 |
| B6 fact validity | valid_to_ms | 测试 |
| G1 candidate auto-promotion | dry-run 默认，生产 pending=0 | 测试/脚本 |
| G2 narrative projection | 只读，A/B 否决 prompt | baseline |
| 融合条件化 | confidence/lock 常数、recency/order cue | 500 结果 |

## 2. 明确被阻塞

| 项 | 阻塞 | 不做的原因 |
|---|---|---|
| CharacterEval 官方分 | BaichuanCharRM 13B，RX6800 16GB 不足 | 不能用 CPU/伪 judge 代替 |
| live 自动 supersede | claims.subject 是人名，value 不是函数槽 | 7/7 候选都是不同事实 |
| slot_key 回填 | 缺产品命名规则 | 不能自动从 value 猜 |
| live metadata-aware retrieval | 需隐私/70/500 验证 | benchmark metadata 不能直接搬 |
| dormant 策略 | 缺 sourced 时间窗 | 不拍天数 |
| stance 校准 | 无对照标签 | 90 组是模型 A/B |
| G3/G5/G6/G7/G8 | 需长期数据/外部集 | 长数据依赖 |
| A8–A10/B1–B3/B7/C2–C4/D3–D4 | 需外部集/资源 | 数据依赖 |

## 3. 当前结论

- 所有**不需要新产品决策或新硬件**的代码/评测项，已经收敛到可验证状态；
- 剩余项不是“再写一个补丁”能解决的；
- 继续改 live 检索/prompt/claims 写入会引入无证据风险；
- 下一步应做产品决策（slot key 命名）或补硬件（CharacterRM）。

## 4. 复核入口

- Stage 42 计划：`docs/plans/STAGE_42_CAPABILITY_COMPLETION_PLAN.md`
- 当前状态：`docs/CURRENT_STATE_2026-11-01.md`
- 外部评测：`docs/GROUPMEMBENCH_MODEL.md`、`docs/LONGMEMEVAL_QA_MODEL.md`
- 更新检测：`docs/LIVE_UPDATE_DETECTION_MODEL.md`
- CharacterEval：`docs/CHARACTEREVAL_MODEL.md`
