# Evaluation Protocol & Frozen Benchmark Specifications

Date: 2026-11-01
Status: FROZEN

## 1. Integrity Rules & Evaluation Constraints

To prevent gaming or overfitting to evaluation benchmarks:
1. Three completely disjoint sets are maintained under `data/eval/`:
   - `dev.json`: For tuning verifier rules and similarity thresholds.
   - `test_wrong_10.json`: 10 frozen deliberately wrong cases covering critical failure modes.
   - `test_correct.json`: 20 frozen correct cases drawn >= 50% from real documents.
2. The benchmark sets (`test_wrong_10.json` and `test_correct.json`) are frozen with SHA-256 hashes recorded below **BEFORE** any verifier code or threshold is modified.
3. Tuning is performed strictly on `dev.json`. The frozen test sets are evaluated only during benchmark runs, with all run outputs preserved in `results/`.
4. Success criteria for Claim (C):
   - Wrong-case flag rate $N/10 \ge 8$ ($80\%$).
   - False-flag rate on correct answers $\le 20\%$.
   - A verifier that flags everything is a failure, not a pass.

---

## 2. Frozen Dataset Hashes (SHA-256)

| File | SHA-256 Checksum | Cases | Real Document Ratio |
| :--- | :--- | :--- | :--- |
| `data/eval/test_wrong_10.json` | `dd0e1ce1b3a516eae81816793072f681cb55315fae3dfed8860f5e8d07d09b51` | 10 | 70% (7/10) |
| `data/eval/test_correct.json` | `511a4ef2519b25fb010ebfacc235f8fe37cdaaf026ef6b4fc5bf7d290bfbb6dd` | 20 | 70% (14/20) |
| `data/eval/heldout_60.json` | `0a758d62c985b1d62b7aeedd02e326fb1ccc01f9cac9ad4840540fc1238b8c69` | 60 | 73.3% (44/60) |
| `data/eval/dev.json` | `13e52fc997a081b5efa8ccefcdd2bad7fc40d0435468b14ac41965a9cd4d13a3` | 5 | 60% (3/5) |
| `data/eval/gold.json` | `8dedf9829f7010520c5a28015bb84bc3b7353629fa8eb63655bb3f6932cd2d36` | 62 | 75.8% (47/62) |

---

## 3. Failure Mode Coverage in `test_wrong_10.json`

| Case ID | Failure Mode | Source | Perturbation Technique |
| :--- | :--- | :--- | :--- |
| `W01_wrong_error_code_meaning` | Wrong error-code meaning | Real (`charger-error-codes` p.5) | Perturbed steady yellow LED halo (locked) to mean error. |
| `W02_swapped_numeric_value` | Swapped numeric value | Real (`ev-safety-compliance` p.12) | Swapped 5 mA harmless let-go threshold to 50 mA. |
| `W03_wrong_unit` | Wrong unit | Real (`wallbox-pulsar-plus-install` p.9) | Changed 1.40 m mounting height to 1.40 inches. |
| `W04_negation_flip` | Negation flip | Real (`charger-error-codes` p.5) | Flipped "locked and will not charge" to "unlocked and will charge normally". |
| `W05_wrong_ocpp_field_message` | Wrong OCPP field/message | Real (`ocpp-2.0.1-spec` p.128) | Claimed `seqNo` belongs to `BootNotificationRequest` rather than `TransactionEventRequest`. |
| `W06_citation_real_wrong_chunk` | Citation to real but wrong chunk | Real (`charger-error-codes` p.5) | Pulsar Plus LED claim cites OSHA general electrical standard chunk. |
| `W07_citation_nonexistent_chunk` | Citation to nonexistent chunk | Synthetic (`voltco_ac22_specs` p.1) | Cites non-existent chunk bracket `[99]`. |
| `W08_uncited_claim` | Uncited claim | Synthetic (`voltco_err_codes` p.1) | Emitted answer text with zero citation brackets. |
| `W09_fluent_fabrication` | Fluent fabrication (no corpus basis) | Synthetic (unsupported) | Invented procedure for liquid nitrogen cryogenic coolant lines. |
| `W10_hindi_wrong_answer` | Hindi-language wrong answer | Real (`ev-safety-compliance` p.12) | Falsely claimed 1 mA current causes fatal cardiac arrest in Hindi. |

---

## 4. Evaluation Execution Procedure

1. **Deterministic Verifier Eval**:
   - Executes via `scripts/evaluate_verifier.py`.
   - Injects generation results directly into `run_verifier_agent` without requiring live LLM API keys.
   - Verifies exact claim-level scoring, numeric gate verification, citation bounds, and threshold flags.
2. **End-to-End Pipeline Eval**:
   - Executes via `scripts/evaluate_retrieval.py` and `run_pipeline` when an LLM API key (`GEMINI_API_KEY` or `OPENAI_API_KEY`) is configured.
   - If no live key is present, deterministic eval is executed and reported without fabricated live metrics.

