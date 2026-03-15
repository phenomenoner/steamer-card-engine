# M1 Evidence-Pack Acceptance Contract (Freeze v1)

Status: **frozen for M1 pre-sprint gate**  
Date (UTC): 2026-03-15

This contract defines what counts as an acceptable M1 evidence pack and what is explicitly disallowed.

## 1) Required scenario count

- Evidence pack must contain **at least 3 scenarios**.
- One scenario may be the canonical anchor; at least two must be additional scenarios.
- “3 scenarios” means **3 distinct `scenario_id`s** (not reruns of the same `scenario_id`).

## 2) Scenario identity + execution-model consistency (hard gates)

For every baseline/candidate pair in the evidence pack:

1. `scenario_id` must match exactly.
2. `scenario_fingerprint` must exist on both manifests and match exactly.
3. `execution_model` canonical hash must match exactly.
4. If any of the above fails, scenario status is **hard-fail** and that pair cannot be used as acceptance evidence.

## 3) Candidate provenance requirements (hard gates)

For every candidate bundle used as evidence:

- `run-manifest.json.provenance.engine_name` must identify candidate runtime origin (for current M1 lane: `steamer-card-engine-replay-runner`).
- `lane` must be `steamer-card-engine`.
- `capability_posture.trade_enabled` must be `false`.
- `config-snapshot.json` must include explicit emitter metadata for the candidate lane.

If provenance is missing or ambiguous, the scenario is **not acceptable evidence**.

## 4) Anti-gaming rules (explicit prohibitions)

The following invalidate acceptance claims:

- claiming candidate evidence when candidate artifacts are emitted by baseline converter lane without candidate provenance
- placeholder/converter truth-swaps (e.g., relabeling baseline-normalized outputs as candidate-native without disclosure)
- using compare outputs where hard-fail reasons were suppressed/ignored
- mixing scenario identities or execution models and presenting results as comparable

## 5) Required artifacts per scenario

Each accepted scenario must provide all pointers below:

1. baseline bundle path (or normalize receipt containing it)
2. candidate bundle path (or replay receipt containing it)
3. comparator output path (`compare-manifest.json`, `diff.json`, `summary.md`)
4. a short review note that states:
   - scenario id
   - baseline run id
   - candidate run id
   - comparator status + hard-fail count
   - any anomaly caveats that materially affect interpretation

## 6) M1 acceptance statement format

An M1 evidence-pack acceptance statement is valid only if it includes:

- scenario count proof (`>=3` distinct scenario IDs)
- per-scenario artifact pointers
- per-scenario short review notes
- explicit declaration that no anti-gaming rule was violated

## 7) Scope boundary reminder

This contract is for **M1 sim-only comparability**. It does not imply:

- live authority
- production readiness
- broker execution parity

All evidence remains under `trade_enabled=false` posture.
