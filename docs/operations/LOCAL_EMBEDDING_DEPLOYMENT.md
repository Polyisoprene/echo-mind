# 本地 Embedding 部署（GTX 1050 Ti）

> 2026-11-02：embedding 已从远端 `192.168.3.2` 迁到本机，远端 8010 关闭。
> 目标是释放远端显存给语音服务，不是把远端模型简单换端口。

## 1. 机器与资源

```text
主机：本机
GPU：NVIDIA GeForce GTX 1050 Ti Mobile
VRAM：4.23GB
驱动：NVIDIA 580 内核模块
```

注意：`nvidia-smi` 当前未安装，但 torch CUDA 正常；不影响推理。

## 2. 依赖

独立 venv，不污染 EchoMind：

```text
/home/polyisoprene/embedding-service/venv
Python 3.12.15
torch 2.5.1+cu124
transformers 4.46.3
tokenizers 0.20.3
```

## 3. 模型

```text
bge-m3，1024 维
```

物理路径：

```text
~/Documents/echo-mind-storage/embedding-model
```

原路径：

```text
~/embedding-service/bge-m3
```

是软链接，指向 Documents 机械盘，避免占用根盘。

## 4. 启动

```bash
screen -dmS embedding-local bash -c \
  'cd /home/polyisoprene/embedding-service && \
   while true; do \
     venv/bin/python server.py \
       --model /home/polyisoprene/embedding-service/bge-m3 \
       --host 127.0.0.1 --port 8010 \
       --device cuda --dtype float16 --max-length 1024 \
       >> embedding.log 2>&1; \
     sleep 3; \
   done'
```

健康检查：

```bash
curl http://127.0.0.1:8010/health
```

期望：

```json
{"status":"ok","model":"/home/polyisoprene/embedding-service/bge-m3","device":"cuda"}
```

## 5. 资源实测

| 项 | 数值 |
|---|---|
| 进程 RSS | 约 1.29GB |
| 1050Ti 显存 | 约 1.24GB / 4.23GB |
| 1024 维 | 已验证 |
| 模型加载 | 约 42 秒 |

## 6. EchoMind 配置

`data/config.json` 与 `data-xiaomo/config.json`：

```json
"embeddingModel": "BAAI/bge-m3",
"embeddingBaseUrl": "http://127.0.0.1:8010/v1",
"embeddingApiKey": "local",
"embeddingDimensions": 1024
```

## 7. 真实链路验证

使用不发送 QQ 的 cognitive probe：

```bash
curl -s -X POST http://127.0.0.1:3310/api/mind/probe \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"chat_key":"group:813506156","text":"你还记得我喜欢吃什么吗？","sender_id":"3487266420","sender_name":"主人"}'
```

验证结果：

```text
probe ok = true
embedding.log: POST /v1/embeddings 200
rendered_mind_block: 包含权威事实与海马体召回
```

## 8. 远端状态

```text
远端 8010：已关闭
远端 9880：feiyu-voice
远端 screen：feiyu-voice、feiyu-tts-daemon
```

远端不再承担 embedding，显存留给语音。

## 9. 注意

- `embedding-local` 是 screen，不是 systemd；重启后手动拉起；
- 本地 4GB 显存不要同时加载其他大模型；
- 切勿把 `/tmp` 当 pip 临时目录：本机 `/tmp` 是 5.6GB tmpfs，装 CUDA wheel 会打满；使用：
  ```bash
  TMPDIR=~/Documents/echo-mind-storage/tmp
  ```
- 若回滚远端，把两份 config 的 URL 改回 `http://192.168.3.2:8010/v1` 并启动远端 screen。
