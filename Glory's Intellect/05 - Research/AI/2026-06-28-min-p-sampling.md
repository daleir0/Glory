---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2407.01082"
date: 2026-06-28
tags: [sampling, inference, llama-cpp, decoding, temperature, local-inference]
---
# Min-p Sampling: Confidence-Scaled Truncation That Replaces Top-k/Top-p

## What
Min-p is a dynamic truncation sampler that keeps only tokens whose probability is at least `min_p × p_max`, where `p_max` is the top token's probability. The cutoff therefore *scales with the model's confidence*: when one token dominates (p_max≈0.9, min_p=0.1 → floor 0.09) it keeps a tight set; when the distribution is flat (p_max≈0.2 → floor 0.02) it admits more variety. This single mechanism subsumes the job of both top-k and top-p. Published as "Turning Up the Heat" (arXiv 2407.01082), it was the 18th-highest-scoring ICLR 2025 submission and an oral; min_p of 0.05–0.1 consistently beats top-p on GPQA, GSM8K, and creative writing — *especially at high temperature*, where top-p's fixed cumulative mass admits long garbage tails.

## Why It Matters
Glory's local stack (llama.cpp on the RTX 3060, serving Qwen/Gemma GGUFs) exposes min-p directly via `--min-p`. The verified power-user config as of early 2026 is **`--temp 0.7 --min-p 0.05 --top-k 0 --top-p 1.0`** — two knobs instead of four, disabling top-k/top-p entirely. This lets us raise temperature for diversity (agentic exploration, creative synthesis) without the incoherence top-p produces, because the truncation floor rises with confidence. Knowing llama.cpp's sampler chain order matters: logits → penalties → dry → top_n_sigma → top_k → typical → top_p → **min_p → xtc → temperature → sample**. min_p runs before temperature in that chain, so the relative-probability floor is computed on pre-temperature logits — set temperature high freely; min_p still guards coherence. Without this, our high-temp generations either collapse (low temp) or hallucinate tails (top-p at high temp).

## Source
- https://arxiv.org/abs/2407.01082 — "Turning Up the Heat: Min-p Sampling for Creative and Coherent LLM Outputs"
- https://iclr.cc/virtual/2025/oral/31888 — ICLR 2025 oral
- https://smcleod.net/2025/04/llm-sampling-parameters-guide/ — llama.cpp sampler chain + recommended settings

## Connected To
- [[2026-05-31-gbnf-grammar-constrained-decoding]]
- [[2026-06-27-batch-invariant-deterministic-inference]]
- [[2026-06-05-eagle-3-speculative-decoding]]
- [[2026-05-18-rtx3060-optimal-llm-models]]
