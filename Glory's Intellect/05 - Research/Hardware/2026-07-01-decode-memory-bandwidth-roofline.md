---
type: research-note
domain: Hardware
confidence: verified
source: "https://arxiv.org/html/2402.16363v4"
date: 2026-07-01
tags: [roofline, memory-bandwidth, arithmetic-intensity, inference, rtx3060, quantization, batching]
---
# LLM Decode Is Memory-Bandwidth-Bound: The Roofline Ceiling on Glory's RTX 3060

## What
During single-stream (batch-1) autoregressive decode, the GPU must re-read **every model weight from VRAM to produce each token**, while doing only a trivial amount of arithmetic per byte read. This gives decode very low *arithmetic intensity* (FLOPs ÷ bytes moved), so it sits on the memory-bandwidth slope of the roofline — the GPU idles waiting on memory, not compute. The hard ceiling is therefore:

```
max_tokens_per_sec ≈ VRAM_bandwidth / bytes_read_per_token
                   ≈ VRAM_bandwidth / model_size_in_bytes   (batch=1)
```

On Glory's **RTX 3060 12GB** (360 GB/s, 192-bit GDDR6 @ 15 Gbps), the theoretical decode ceilings are:
- 7B @ Q4 (~4.5 GB): 360 / 4.5 ≈ **~80 tok/s** ceiling (real llama.cpp ~50–70)
- 7B @ Q8 (~7 GB): 360 / 7 ≈ **~51 tok/s**
- 7B @ FP16 (14 GB): won't even fit in 12 GB

Prefill (prompt ingestion) is the opposite: high arithmetic intensity, **compute-bound**, uses the 13 shader-TFLOPS / tensor cores.

## Why It Matters
This single ratio is the "why" behind most of the AI/inference notes in this vault, and it dictates every local-inference decision on the 3060:
- **Quantization is a direct speedup, not just a memory saver.** Halving bytes/token (Q8→Q4) nearly doubles the decode ceiling. This is why [[2026-06-24-imatrix-iq-quantization-gguf]] and [[2026-05-29-kv-cache-quantization]] matter for latency, not only for fitting the model.
- **Batching raises throughput but not per-stream latency.** More concurrent requests amortize one weight-read across many tokens (AI rises toward the compute roof) — the basis of [[2026-06-03-pagedattention-continuous-batching]]. But at batch=1, more compute is useless.
- **Speculative decoding wins because it verifies K tokens per weight-read pass**, spending idle memory-bound cycles on parallel compute — exactly why [[2026-05-28-speculative-decoding-local-inference]] and [[2026-06-05-eagle-3-speculative-decoding]] give real speedups on the 3060.
- **MoE offloading is slow because PCIe (~16 GB/s) is ~22× narrower than VRAM (360 GB/s)** — any weight pulled across the bus per token is catastrophic for the ceiling, framing the trade-offs in [[2026-06-07-moe-expert-offloading-llama-cpp]].
- **Practical rule for Glory:** to make local generation faster, cut bytes-read-per-token (quantize weights + KV cache, shrink the model, keep everything in VRAM) or read fewer times per output token (speculative/multi-token). Adding compute does nothing.

## Source
- LLM Inference Unveiled: Survey and Roofline Model Insights — https://arxiv.org/html/2402.16363v4
- RTX 3060 12GB specs (360 GB/s, 192-bit, 15 Gbps GDDR6) — https://www.techpowerup.com/gpu-specs/geforce-rtx-3060-12-gb.c3682

## Connected To
- [[2026-05-18-rtx3060-optimal-llm-models]]
- [[2026-06-24-imatrix-iq-quantization-gguf]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-03-pagedattention-continuous-batching]]
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-06-07-moe-expert-offloading-llama-cpp]]
