# GroupMemBench asking-user 消融（2026-11-01）

> 背景：knowledge_update 诊断中，多条失败不是“没检索到”，而是模型坚持“User_X 没说”，而 gold 是群里另一角色的决定。
> 变量：去掉 `Asking user` 行，其余官方协议不变。

## 1. 观察

失败样例：

- “The retrieved passages do not contain a statement from User_9…”
- “User_5’s message only discusses… the stamping approach is from User_13…”

gold 恰恰是团队决定，不一定由 asking_user 说出。

## 2. 对照

固定：

- metadata-aware BM25；
- top10；
- 官方 agent/judge prompt；
- 同一 LLM。

变量：

```text
official: query = asking_user_id + question，prompt 含 Asking user
no-asker: query = question，prompt 去掉 Asking user
```

## 3. 判据

- Finance knowledge_update 是否提升；
- 不改变检索/索引；
- 若提升，再考虑 full Finance；
- 不接 live。

## 4. 边界

- GroupMemBench 的 asking_user 本来是 ToM 设计；去掉它是 benchmark 适配，不是通用结论；
- 只做消融，不宣称官方指标。

## 5. 结果（2026-11-01）

Finance knowledge_update：

| 条件 | n | accuracy |
|---|---:|---:|
| 官方 asking_user | 32 | **0.469** |
| 去掉 asking_user | 32 | 0.438 |

结论：

- 去掉 asker 反而下降；
- 失败不能简单归因于 asker；
- 不采用；
- 需要继续做证据级诊断，而不是改 prompt 标签。
