# M1 Comparator Summary

- status: **FAIL**
- baseline run: `replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260315T082717Z` (baseline-bot)
- candidate run: `replay-sim_tw-paper-sim-twse-2026-03-12-full-session_candidate_20260315T082719Z` (steamer-card-engine)
- scenario_id: `tw-paper-sim.twse.2026-03-06.full-session`

## Hard fail reasons
- scenario_id mismatch: baseline=tw-paper-sim.twse.2026-03-06.full-session candidate=tw-paper-sim.twse.2026-03-12.full-session
- scenario_fingerprint mismatch: baseline=b6d0df4a4635e7cbebf83677bedf69a97e1ed339061b9c9af1d89908765ec9df candidate=6cd13ee0982eb797a21c3514294f2fb077a5dcdf177d94c3b6fd113189da4768

## Counts scaffold
- fills: baseline=0 candidate=0
- orders: baseline=0 candidate=0
- intents: baseline=200 candidate=200
- risk decisions: baseline=100 candidate=100

## Notes
- This is a comparator skeleton; per-symbol exposure/exit diffs are scaffold placeholders.
- execution_model hash mismatch remains a hard stop.
