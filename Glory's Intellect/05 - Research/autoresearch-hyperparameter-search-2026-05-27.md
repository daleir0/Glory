---
tags: [research, ml, hyperparameter-search, autoresearch, nanogpt, muon]
date: 2026-05-27
project: autoresearch
status: verified
---

# Autoresearch Hyperparameter Search — No-Compile Windows Regime

Verified learnings from the autoresearch ML loop (`E:\Glory\autoresearch`), a
time-budgeted (300s) GPT pretraining sweep on `climbmix-400b-shuffle`, RTX 3060
12GB. Each result is one full training run; `val_bpb` = validation bits-per-byte
(lower is better). Architecture: ~25M param GPT, Muon optimizer for matrices +
Adam for embeddings/scalars, BPE vocab 8192, seq_len 2048.

## Baseline context

The old **compiled** best was ~1.172 val_bpb. Under the Windows **no-compile**
regime (SDPA shim replacing flash-attn3, `TORCHDYNAMO_DISABLE=1` because
triton-windows 3.7 breaks PyTorch 2.9 inductor backward), results are NOT
comparable — eager mode keeps all backward activations (7.7 GB vs 3.1 GB) and
the no-compile baseline reset to **1.2879**. All findings below are within the
no-compile regime.

## The winning trajectory (1.2879 → 1.256050)

| Change | val_bpb | verdict |
|--------|---------|---------|
| no-compile baseline | 1.2879 | — |
| EMBEDDING_LR 0.4 → 0.5 → 0.6 | 1.2743 | keep (0.7 unstable) |
| ADAM_BETAS beta2 0.95 → 0.98 → 0.99 | 1.2716 | keep (0.999 worse) |
| SCALAR_LR 0.5 → 0.3 → 0.1 → 0.03 → 0.01 | 1.2649 | keep (0.003 & 0.0 worse) |
| MATRIX_LR 0.02 → 0.025 (retest w/ new config) | 1.2639 | keep |
| **DEPTH 5 → 4** (more steps in 300s budget) | 1.2627 | **keep** |
| **MATRIX_LR 0.025 → 0.035** (retune for DEPTH=4) | **1.256050** | **keep (best)** |

## Key insights (the transferable ones)

1. **Hyperparameters interact — re-test after any structural change.**
   MATRIX_LR=0.025 was a *discard* at DEPTH=5 (1.283) but a *keep* once
   SCALAR_LR and beta2 were tuned. After dropping to DEPTH=4 it wanted to go
   higher still (0.035). A greedy one-knob-at-a-time sweep misses these; periodic
   re-tests of previously-rejected values are essential.

2. **SCALAR_LR (per-layer learnable scalars) wants to be ~50× lower than default.**
   Monotonic improvement 0.5 → 0.01 (1.2716 → 1.2649). But freezing entirely
   (0.0) is *worse* (1.2672) — the scalars must learn, just slowly.

3. **Smaller-but-more-trained beats bigger-undertrained on a fixed time budget.**
   DEPTH=4 (1124 steps) > DEPTH=5 (712 steps) > DEPTH=6 (615 steps). DEPTH=3 is
   undercapacity (1.274) even at 1319 steps. For a 300s/RTX-3060 budget, depth 4
   is the sweet spot. Smaller models also tolerate (want) higher Muon LR.

4. **Adam beta2=0.99 > 0.95 default** for this setup; beta1 stays at 0.8.

5. **Batch size 2^15 is a hard floor.** 2^16 halves the step count and craters
   val_bpb to 1.378 — step count dominates at this budget.

## Confirmed-optimal (don't re-litigate without a structural change)

EMBEDDING_LR=0.6, UNEMBEDDING_LR=0.004, WEIGHT_DECAY=0.05, WARMUP_RATIO=0.05,
WARMDOWN_RATIO=0.5, FINAL_LR_FRAC=0.1, TOTAL_BATCH_SIZE=2^15.

## Best config (val_bpb = 1.256050)

```
DEPTH = 4
EMBEDDING_LR = 0.6
UNEMBEDDING_LR = 0.004
MATRIX_LR = 0.035        # Muon
SCALAR_LR = 0.01
WEIGHT_DECAY = 0.05
ADAM_BETAS = (0.8, 0.99)
WARMUP_RATIO = 0.05
WARMDOWN_RATIO = 0.5
FINAL_LR_FRAC = 0.1
TOTAL_BATCH_SIZE = 2**15
```

## Operational note

D:\Glory\autoresearch was wiped mid-session; the live repo is **E:\Glory\autoresearch**
(branch `autoresearch/may6`). Three beta2 results (1.2733/1.2716/1.2791) ran from
the old path and were backfilled into results.tsv with `lost-` commit prefixes.
