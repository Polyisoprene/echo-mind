# 部署与运维（Operations）

回答"怎么让它稳定跑起来"。日常启停用 [`../../scripts/service.sh`](../../scripts/service.sh)，本目录记录**外部依赖服务**的部署细节。

| 文档 | 说明 |
|---|---|
| [`LOCAL_EMBEDDING_DEPLOYMENT.md`](LOCAL_EMBEDDING_DEPLOYMENT.md) | 本地 embedding 服务部署（GPU、端口、模型、显存取舍） |

## 外部依赖速查

| 服务 | 默认地址 | 缺失时的行为 |
|---|---|---|
| Embedding（bge-m3） | `http://127.0.0.1:8010` | 语义检索降级为关键词检索 |
| 语音合成（CosyVoice3） | 见 `data/config.json` 的 `feiyuVoice.baseUrl` | 语音类工具不可用，文字链路正常 |
| LLM 网关 | 见 `api.baseUrl`，支持 `fallbackModels` 链 | 主端点失败自动切备用端点 |
| OneBot（NapCat） | 见 `snowluma.wsUrl` / `httpUrl` | 无法收发 QQ 消息 |

> 完整的启停、多实例、故障排查见 [`../HANDOFF.md`](../HANDOFF.md)。

<div align="right"><a href="../README.md">← 返回文档索引</a></div>
