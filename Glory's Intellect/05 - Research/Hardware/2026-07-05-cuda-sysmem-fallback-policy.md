---
type: research-note
domain: hardware
confidence: verified
source: "https://nvidia.custhelp.com/app/answers/detail/a_id/5490"
date: 2026-07-05
tags: [gpu, vram, cuda, windows, nvidia-driver, local-inference, rtx-3060, llama-cpp]
---
# CUDA Sysmem Fallback: Windows NVIDIA driver silently spills VRAM overflow to system RAM

## What
Since driver 536.40 (June 2023), the Windows NVIDIA driver no longer throws out-of-memory when a CUDA allocation doesn't fit in dedicated VRAM — it silently places the allocation in "shared GPU memory" (system RAM over PCIe, capped at half of installed RAM). The spill triggers when the GPU gets *close* to full, not only at the hard limit, and it is Windows-only (WDDM behavior; Linux drivers still OOM). It is controllable per-application in NVIDIA Control Panel → Manage 3D Settings → **CUDA - Sysmem Fallback Policy** → Driver Default / Prefer No Sysmem Fallback / Prefer Sysmem Fallback.

## Why It Matters
This is the #1 cause of "my model suddenly got 10x slower mid-session" on Glory's RTX 3060 12GB. Decode is memory-bandwidth-bound (see [[2026-07-01-decode-memory-bandwidth-roofline]]): weights/KV read from GDDR6 at ~360 GB/s, but anything spilled to shared memory reads over PCIe at ~16-32 GB/s — a 10-20x cut on every token for the spilled fraction. The trap is that it's *silent and delayed*: a model that fits at load time (LM Studio, llama.cpp) crosses the edge later as the KV cache grows with context, so token/s collapses mid-session with no error. Detection: Task Manager → Performance → GPU → "Shared GPU memory" climbing while dedicated is pinned near max. Fix for Glory's stack: set **Prefer No Sysmem Fallback** per-program (python.exe / LM Studio) so overflow fails fast as a hard OOM — then drop quant size, context length, or GPU layers deliberately instead of eating a silent 10x tax. Pairs with [[2026-05-29-kv-cache-quantization]] to keep KV growth from ever hitting the edge.

## Source
- https://nvidia.custhelp.com/app/answers/detail/a_id/5490 (official: fallback behavior, per-app control, "switch occurs when running close to maxing out GPU memory")
- https://github.com/AUTOMATIC1111/stable-diffusion-webui/discussions/14077 (shared GPU memory capped at half of installed RAM; per-application scope of the setting)
- https://www.popularai.org/p/why-ollama-and-llama-cpp-crawl-when-models-spill-into-ram-and-how-to-fix-it (llama.cpp/Ollama-specific symptom profile)

## Connected To
- [[2026-07-01-decode-memory-bandwidth-roofline]]
- [[2026-05-18-rtx3060-optimal-llm-models]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-07-moe-expert-offloading-llama-cpp]]
