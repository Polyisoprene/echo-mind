# 本地 Embedding 部署（192.168.3.2）

## 机器

- 主机：`192.168.3.2`，用户 `polyisoprene`；
- GPU：AMD Radeon RX 6800（gfx1030），ROCm，17.16GB 显存；
- 复用语音服务的 Python 3.11 venv（torch 2.11+rocm7.2、transformers 4.51），**不新增依赖**；
- 服务不占 systemd（语音服务的 systemd 因 render 组被禁用），用 screen。

## 模型

- `BAAI/bge-m3`，1024 维，多语言；
- 目录：`/home/polyisoprene/embedding-service/bge-m3`；
- 旧模型目录保留，可回滚：`bge-small-zh-v1.5`；
- 下载源：hf-mirror 的 `BAAI/bge-m3`。

## 服务

```bash
# 启动/重启
screen -dmS embedding bash /home/polyisoprene/embedding-service/run.sh
# 健康
curl http://192.168.3.2:8010/health
```

- `run.sh` 循环启动 `server.py --model bge-m3 --host 0.0.0.0 --port 8010 --device cuda --dtype float16 --max-length 1024`；
- 日志：`~/embedding-service/embedding.log`；
- OpenAI 兼容：`POST http://192.168.3.2:8010/v1/embeddings`。

## 资源实测

| 项 | 数值 |
|---|---|
| bge-small 服务时显存 | 约 10.4GB |
| bge-m3（FP16）服务时显存 | 约 11.7GB（+1.3GB） |
| 空闲显存 | 约 5.4GB |
| 批量 32×1024 token | **OOM** |
| 外部评测安全 batch | 4 |

bge-m3 比 bge-small 多约 1.3GB 显存；单请求批量不要拉到 32。

## EchoMind 配置

两份 `data*/config.json` 的 `api` 段：

```json
"embeddingModel": "BAAI/bge-m3",
"embeddingBaseUrl": "http://192.168.3.2:8010/v1",
"embeddingApiKey": "local",
"embeddingDimensions": 1024
```

回填：

```bash
.venv/bin/python scripts/backfill_memory_vectors.py --apply
.venv/bin/python scripts/backfill_memory_vectors.py --db data-xiaomo/echomind.db --apply
```

## 效果

- 同义查询 recall@5：关键词 5/10 → bge-small **9/10**；
- LongMemEval-S 100 题检索：bge-small 44.0% → **bge-m3 51.0%**；
- 跨语言对照：`猫粮快没了` vs `the cat food is running low` cosine **0.899**，vs 无关句 0.548；
- frame 在覆盖足够时走语义 rerank，失败自动回退关键词。

## 注意

- 服务重启后需确认 `screen embedding` 存在；
- 模型/向量切换时 `memory_vectors.model` 会隔离，避免混用；
- LongMemEval 仍是英文检索-only，不是端到端 QA；中文外部集/GroupMemBench 还没接。
