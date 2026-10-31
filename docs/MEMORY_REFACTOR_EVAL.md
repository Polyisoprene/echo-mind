# 记忆模块验收基线（D19）

## 运行

```bash
.venv/bin/python -m pytest tests/integration/test_memory_eval.py -q
```

## 检查项

| 指标 | 通过标准 | 证据 |
|---|---|---|
| private 越权召回 | 0 | `L 的病` 只在 `group:1` 与 `private:L` 出现，`group:2`/`private:M` 不含 |
| secret 泄露 | 0 | `暗号` 在四个场合均不出现 |
| 场合隔离 | 0 | `群规` 只在 `group:1` |
| global 可见 | 全部 | `公开梗` 在四个场合都出现 |
| 来源覆盖 | 100% | 每条事实 `source_venue_id` 非空 |
| 门拒绝日志 | 1 条 | 无 owner 时 `keep/owner_absent` |
| 跨场合一致 | 温柔/耐心差 <0.01 | 同一个人 group/private 的 `persona_warmth`、`persona_defiance` 相同 |
| 俏皮归场合 | 群 > 私聊 2 分以上 | `persona_playfulness` |

## 限制

- 合成数据，不是 GroupMemBench 或人工盲评；
- 未覆盖多人同时在场、来源引用措辞、生成后归因；
- secret 授权路径由 `test_disclosure_choice` / `test_disclosure_log` 单独覆盖。

## 结论

这是**内部可复现基线**，用于防止后续改动回退授权/一致/来源三项；外部评测仍是 D19 的剩余部分。
