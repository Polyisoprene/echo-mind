# 本地 Embedding 部署（192.168.3.2）

## 机器

- 主机：`192.168.3.2`，用户 `polyisoprene`；
- GPU：AMD Radeon RX 6800（gfx1030），ROCm，17.16GB 显存；
- 复用语音服务的 Python 3.11 venv（torch 2.11+rocm7.2、transformers 4.51），**不新增依赖**；
- 服务不占 systemd（语音服务的 systemd 因 render 组被禁用），用 screen。

## 模型

- `BAAI/bge-small-zh-v1.5`，512 维；
- 目录：`/home/polyisoprene/embedding-service/bge-small-zh-v1.5`；
- 下载脚本：`scripts/download_bge_small_zh.sh`（默认 hf-mirror，失败回退官方）。

## 服务

```bash
# 启动/重启
screen -dmS embedding bash /home/polyisoprene/embedding-service/run.sh
# 健康
curl http://192.168.3.2:8010/health
```

- `run.sh` 循环启动 `server.py --model ... --host 0.0.0.0 --port 8010 --device cuda`；
- 日志：`~/embedding-service/embedding.log`；
- OpenAI 兼容：`POST http://192.168.3.2:8010/v1/embeddings`。

## 资源实测

| 项 | 数值 |
|---|---|
| 启动前显存 | 8.96GB |
| 空闲 | 9.26GB（+282MB） |
| 回填后 | 9.59GB（+632MB） |
| 进程 RSS | 约 1.45GB |
| 单条查询 | 约 10–85ms |
| 3 条批量 | 约 13ms（热） |

剩余显存约 7.5GB，安全。

## EchoMind 配置

两份 `data*/config.json` 的 `api` 段：

```json
"embeddingModel": "BAAI/bge-small-zh-v1.5",
"embeddingBaseUrl": "http://192.168.3.2:8010/v1",
"embeddingApiKey": "local",
"embeddingDimensions": 512
```

回填：

```bash
.venv/bin/python scripts/backfill_memory_vectors.py --apply
.venv/bin/python scripts/backfill_memory_vectors.py --db data-xiaomo/echomind.db --apply
```

## 效果

- 同义查询 recall@5：关键词 5/10 → **9/10**；
- BGE 查询前缀 8/10，因此不加前缀；
- frame 在覆盖足够时走语义 rerank，失败自动回退关键词。

## 注意

- 服务重启后需确认 `screen embedding` 存在；
- 模型/向量切换时 `memory_vectors.model` 会隔离，避免混用；
- 当前是 10 条合成查询，不是 GroupMemBench/人工盲评。
