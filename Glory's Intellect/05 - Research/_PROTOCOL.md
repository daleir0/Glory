---
type: protocol
created: 2026-05-18
---
# Research Protocol — How Knowledge Enters Glory's Brain

## When to Write a Research Note

Write one whenever:
- You learned how a system works (e.g., how WSL mirrored networking resolves DNS)
- You debugged something non-obvious and found the root cause
- You encountered a tool/API behavior that wasn't documented clearly
- A concept came up in conversation that Glory should permanently know
- You confirmed or disproved something previously uncertain
- A task revealed a pattern that will repeat

**Rule: if it took effort to learn, it belongs here. Write mid-task if needed — don't wait.**

---

## Format

Use the template: [[08 - Templates/research|Research Note Template]]

Required fields:
- `domain:` — which folder it belongs in (AI, Programming, Systems, Hardware, Mathematics, Philosophy)
- `confidence:` — `verified` (tested/sourced), `probable` (strong inference), `uncertain` (needs confirmation)
- `source:` — where it came from (URL, observation, error message, documentation)

---

## File Naming

```
YYYY-MM-DD-kebab-slug.md
```

Place inside the correct domain folder.

Examples:
- `05 - Research/Systems/2026-05-17-wsl-mirrored-network-dns.md`
- `05 - Research/AI/2026-05-18-lm-studio-reasoning-content-field.md`
- `05 - Research/Programming/2026-05-18-hermes-cli-flag-ordering.md`

---

## After Writing

1. Add a row to the domain `_INDEX.md` notes table
2. Add a row to `05 - Research/_INDEX.md` → Recent Additions
3. Link from any related notes already in the vault
4. If it's major (affects multiple sessions), link from `07 - Atlas/INDEX.md`

---

## The Standard

A good research note means: if you read nothing else, you know exactly what this is, why it matters, and can verify it yourself. No filler. No vague summaries. Just the precise, sourced fact.
