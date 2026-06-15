---
type: research-note
domain: AI
confidence: verified
source: "https://huggingface.co/blog/mlabonne/merge-models"
date: 2026-05-30
tags: [model-merging, mergekit, dare, ties, slerp, local-inference, no-train]
---
# Model Merging (DARE-TIES) — Combine Fine-Tunes Into One Model With No GPU Training

## What
Model merging fuses the weights of several fine-tunes of the **same base model** into a single model — no training, no GPU gradient passes, runs on CPU in minutes via `mergekit`. Three core methods:

- **SLERP** — spherical interpolation between **two** models; preserves direction of the weight vectors (not just magnitude), giving a smoother blend than naive averaging. Limited to 2 models at a time.
- **TIES** (Trim, Elect Sign, Merge) — for **3+** models. Computes each model's *task vector* (delta from the base), **trims** to the top-k% highest-magnitude deltas, **elects** a single dominant sign per parameter to resolve conflicts, then merges only the agreeing deltas.
- **DARE** (Drop And REscale) — sparsification used with TIES (`dare_ties`): randomly drops a fraction `p` of delta parameters, then **rescales survivors by 1/(1-p)** to keep output expectations unchanged.

**Why it works:** task-vector magnitudes are concentrated near zero — most fine-tuning changes are tiny noise, only a minority of parameters get large updates. DARE/TIES keep the high-magnitude tail and discard the low-magnitude noise, so independent fine-tunes merge with little interference.

**Practical defaults (from mlabonne / mergekit):**
- `density: 0.5–0.9` (retain 50–90% of each model's deltas; the docs report higher density beats the paper's <0.5 recommendation in practice).
- model `weight`s should **sum to ≈1.0** (tolerated range 0.9–1.1) — this gives lowest perplexity.
- `dare_ties` tends to produce lower-perplexity merges than plain TIES, task-arithmetic, or SLERP.

## Why It Matters
Glory runs local fine-tunes (Kimi-K2.6-GGUF, Gemma 4) on a single RTX 3060. Merging lets us **combine specialist capabilities — e.g. a code fine-tune + a reasoning fine-tune + a chat tune — into one set of weights with zero training cost**, then quantize the result once to GGUF for llama.cpp. This sidesteps the 3060's training bottleneck entirely: the expensive fine-tuning can be done elsewhere (or downloaded), and merging composes them on CPU. The constraint to remember: all inputs must share the **same base architecture/tokenizer**, and only the *delta* from that shared base is merged — so we can't merge across unrelated model families. Pairs naturally with our existing [[2026-05-26-muon-optimizer]] (cheaper fine-tuning) and [[2026-05-29-kv-cache-quantization]] (cheaper serving) to form a no-train / low-train capability-stacking pipeline.

## Source
- https://huggingface.co/blog/mlabonne/merge-models (mergekit practical guide, density/weight defaults)
- https://mbrenndoerfer.com/writing/model-merging-weight-averaging-task-arithmetic-ties-dare (why task-vector magnitude distribution makes DARE/TIES work)
- https://developer.nvidia.com/blog/an-introduction-to-model-merging-for-llms/

## Connected To
- [[2026-05-26-muon-optimizer]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-05-18-gemma-4-e4b-architecture]]
- [[2026-05-18-kimi-k2-architecture]]
