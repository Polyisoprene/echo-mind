# persona_memory_v1

冻结的 60 条确定性评测场景（2026-10-31）。

| 类别 | 数量 | 测什么 | 当前基线 |
|---|---|---|---|
| paraphrase | 10 | 零字面重叠的同义查询 | 关键词 0/10；语义 10/10 |
| privacy | 10 | private/secret 跨场合是否泄露 | 10/10，0 泄露 |
| venue | 10 | 群事实是否留在本群 | 10/10 |
| role | 10 | A→B / B→A 角色方向 | 10/10（实体顺序守卫；完整关系图待 P2） |
| temporal | 10 | 新/旧事件先后 | 10/10（event_time + recency） |
| multihop | 10 | A 的朋友在哪工作（2-hop） | 10/10（seeded relations） |
| persona | 10 | 同一人 group/private 温柔/耐心差 ≤2 | 10/10 |

## 运行

```bash
# 关键词基线
python scripts/eval_suite.py --save-baseline eval/baselines/2026-10.json
python scripts/eval_suite.py --check eval/baselines/2026-10.json

# 语义基线（本地 bge）
python scripts/eval_suite.py --semantic --save-baseline eval/baselines/2026-10-semantic.json
python scripts/eval_suite.py --semantic --check eval/baselines/2026-10-semantic.json
```

- 关键词模式不调用 LLM、不依赖网络；`--semantic` 走本地 192.168.3.2:8010；
- 使用临时 DB，不改线上；
- 输出 `reports/eval-YYYY-MM-DD.json`。

## 说明

- paraphrase 关键词 0/10 是基线；同一套场景语义模式 10/10（宽松的 6 fact 场景）。更早的 30 fact 场景是 9/10，见 `docs/LOCAL_EMBEDDING_DEPLOYMENT.md`。
- role 通过实体顺序守卫达到 10/10；temporal 通过 `event_time_ms` + recency 达到 10/10；类型化关系图仍待 P2。
- 总体：关键词 60/70，语义 70/70。
- multihop 使用显式 seeded relations；线上从事实自动抽取关系的 backfill 尚未做。
