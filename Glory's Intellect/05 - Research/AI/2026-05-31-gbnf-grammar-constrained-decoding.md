---
type: research-note
domain: AI
confidence: verified
source: "https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md"
date: 2026-05-31
tags: [llama-cpp, structured-output, json-schema, gbnf, local-inference, constrained-decoding]
---
# GBNF Grammar-Constrained Decoding: Guaranteeing Valid JSON from Local Models

## What
llama.cpp can mask the token sampler at every decode step so the model can *only* emit tokens that keep the output valid against a formal grammar (GBNF — GGML Backus-Naur Form). You rarely write GBNF by hand: the server converts a **subset** of JSON Schema to GBNF automatically. Invocation differs by endpoint:
- **`/completion`**: pass the schema in the top-level `json_schema` body field (or raw `grammar`).
- **`/v1/chat/completions`** (OpenAI-compatible): pass it inside `response_format`, e.g. `{"type":"json_schema","json_schema":{"schema":{...}}}` or `{"type":"json_object","schema":{...}}`.

The schema constrains sampling only — it is **not** injected into the prompt. The grammar guarantees structural validity (braces, types, enums, required keys), not semantic correctness.

Three verified gotchas that bite in production:
1. **Thinking bypasses grammar.** With `enable_thinking: true` (reasoning models), `response_format`/JSON-schema enforcement is currently *inactive* — the model can emit free-form text (GitHub issue #20345). Disable thinking for any call that must return strict JSON.
2. **Fails open on bad grammar.** If JSON-schema→GBNF conversion fails, llama-server has been observed to silently produce *unconstrained* output instead of erroring (issue #19051). Never assume output is valid — always parse defensively.
3. **`x? x? x?` repetition pattern** (allowing up to N optional repeats) can blow up sampling time via deep token stacks. Use explicit array/repetition rules instead.

By default converted objects forbid extra keys; set `"additionalProperties": true` to allow them. Only a subset of JSON Schema is supported by `json-schema-to-grammar.py`.

## Why It Matters
Glory's HYPE stack (`start-llama.bat`, `start-qwen.bat`) extracts structured data from local models: the v2 Narrative Engine and v3 Chart Reader both depend on parsing JSON out of model output. Today that relies on the model *choosing* to format correctly plus a defensive parser catching failures (`parse_chart_read`). Grammar constraints move that guarantee upstream — the model becomes structurally *incapable* of emitting malformed JSON, eliminating retry loops and parse-failure paths for the local-model legs.

Crucially, our defensive parsers stay necessary anyway because of gotcha #2 (fail-open) and #1 (thinking models). The actionable rule for Glory: **constrain at the sampler AND parse defensively** — belt and suspenders. The cost is a modest, usually-negligible sampling slowdown; the win is deterministic schema conformance on a 12GB RTX 3060 with no API dependency.

## Source
- https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- Fail-open on bad grammar: https://github.com/ggml-org/llama.cpp/issues/19051
- Thinking bypasses enforcement: https://github.com/ggml-org/llama.cpp/issues/20345

## Connected To
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-05-18-gemma-proxy-integration]]
- [[2026-05-18-prompt-cleaning-pattern]]
