---
type: research-note
domain: AI
confidence: verified
source: "https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md"
date: 2026-06-24
tags: [quantization, gguf, llama-cpp, imatrix, iq-quants, local-inference, vram]
---
# Importance-Matrix (imatrix) Quantization and the IQ Formats in GGUF

## What
An **importance matrix (imatrix)** is a per-tensor table where each entry holds the mean-squared activation magnitude observed at that weight position while running a calibration corpus (e.g. WikiText) through the *unquantized* model. `llama-imatrix` intercepts every matmul via an eval callback to accumulate these stats. The quantizer then biases per-block scale selection toward the weights that real inputs exercise most, spending precision where it cuts loss the most. The **IQ formats** (IQ1_S, IQ2_XXS/XS/S, IQ3_XXS/XS/S/M, IQ4_XS/NL) are lookup-table-based "I-quants" *designed around* an imatrix — they recover weights from a super-block scale plus the importance matrix and give the best quality-per-byte at low bitrates. Key thresholds:
- **≤3 bpw:** imatrix is essential; the lowest IQ types degrade badly without it. A poorly-calibrated IQ-quant can be *worse* than the plain K-quant of the same size.
- **Q4_K_M and above:** imatrix gives only marginal benefit.
- **Calibration set matters:** perplexity/KL-divergence numbers shift a lot with the imatrix dataset (most public GGUFs calibrate on Wiki-like text at 512 ctx, which flatters Wiki-test perplexity).

**Unsloth Dynamic 2.0** is the current SOTA on top of this: instead of one uniform quant type, it picks a *different bit-width per layer* using a model-specific scheme (Gemma's scheme ≠ Llama's) plus a hand-curated 300K–1.5M-token calibration set, and beats standard imatrix and QAT on both MMLU and KL-divergence across Gemma 3, Llama 4, and Qwen3.5.

## Why It Matters
Glory runs Kimi K2.6 and Gemma locally as GGUF through llama.cpp on a 16GB / RTX 3060 budget — quant choice is the single biggest lever on whether a model fits in VRAM and how much it degrades. This note converts that into rules: don't trust a generic "IQ2 is smaller" — below 3 bpw the imatrix and its calibration corpus *are* the model quality, so prefer Unsloth Dynamic 2.0 uploads (or generate our own imatrix on a corpus that matches Glory's actual workload) over naive IQ quants. Above ~Q4_K_M, skip imatrix effort entirely — it buys almost nothing. This is the difference between a usable local model and one that quietly produces worse completions to save a gigabyte.

## Source
- https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md
- https://github.com/ggml-org/llama.cpp/discussions/5006 (imatrix calibration on near-random data)
- https://kaitchup.substack.com/p/choosing-a-gguf-model-k-quants-i (K-quants vs I-quants)
- https://unsloth.ai/docs/basics/unsloth-dynamic-2.0-ggufs (Dynamic 2.0 per-layer quant)

## Connected To
- [[2026-06-08-qlora-nf4-mechanics]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-07-moe-expert-offloading-llama-cpp]]
- [[2026-05-30-model-merging-dare-ties]]
