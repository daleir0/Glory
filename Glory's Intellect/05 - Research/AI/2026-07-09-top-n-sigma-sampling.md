---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2411.07641"
date: 2026-07-09
tags: [sampling, inference, llama-cpp, decoding, temperature, local-inference]
---
# Top-nσ Sampling: Temperature-Invariant Token Filtering in Logit Space

## What
Top-nσ (ACL 2025, arXiv 2411.07641) filters candidate tokens *before* softmax using a single statistical rule on the raw logits: `threshold = max(logits) - n * std(logits)`, then sets every logit below the threshold to `-inf`. The insight is that a model's logits split into a large **Gaussian-distributed noise region** (the bulk) and a small **informative region** (outliers near the max); keeping only logits within `n` standard deviations of the peak removes the noise directly, no probability manipulation needed. Recommended `n ≈ 1.0`. It is **temperature-invariant**: scaling logits by `1/T` scales `max` and `std` by the same factor, so `threshold` scales by `1/T` too and the *surviving token set does not change with temperature* — temperature only reshapes probabilities *within* that fixed set.

## Why It Matters
This fixes the core failure mode of top-p/min-p at high temperature: normally, raising `T` flattens the distribution and lets low-quality "noise" tokens leak into the sample, so you're forced to keep `T` low and lose diversity. Top-nσ decouples the two — the noise floor is cut in logit space *once*, and then temperature safely tunes creativity within the clean survivor set. The paper shows the biggest gains in high-temperature reasoning and creative-writing settings. For Glory's local stack this is directly usable: it's merged in llama.cpp (PR #11223, server support #11896) and exposed as `--top-n-sigma` (default 0 = off; set `~1.0` to enable). It's cheaper than top-p (no sort, no cumulative-probability pass — just max + std over the vocab), and it complements the existing [[2026-06-28-min-p-sampling]] note: min-p prunes in *probability* space post-softmax, top-nσ prunes in *logit* space pre-softmax with temperature robustness min-p lacks. Practical use for Gemma/Qwen research runs: enable top-nσ ≈ 1.0 and push temperature higher for idea diversity without the usual degeneration.

## Source
- Paper: https://arxiv.org/abs/2411.07641 — "Top-nσ: Not All Logits Are You Need" (Tang, Liu, Xu, Huang; ACL 2025 Long Papers)
- llama.cpp sampler: https://github.com/ggml-org/llama.cpp/pull/11223 ; server flag: PR #11896 (`--top-n-sigma`)

## Connected To
- [[2026-06-28-min-p-sampling]]
- [[2026-05-31-gbnf-grammar-constrained-decoding]]
