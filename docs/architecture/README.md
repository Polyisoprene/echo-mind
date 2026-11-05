# 架构与工程契约（Architecture）

回答"代码该怎么写"。这里的规则由 `tests/architecture/` 下的 AST 门禁强制执行。

| 文档 | 说明 |
|---|---|
| [`ARCHITECTURE_CONTRACTS.md`](ARCHITECTURE_CONTRACTS.md) | **最高工程契约**：7 层边界、SOLID 硬约束、扁平化四原则、值对象清单 |
| [`RED_GREEN_AND_AB_LANES.md`](RED_GREEN_AND_AB_LANES.md) | 红绿交付与 A/B 双线工程流程 |
| [`DATA_MIGRATION_GUIDE.md`](DATA_MIGRATION_GUIDE.md) | 外部数据导入与旧版迁移指南 |

## 相关门禁

| 门禁 | 强制内容 |
|---|---|
| [`tests/architecture/test_solid_boundaries.py`](../../tests/architecture/test_solid_boundaries.py) | 分层依赖、单文件/单函数长度、嵌套深度、值对象不可变、Protocol 窄接口 |
| [`tests/architecture/test_docs_integrity.py`](../../tests/architecture/test_docs_integrity.py) | 文档链接有效性、目录规范、归档标注 |
| [`tests/architecture/test_param_provenance.py`](../../tests/architecture/test_param_provenance.py) | 参数溯源 |
| [`tests/architecture/test_persona_single_source.py`](../../tests/architecture/test_persona_single_source.py) | 人格默认值单一事实源 |
| [`tests/architecture/test_evidence_ledger.py`](../../tests/architecture/test_evidence_ledger.py) | 证据账本 |

<div align="right"><a href="../README.md">← 返回文档索引</a></div>
