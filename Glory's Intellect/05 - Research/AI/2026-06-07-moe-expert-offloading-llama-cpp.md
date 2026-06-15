---
type: research-note
domain: AI
confidence: verified
source: "https://huggingface.co/blog/Doctor-Shotgun/llamacpp-moe-offload-guide"
date: 2026-06-07
tags: [moe, llama-cpp, inference, vram, offloading, gguf, kimi-k2, local-inference]
---
# MoE Expert Offloading: Run Huge MoE Models on Small VRAM by Pinning Attention to GPU and Routed Experts to CPU

## What
For Mixture-of-Experts models, the attention/shared weights are used on *every*
token while the routed FFN expert weights are used sparsely. llama.cpp's
`--override-tensor` / `-ot` flag (and the newer `--n-cpu-moe` shortcut) exploits
this: pin all "always-active" tensors on the GPU and offload the big, rarely-hit
routed experts to CPU RAM with a regex like `-ot "\.ffn_.*_exps\.weight=CPU"`.
The CPU does the expert matmul on the small per-token activation vector shipped
over PCIe, then returns the result. This makes a model far larger than VRAM
runnable instead of impossible. Real numbers: a 141GB MiniMax on a 96GB GPU went
from **5.7 → 16.7 tok/s** by pinning attention to GPU and offloading only
experts; ~15–20% of experts handle ~80% of tokens, so keeping those *hot*
experts VRAM-resident drives per-token PCIe traffic toward zero after warm-up.

## Why It Matters
This is the exact lever that lets Glory run Kimi-K2.6-class MoE locally. The naive
choice is binary — "fits in 16GB or it doesn't" — and a frontier MoE never fits.
Offloading changes the question from *which layers fit* (`-ngl`) to *which tensor
types fit*: keep the dense attention + shared experts (small, hit every token) on
the 3060, push the routed FFN experts (huge, sparse) to system RAM. That converts
"can't load" into "loads and runs at usable speed." Without this technique Glory
is capped at small dense models; with it, the ceiling becomes system RAM, not
VRAM. The tuning is empirical — adjust the `-ot` regex per model topology and
measure tok/s. The frontier beyond llama.cpp's static split is a hot-expert
cache with an eviction policy (proposed in ggml-org/llama.cpp#20757; cf. ProMoE
proactive caching, HOBBIT mixed-precision offload).

## Source
- https://huggingface.co/blog/Doctor-Shotgun/llamacpp-moe-offload-guide
- https://medium.com/@david.sanftenberg/gpu-poor-how-to-configure-offloading-for-the-qwen-3-235b-a22b-moe-model-using-llama-cpp-13dc15287bed
- https://github.com/ggml-org/llama.cpp/discussions/13154 (-ot / --override-tensor flag)
- https://github.com/ggml-org/llama.cpp/issues/20757 (two-tier GPU+RAM expert cache proposal)

## Connected To
- [[2026-05-18-kimi-k2-architecture]]
- [[2026-05-18-rtx3060-optimal-llm-models]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-05-30-model-merging-dare-ties]]
