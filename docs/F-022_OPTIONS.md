# F-022 options: chunks (350 tiktoken tokens) are longer than the embedder window (128 wordpieces)

**Status: proposal. Nothing implemented. Waiting for owner OK because it touches chunking and corpus design.**

## What is established (measured, 2026-10-23)
- `paraphrase-multilingual-mpnet-base-v2`, `max_seq_length = 128`. Text beyond that is silently dropped.
- Two full-size chunks differing only in a number placed after the window have cosine 1.0000 (probe; committed as `tests/test_embedder_window.py`).
- **Which components are blind:** the dense leg (query vs chunk vectors) and the verifier (cosine of claim vs whole chunk). **The BM25 leg is not truncated**: it indexes the full chunk text. So hybrid retrieval is only partly affected; the verifier is fully affected.
- Not yet measured: how often real corpus facts sit past the window (needs Phase 1 corpus + Phase 2 baseline).

## Options

| | A. Shorter chunks | B. Per-window verification | C. Deterministic full-text numeric/code gate | D. Long-context embedder |
|---|---|---|---|---|
| What | Re-chunk so every chunk fits the window, measured with the embedder's own tokenizer (about 100 wordpieces), not tiktoken | Verifier splits the cited chunk into overlapping windows of at most 128 wordpieces and scores the claim against the best window | Extract numbers+units, error codes, model names from each claim; require exact match in the FULL cited chunk text (no embeddings). Already required by principle 4 | Replace the embedder with a long-context multilingual model (for example bge-m3, 8k window) |
| Fixes dense retrieval blindness | Yes | No | No | Yes |
| Fixes verifier blindness | Yes (chunk = window) | Yes (for semantic support) | Only for numbers/units/codes/models | Yes |
| Changes chunking / reindex | Yes, full reindex | No | No | Yes, new collection, new dimension |
| Main cost / risk | About 3x more chunks; warnings separated from their procedures and numbers from units unless overlap/sectioning is smart; tables get fragmented | 3-4x more encodes per claim (latency); still blind to negation/qualifier subtleties | Does not catch wrong-model, negation or unsupported prose claims; needs a robust unit/number parser (Devanagari numerals, "E one-oh-one") | About 2 GB model, heavier CPU latency, new heavy dependency (owner approval needed), Hindi behaviour must be re-measured |
| Measure before choosing | Recall@k and MRR on golden items with late-position facts; chunk count; share of safety values co-located with their warning | Verifier precision/recall on the labelled claim set with late-position facts; verifier p50/p95 latency | Precision/recall of the gate on subtly-wrong-number/unit claims; false-rejection rate on correct paraphrases | Recall@k, MRR, Hindi cross-lingual recall, latency, memory |

## Recommendation
**C + B first, defer A/D until the baseline says they are needed.**
1. **C (numeric/code gate) is mandatory regardless** (principle 4) and is the only option that makes "wrong number/unit can never be outcome A" a deterministic guarantee. It also closes F-001 without relying on any embedding.
2. **B** removes the verifier's blind spot with no change to chunking, the index or the corpus design.
3. Hold **A/D**. BM25 still sees the whole chunk, so retrieval damage may be smaller than the verifier damage. Phase 1 plants late-position facts in the corpus, and Phase 2 will measure dense-only vs BM25-only vs fused recall on them. If dense recall on late-position items is materially worse, then choose A (small-to-big: index small child chunks, pass the parent section to the LLM) or D with that evidence.

Risk of this recommendation: it leaves dense retrieval blind to late text until Phase 2 data exists. Acceptable because Phase 2 happens before any fix is declared done, and the BM25 leg covers exact codes and numbers.
