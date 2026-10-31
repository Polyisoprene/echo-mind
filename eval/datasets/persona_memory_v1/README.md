# persona_memory_v1

冻结的 60 条确定性评测场景（2026-10-31）。

| 类别 | 数量 | 测什么 | 当前基线 |
|---|---|---|---|
| paraphrase | 10 | 零字面重叠的同义查询 | 0/10（关键词无法命中） |
| privacy | 10 | private/secret 跨场合是否泄露 | 10/10，0 泄露 |
| venue | 10 | 群事实是否留在本群 | 10/10 |
| role | 10 | A→B / B→A 角色方向 | 0/10（未实现关系图） |
| temporal | 10 | 新/旧事件先后 | 0/10（未实现事件时间） |
| persona | 10 | 同一人 group/private 温柔/耐心差 ≤2 | 10/10 |

## 运行

```bash
python scripts/eval_suite.py --save-baseline eval/baselines/2026-10.json
python scripts/eval_suite.py --check eval/baselines/2026-10.json
```

- 不调用 LLM、不依赖网络；
- 使用临时 DB，不改线上；
- 输出 `reports/eval-YYYY-MM-DD.json`。

## 说明

- paraphrase 的 0/10 是**基线**，不是回归；真实语义检索单独评估为 9/10（见 `docs/LOCAL_EMBEDDING_DEPLOYMENT.md`），下一步会把语义通道接进 runner。
- role/temporal 的 0/10 是**已知能力缺口**，不是测试失败；先记录，后续按路线图补关系图/事件时间。
