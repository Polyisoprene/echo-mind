# CharacterEval 接入审计（2026-11-01）

> 数据：CharacterEval 官方仓库浅克隆到 `data/external/CharacterEval`。
> 状态：**数据已获取；评分未跑**。

## 1. 数据

```text
data/test_data.jsonl      4564 条测试对话
data/character_profiles.json  77 个角色
data/id2metric.jsonl      指标定义
results/*.jsonl           官方五个模型的参考输出
```

字段：

```text
id, role, novel_name, context
```

`get_response.py` 的协议：

- 用角色 profile 构造 system；
- 把 context 拆成对话；
- 模型扮演 role，预测最后一条回复。

## 2. 评分依赖

官方评分需要：

```text
BaichuanCharRM（HuggingFace morecry/BaichuanCharRM）
+ GPU
+ run_char_rm.py
+ 13 指标 / 4 维度
```

本机/远端当前没有 CharacterRM，也没有足够的 GPU 显存；因此**不能产出官方 CharacterEval 分数**。

## 3. 现在能做什么

- 已获取数据与 profile；
- 可以生成模型回复；
- 但不能用 LLM judge 冒充 CharacterRM；
- 不能把“自己写的 rubric”当官方 13 指标；
- 不接 live。

## 4. 结论

CharacterEval 不是“代码没写”，而是**评分资源缺失**：

```text
数据：可用
生成：可做
官方评分：缺 CharacterRM/GPU
```

在拿到 CharacterRM 前，只保留数据审计，不报告分数。

## 5. 后续

1. 确认远端 ROCm/GPU 能否加载 BaichuanCharRM；
2. 或使用官方提供的中间结果做协议校验；
3. 没有 reward model 就不宣称 CharacterEval 完成。
