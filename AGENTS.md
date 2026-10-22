# VoltAgent: agent rules
Voice-first verified RAG copilot for EV charger technicians. Live electrical
equipment: a confident wrong answer is the worst outcome.

## Read first, every session
docs/SAFETY_CONTRACT.md, docs/STATUS.md, docs/PROGRESS.md, docs/FAILURES.md

## Hard rules
- Every request ends in outcome A, B, or C (see SAFETY_CONTRACT). Never anything else.
- Never weaken, delete, or special-case a test to make it pass.
- Tune on the dev split only. Never look at heldout until Phase 5.
- Fix at the root cause. Every fix gets a regression test that fails if reverted.
- Log every failure found in docs/FAILURES.md.
- No force push, no history rewrite, no secrets in commits, ask before adding heavy deps.

## Commands
(make up / make test / make eval / make chaos-query Q="..." : fill in after Phase 0)

## Layout
See docs/ARCHITECTURE.md