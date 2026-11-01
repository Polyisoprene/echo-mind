# Response Attribution 模型（P0，2026-11-01）

> 目的：知道她说完一句话后，谁回应、是否针对她、间隔多久。
> 状态：**shadow only，不接 trait/ranker/prompt。**

---

## 1. 数据

来源：`chat_messages`

```text
chat_key, ts, sender_id, sender_name, is_self, text
```

当前规模：

- 8,326 条消息；
- 1,709 条 self；
- 无 `reply_to`/`mid` 元数据可用（mid 为空，text 无 CQ reply）。

所以 tier A（quote/reply 元数据）当前不可用；只实现 tier B/C。

## 2. 归因层级

| tier | 条件 | 是否进 evidence |
|---|---|---|
| A | 原始 reply/quote id 指向她 | 未来可用；当前无数据 |
| B | 后续他人消息明确包含她的名字/别名（回音、尾尾） | 可作候选，不自动进 evidence |
| C | 仅时间相邻 | **绝不进 evidence**，只统计 |

本机数据：

```text
1,709 self 消息
30 min 内任意他人消息：96.8%
30 min 内明确点名：78.0%
直接回应延迟：median 208.9s, p90 1122.2s, p95 1371.9s
```

窗口取 **30 min**：覆盖直接回应 p95（22.9 min），并留出余量；不是拍脑袋的 5 min。

## 3. 输出模型

```text
InteractionOutcome
  self_message_id
  chat_key
  self_ts
  response_message_id
  response_ts
  delay_ms
  attribution: "mention" | "temporal"
  sender_id / sender_name
  response_text
```

规则：

- 每条 self 消息最多一条 outcome：优先取**第一条明确点名**的回应；没有点名才取**第一条时间相邻**回应；
- 超过 30 min 无回复 → 也写一条 `no_response`？  
  第一版不写空 outcome，只写有回复的；覆盖率单独统计。
- 同一 self 的重复运行幂等（唯一键）。

## 4. 存储

```sql
CREATE TABLE IF NOT EXISTS interaction_outcomes (
  self_message_id INTEGER NOT NULL,
  response_message_id INTEGER NOT NULL,
  chat_key TEXT NOT NULL,
  self_ts INTEGER NOT NULL,
  response_ts INTEGER NOT NULL,
  delay_ms INTEGER NOT NULL,
  attribution TEXT NOT NULL CHECK(attribution IN ('mention','temporal')),
  sender_id TEXT NOT NULL DEFAULT '',
  sender_name TEXT NOT NULL DEFAULT '',
  response_text TEXT NOT NULL DEFAULT '',
  created_ms INTEGER NOT NULL,
  PRIMARY KEY(self_message_id, response_message_id)
);
```

## 5. Shadow 原则

- 不改 prompt；
- 不改 trait evidence；
- 不改 ranker；
- 不改 social reward；
- 只落表 + 报告；
- 任何后续闭环必须另立阶段，重新评估。

## 6. 验收

- 每条自消息最多一条 outcome；
- 30 min 窗口在代码与 ledger 有来源；
- tier C 不被写成 evidence；
- 运行前后 387 tests / fusion 70/70 不变；
- 指标：
  - coverage（有回复的自消息比例）；
  - directed rate（mention 比例）；
  - delay p50/p90/p95；
  - 与人工/规则抽检的差异（不新增训练标签）。

## 7. 非目标

- 不把“任意相邻消息”当回复；
- 不把群友之间互相说话算作她的反馈；
- 不用 B 站评论做 attribution；
- 不引入社交奖励权重。


## 8. 2026-11-01 shadow 运行结果

真实主库：

```text
self messages=1709
outcomes=1654
coverage=0.968
mention=1333
temporal=321
p50=131.4s
p90=995.4s
p95=1329.1s
```

已写入 `interaction_outcomes`，不参与 trait/ranker/prompt。  
产物：`eval/baselines/response-attribution-2026-11-01.json`。
