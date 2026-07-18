---
type: research-note
domain: hardware
confidence: verified
source: "https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/"
date: 2026-07-18
tags: [cuda-graphs, llama-cpp, decode-latency, kernel-launch-overhead, wddm, windows, moe, rtx3060]
---
# CUDA Graphs collapse per-token kernel launch overhead in llama.cpp — but silently switch off for MoE models

## What
llama.cpp captures the entire single-token decode graph into one CUDA graph and replays it with a single launch call, instead of dispatching every kernel individually from the CPU. NVIDIA measured llama-2-7b Q4_K_M on H100-PCIe going 143.35 → 163.83 tok/s (~14%, up to 1.2x), with graph execution itself ~40% faster and the inter-kernel gaps nearly eliminated. It is on by default, but **only for batch size 1**, and it is disabled at runtime when the graph contains `MUL_MAT_ID` nodes (MoE expert routing), when split buffers are present, or after too many consecutive graph updates — `GGML_CUDA_DISABLE_GRAPHS=1` forces it off entirely.

The escape hatch that makes it viable: rather than re-instantiating the graph each token, llama.cpp patches only the KV-cache node parameters in place, and calls `cudaGraphExecUpdate` when the context grows enough to change kernel grid sizes.

## Why It Matters
This is a bigger lever on Glory's box than on the H100 it was benchmarked on, for two compounding reasons:

1. **Windows WDDM taxes every launch.** Under WDDM packet scheduling the OS serializes submissions per context, so the CUDA driver has to batch launches to hide the cost — work submission is near-instantaneous on native Linux, not on Windows. Null-kernel launch overhead sits around 2.3–2.8 µs. Decode is dozens of tiny kernels per token, so on the RTX 3060 the CPU-side dispatch path is a *larger* fraction of step time than on an H100, and CUDA graphs remove it wholesale.
2. **Decode at batch 1 is exactly Glory's workload.** Every local inference path — Hermes/Gemma at :1234, the proxy at :8082, autoresearch — is single-stream greedy decode. That is the one regime where graphs are enabled and where launch overhead is most exposed, because there is no batch work to hide it behind.

The trap worth remembering: **MoE gets nothing here.** `MUL_MAT_ID` is the expert-gather op, so Kimi K2 and any MoE GGUF fall back to eager per-kernel dispatch and eat the full WDDM launch tax. That partly explains why MoE decode on Windows underperforms its FLOP/bandwidth budget — the gap is host-side scheduling, not the GPU. It also means MoE offload tuning ([[2026-06-07-moe-expert-offloading-llama-cpp]]) is fighting a second, independent overhead that expert placement cannot fix.

Two more operational consequences:
- **CUDA graphs are a suspect during correctness bugs, not just a perf knob.** They have historically broken quantized K cache; `GGML_CUDA_DISABLE_GRAPHS=1` is the first bisect step when a quantized-cache run produces garbage ([[2026-05-29-kv-cache-quantization]]).
- **Graph capture assumes a stable kernel shape.** Anything that perturbs grid sizes per token — changing batch size, speculative decoding accepting a variable number of drafted tokens — forces updates or disables capture. Speculative decoding's multi-token verify step is inherently batch>1, so its measured wins ([[2026-05-28-speculative-decoding-local-inference]], [[2026-07-10-prompt-lookup-decoding-draft-free-speculative]]) are already net of losing graphs on the verify pass.

Practical read: for dense models at batch 1 on Windows, confirm graphs are active before trusting any decode benchmark — a run with graphs disabled and one with them on are not the same experiment.

## Source
- https://developer.nvidia.com/blog/optimizing-llama-cpp-ai-inference-with-cuda-graphs/
- https://github.com/ggml-org/llama.cpp/issues/6763 (integration tracking)
- https://github.com/ggml-org/llama.cpp/issues/7492 (graphs break quantized K cache)
- https://github.com/ggml-org/llama.cpp/pull/7302 (avoid unnecessarily disabling graphs)
- https://developer.nvidia.com/blog/leveling-up-cuda-performance-on-wsl2-with-new-enhancements/ (WDDM submission model)

## Connected To
- [[2026-07-01-decode-memory-bandwidth-roofline]] — launch overhead is the *other* ceiling; roofline explains the GPU-side limit, this explains the host-side one
- [[2026-06-07-moe-expert-offloading-llama-cpp]] — MoE forfeits graphs via MUL_MAT_ID
- [[2026-07-04-windows-timer-resolution-high-precision-sleep]] — same theme: Windows scheduling as a latency tax
- [[2026-05-29-kv-cache-quantization]] — known graph/quantized-cache interaction
- [[2026-06-27-batch-invariant-deterministic-inference]] — graph capture pins kernel shape, reinforcing determinism at fixed batch
- [[2026-07-12-chunked-prefill-stall-free-batching]] — batching moves you out of the graph-eligible regime
- [[2026-05-18-rtx3060-optimal-llm-models]] — the hardware this matters most on
