# 真人感风格监控（不再真人测试）

真人评测已暂停。之后只看确定性指标，不让你再标。

## 指标

| 指标 | 含义 |
|---|---|
| avg_len | 平均回复长度（字符） |
| long_rate | >40 字比例 |
| explain_rate | 出现“因为/所以/不能/隐私/规则/需要/建议/可以/但是”的比例 |
| roleplay_rate | 出现括号动作 `（…）` 的比例 |
| multi_question_rate | 一条回复里多个问号的比例 |

## 基线（2026-11-01 当前）

7 天 1000 条 self 消息：

```
avg_len 41.6
long_rate 0.336
explain_rate 0.033
roleplay_rate 0.101
multi_question_rate 0.004
```

最近 24 小时 200–222 条：

```
avg_len 28.3
long_rate 0.140
explain_rate 0.027
roleplay_rate 0.032
multi_question_rate 0.000
```

注意：这是趋势基线，不是因果；最近 24h 明显更短，但 7 天整体仍偏长。

## 运行

```bash
python scripts/style_monitor.py
```

输出 `reports/style-monitor.json`。

控制台只读接口：

```text
GET /api/mind/style-health
```

## 目标

- 长度和 >40 字比例下降；
- explain_rate 下降；
- roleplay_rate 下降；
- 隐私/边界不退化（仍由 60 条记忆评测与拒绝日志保证）。

## 边界

- 不追求“越短越好”；安慰/技术说明需要展开；
- 不再用 LLM judge 绝对分做门禁；
- 不再新增真人标注。
