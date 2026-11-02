# EchoMind 闭环矩阵（2026-11-02）

> 目的：把“已完成、已验证、被外部资源阻塞”的项集中列出，作为当前收口依据。
> 当前门禁：429 passed / 93%，fusion 70/70。

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
| FTS5 shadow | 500 recall 0.942/MRR .876；RRF 0.944/.878，仍低于 .954/.892；未接 live | `memory_fts.py`、baseline |
| 本地 embedding | bge-m3 / 1050Ti / 1024 维；RSS 1.29GB，VRAM 1.24GB | `LOCAL_EMBEDDING_DEPLOYMENT.md`、probe 验证 |
| Stage 43 P0 | 跨会话访问策略、BDI 栈、HEXACO 覆盖审计（纯函数，不接 live） | `STAGE_43...PLAN.md`、3 组单测 |
| slot 功能 | 单值 QQ/性别/生日/年龄；昵称多值；group_id 不建槽 | `CLAIM_SLOT_FUNCTION_MODEL.md` |
| 远端语音（TTS） | TTS 真实合成；RVC/SVS 仅 capability | `voice-service.log`、`tts-daemon.log` |

## 2. 明确被阻塞

| 项 | 阻塞 | 不做的原因 |
|---|---|---|
| CharacterEval 官方分 | BaichuanCharRM 13B，远端 16GB / 本地 4GB 不足 | 不能用 CPU/伪 judge 代替 |
| live 自动 supersede | claims.subject 是人名，value 不是函数槽 | 7/7 候选都是不同事实；slot 数据只回填 1 条 gender |
| slot_key 回填 | 缺产品命名规则 | 不能自动从 value 猜 |
| live metadata-aware retrieval | 需隐私/70/500 验证 | benchmark metadata 不能直接搬 |
| dormant 策略 | 缺 sourced 时间窗 | 不拍天数 |
| stance 校准 | 无对照标签 | 90 组是模型 A/B |
| G3/G5/G6/G7/G8 | 需长期数据/外部集 | 长数据依赖 |
| A8–A10/B1–B3/B7/C2–C4/D3–D4 | 需外部集/资源 | 数据依赖 |

## 2.1 明确未完成但可做

| 项 | 现状 | 说明 |
|---|---|---|
| 跨会话记忆 | `get_cross_session_facts()` 已实现但未接 live；原始私聊事实仍不跨 | 承诺事件/披露模型未实现 |
| BDI 生产者 | 明确承诺句生成 intention；TTL 未校准；目标不自动解析 | 已有 `mind/commitment.py` 与测试 |
| 跨会话发送 | 真实私聊→群已验收：send_to_chat → group:813506156，message_id 1143989337 | `turn_traces` + `chat_messages` |
| RVC/SVS 真实唱歌 | 服务 capability 可用，但未跑真实样本 | 需验证显存/内存与 OOM |

## 3. 当前结论

- 大部分不需要新产品决策或新硬件的代码/评测项已收敛；
- 剩余项不是“再写一个补丁”能解决的；
- 跨会话记忆是当前最大可做缺口，需按 source/audience 分阶段落地；
- 下一步应做产品决策（slot key 命名）或补硬件（CharacterRM）。

## 4. 复核入口

- Stage 42 计划：`docs/plans/STAGE_42_CAPABILITY_COMPLETION_PLAN.md`
- 当前状态：`docs/CURRENT_STATE_2026-11-01.md`
- 外部评测：`docs/GROUPMEMBENCH_MODEL.md`、`docs/LONGMEMEVAL_QA_MODEL.md`
- 更新检测：`docs/LIVE_UPDATE_DETECTION_MODEL.md`
- CharacterEval：`docs/CHARACTEREVAL_MODEL.md`
