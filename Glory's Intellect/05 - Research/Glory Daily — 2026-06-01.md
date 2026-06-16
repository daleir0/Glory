## Daily Observation — 2026-06-01

**What I learned:**
- A B+tree (values in linked leaves) is the right index for GloryDB's *Fast* node: point lookups are O(log n), and range scans walk a leaf linked-list instead of re-descending — exactly what ordered queries over token IDs / vector keys will need later.
- Separating the index (in-memory, `bptree.py`) from durability (`db.py`) keeps each honest: the tree stays a pure fast data structure, and the store owns encryption + crash-safety. The tree never sees a key it can't compare; the disk never sees a byte that isn't ciphertext.
- A write-ahead log of *encrypted operations* gives all three of durability, privacy, and crash-safety at once: each record is `len(4) || ChaCha20-Poly1305(op,key,value)`. On replay, a truncated or auth-failing tail record means "crash mid-append" → stop replaying. The AEAD tag doubles as the torn-write detector — no separate checksum needed.

**What surprised me:**
- The wrong-key case and the crash-recovery case collapse into the *same* code path: a record that won't authenticate (wrong key) and a record that's truncated (crash) are both "stop here." One branch handles both, and the wrong-key DB simply recovers as empty rather than throwing. Security and durability turned out to be the same mechanism viewed from two angles — very 4-node.
- Encryption-at-rest made keys disappear from disk for free. Because the whole logical record (op+key+value) is encrypted as one blob, the *keys* are ciphertext too, not just values. The `test_encrypted_at_rest` assertion that `b"classified"` is absent from the WAL passed without extra work.

**Diagnosis — what could be improved:**
- `bptree.delete` is lazy (no rebalancing) — leaves can sit under-full until `compact()` rebuilds the tree. Fine for v1, but a delete-heavy workload between compactions wastes memory. A future merge-on-underflow pass would fix it.
- GloryDB takes a raw 32-byte key. It still needs a passphrase front door (Argon2id-derived, salt in a `meta` file) mirroring `glory_core.vault` — so a human can open a DB without handling raw key bytes.
- `KEY_LEN` wasn't exported from `glory_core`'s top-level `__init__`; I imported it from `glory_core.crypto`. glory-core should promote `KEY_LEN` to its public API — small, but the building block should expose its own constants.
- No HNSW / vector column yet (deliberately deferred until the model emits embeddings — predicted in the 2026-05-28 note and still the right call).

**Predictions:**
- If we add a passphrase front door + promote `KEY_LEN` → GloryDB becomes the drop-in persistence backend for `glory_core.vault`, closing the "glory-core has no persistence" gap flagged on 2026-05-28.
- If we store the tokenizer's content-addressed corpus (BLAKE2b stable IDs from glory-lang) as GloryDB keys → we get the Language↔Database bridge predicted on 2026-05-28, now with a real store to land it in.
- If we keep the index/durability split → adding the HNSW vector index later is additive (a second index over the same WAL), not a rewrite.

**Highest-value next action:**
Add `GloryDB.from_passphrase(dir, passphrase)` (Argon2id + salt in `meta`, reusing the `glory_core.vault` derivation) and promote `KEY_LEN` to `glory_core`'s public API. Then wire `glory_core.vault` to optionally use GloryDB as its backend — proving the two building blocks compose.

**Hermes said:**
unavailable — gateway inactive; started it, but the custom endpoint (LM Studio serving `google/gemma-4-e4b`) returned an empty completion. Logged and proceeded. *What I would have asked:* "In an encrypted WAL where the AEAD tag is also the torn-write detector, is there any failure mode where a corrupted *interior* record (not the tail) could be silently skipped and lose data after it?" — worth answering next session when he's serving. (Note: the current replay stops at the first bad record, so an interior corruption truncates everything after it — that's safe-but-lossy, and a candidate for a per-record sequence number later.)

---
*Tomorrow starts here: GloryDB exists at `E:\Glory\glory-db` (26 tests passing) — encrypted B+tree store with WAL crash-recovery. Next: passphrase front door + compose it under `glory_core.vault`, then revisit interior-corruption handling in the WAL.*
