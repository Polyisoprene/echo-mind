# External benchmarks

## LongMemEval-S

- Paper: Wu et al., *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory*, ICLR 2025. [arXiv:2410.10813](https://arxiv.org/abs/2410.10813)
- Data: [xiaowu0162/longmemeval-cleaned](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned)
- File used: `longmemeval_s_cleaned.json` (~265MB), **not committed**.
- Adapter: `scripts/eval_longmemeval.py`
- Baselines: `eval/baselines/longmemeval-session-100-2026-11-01.json` (bge-small), `eval/baselines/longmemeval-m3-session-100-2026-11-01.json` (bge-m3)
- Report: `docs/EXTERNAL_BENCHMARK_LONGMEMEVAL.md`
- bge-m3 result: session recall@5 **0.510**, MRR **0.315** (100 questions, session granularity)

Download:

```bash
mkdir -p data/external
curl -L --fail -o data/external/longmemeval_s.json \
  https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json
```

Run on 192.168.3.2 (memory-constrained host):

```bash
PYTHONPATH=src python scripts/eval_longmemeval.py \
  --limit 100 --granularity session --batch 4 \
  --out reports/longmemeval_m3_session_100.json
```

The dataset is public research data; keep the citation when publishing results.

bge-m3 at batch=32 OOMs on the 17GB GPU; use `--batch 4`.
