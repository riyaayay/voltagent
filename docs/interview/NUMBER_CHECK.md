# VoltAgent — Number & Evidence Cross-Check Table
*Every numerical claim in the interview guide cross-checked against actual files in the repository.*

| Claim Description | Value Reported | Source File Path | Line / Key Reference | Verified? | Notes / Discrepancy Flag |
|---|---|---|---|---|---|
| Post-F-022 Retrieval Recall@5 (All) | **97.9%** (47 / 48) | `results/retrieval_eval_after_f022.json` | `splits.all.fused_recall` = 0.979; `docs/RESULTS.md:64` | YES | 1 query missed out of 48 non-null queries |
| Post-F-022 Fused MRR (All) | **0.903** | `results/retrieval_eval_after_f022.json` | `splits.all.fused_mrr` = 0.903; `docs/RESULTS.md:64` | YES | Top-1 in 41 of 48 queries |
| Pre-F-022 Retrieval Recall@5 (All) | **95.8%** (46 / 48) | `results/retrieval_eval_before_f022.json` | `splits.all.fused_recall` = 0.958; `docs/RESULTS.md:50` | YES | 350-token chunks baseline |
| Pre-F-022 Fused MRR (All) | **0.920** | `results/retrieval_eval_before_f022.json` | `splits.all.fused_mrr` = 0.920; `docs/RESULTS.md:50` | YES | MRR dropped slightly post-F-022 as chunk count tripled |
| Post-F-022 Hindi Devanagari Recall@5 | **85.7%** (6 / 7) | `results/retrieval_eval_after_f022.json` | `splits['lang:hi'].fused_recall` = 0.857; `docs/RESULTS.md:67` | YES | BM25 sparse recall was 0.0% (0/7) |
| Pre-F-022 Hindi Devanagari Recall@5 | **71.4%** (5 / 7) | `results/retrieval_eval_before_f022.json` | `splits['lang:hi'].fused_recall` = 0.714; `docs/RESULTS.md:53` | YES | Lifted by +14.3% absolute post-F-022 |
| Post-F-022 English Retrieval Recall@5 | **100.0%** (33 / 33) | `results/retrieval_eval_after_f022.json` | `splits['lang:en'].fused_recall` = 1.0; `docs/RESULTS.md:66` | YES | Sparse BM25 achieved 100.0% alone |
| Post-F-022 Hinglish Retrieval Recall@5 | **100.0%** (8 / 8) | `results/retrieval_eval_after_f022.json` | `splits['lang:hinglish'].fused_recall` = 1.0; `docs/RESULTS.md:68` | YES | BM25 alone was 100.0%, dense was 87.5% |
| Total Non-Null Evaluation Queries in Gold | **48 queries** | `data/eval/gold.json` | 48 items with non-null `expected_doc_id` | YES | 32 English real, 15 Hindi/Hinglish, 1 adversarial |
| Total Queries in gold.json | **62 queries** | `data/eval/gold.json` | Total items in `gold.json` | YES | 48 non-null + 10 out-of-scope probes + 4 adversarial |
| Frozen 10-Wrong Benchmark Flagged Rate | **8 / 10 (80.0%)** | `results/verifier_eval_frozen.txt` | Line 85; `results/verifier_eval_after_f022.json:9` | YES | W01 and W02 missed; W03-W10 flagged |
| Frozen Correct Benchmark False Flags | **0 / 20 (0.0%)** | `results/verifier_eval_frozen.txt` | Line 88; `results/verifier_eval_after_f022.json:153` | YES | 20 of 20 passed verification |
| Held-Out 60 Wrong Flag Rate | **27 / 30 (90.0%)** | `results/verifier_eval_heldout_60.json` | `metrics.wrong_flag_count` = 27, `wrong_flag_total` = 30; `docs/RESULTS.md:110` | YES | Real: 21/22 (95.5%), Synthetic: 6/8 (75.0%) |
| Held-Out 60 False Flag Rate | **4 / 30 (13.3%)** | `results/verifier_eval_heldout_60.json` | `metrics.false_flag_count` = 4, `false_flag_total` = 30; `docs/RESULTS.md:111` | YES | All 4 false flags occurred on real PDFs (18.2%) |
| Total Real PDF Documents | **5 documents** | `data/raw/real/` | `docs/CORPUS.md:4` | YES | OCPP 2.0.1 (spec + appendices), Pulsar (guide + install), OSHA 3075 |
| Total Real PDF Pages | **711 pages** | `docs/CORPUS.md:5` | Sum of page counts in `corpus_inventory.json` | YES | 481 + 39 + 8 + 112 + 71 = 711 |
| Total Extractable Real Pages | **710 pages (99.86%)** | `docs/CORPUS.md:6` | `docs/CORPUS.md:17` | YES | 1 blank/cover page in wallbox install guide skipped |
| Total Chunks Indexed (Post-F-022) | **4,857 chunks** | `results/clean_clone_run.txt` | Line 65, 84; `data/index_cache/dense.pt` | YES | Real: 4,850 chunks, Synthetic: 7 chunks |
| Total Chunks Indexed (Pre-F-022) | **1,641 chunks** (1,634 real + 7 synth) | `docs/RESULTS.md:40`, `docs/RESULTS.md:45` | `results/corpus_inventory.json` | YES | Evaluated under 350-token chunk window |
| Verifier Confidence Threshold | **0.55** | `voltagent/config.py` | Line 41; `results/verifier_eval_frozen.txt:5` | YES | Calibrated on `dev.json` |
| RRF Constant $k$ | **60** | `voltagent/config.py` | Line 38; `voltagent/retrieval/fusion.py:17` | YES | Standard Cormack et al. constant |
| Retrieval Top-k Parameters | **Sparse=10, Dense=10, Fused=6** | `voltagent/config.py` | Lines 35-37 | YES | top_k_sparse=10, top_k_dense=10, top_k_fused=6 |
| Maximum Query Text Length | **2,000 characters** | `voltagent/config.py` | Line 56; `voltagent/api/main.py:44` | YES | HTTP 400 rejected if exceeded |
| Unit Tests Passing in Suite | **149 passed, 3 xfailed, 0 failed** | `results/pytest_final.txt` | Line 1; `docs/RESULTS.md:23` | YES | xfails document known F-021/F-022 constraints |
| End-to-End Latency Percentiles (p50/p95/p99) | **NOT IN REPO** | N/A | No aggregated `e2e_live.csv` stored | NOT IN REPO | Flagged in gap audit |
| Live Deployed Cloud URL | **NOT IN REPO** | N/A | Space parked in `deploy/huggingface/` | NOT IN REPO | Flagged in gap audit (runs fully locally on `http://127.0.0.1:8000`) |
| Native Speaker Review of Hindi Lexicon | **NOT IN REPO** | `voltagent/agents/numeric_gate.py` | Line 19: "UNREVIEWED by a native speaker" | NOT IN REPO | Flagged in gap audit |

