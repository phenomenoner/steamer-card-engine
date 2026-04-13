# 2026-04-12 — strategy-pipeline runtime dispatch visibility and selector truth

- status: done
- topology: unchanged
- scope: expose runtime dispatch truth in strategy-pipeline surface, align campaign-control indicators to runtime dispatch state, and document selector policy reasoning

## What changed
- Replaced hard-coded campaign pointer in `strategy_pipeline.py` with selector logic that:
  - reads runtime handoff shadow (`.state/steamer/autonomous_slow_cook_handoff_shadow.v1.json`)
  - resolves runtime target from activation/dispatch payload
  - falls back to campaign index order when runtime target is unavailable
  - emits explicit `runtime_campaign_selection` metadata (`policy`, `requested_campaign_id`, `selected_campaign_id`, `selection_reason`, `selected_entry_present`)
- Added runtime dispatch truth into pipeline/control outputs:
  - `control_plane.runtime_dispatch`
  - `control_plane.runtime_activation`
  - `control_plane.runtime_campaign_selection`
- Added runtime-facing fields into campaign controller section output:
  - `campaign_state.runtime_dispatch`
  - `campaign_state.selection`
- Updated campaign readiness fields to reflect runtime truth:
  - `research_autonomous` and `attach_autonomous` now gate on runtime dispatch `state == applied` + campaign dispatch attempt
  - verdict now reports `research-autonomous-{yes|no} / attach-autonomous-{yes|no}` from runtime-aware readiness
- Updated strategy pipeline frontend panel (`Campaign Controller` + `Handoff Gate`) to show:
  - runtime dispatch state
  - runtime requested/selected/suggested campaign ids
  - fallback_used
  - activation_mismatch
  - selection policy/reason
- Updated tests in `tests/test_dashboard.py` to assert the runtime dispatch visibility fields and corrected selector outcome with current runtime truth.

## Verification
- `uv run python -m py_compile src/steamer_card_engine/dashboard/strategy_pipeline.py`
- `uv run pytest tests/test_dashboard.py -q`
- `cd frontend && npm run build`
- `python3 projects/steamer/tools/steamer_autonomous_handoff_shadow_runtime_smoke.py`
- `python3 projects/steamer/tools/steamer_autonomous_slow_cook_operator_gate_resume.py`

## Truth / boundary notes
- no runtime topology edits
- no attach-autonomous activation wiring introduced
- no capital posture/capital-gated control changes
- runtime truth is preserved as-is; blocked/non-dispatchable paths are shown as hard facts (e.g., `skipped_not_dispatchable`, `activation_mismatch`, `suggested_campaign_id`).


## Follow-up in selector policy cut
- Added machine-readable selector metadata to runtime dispatch state (`selection`):
  - `policy_id`
  - `candidate_set` (ranked/priority-ready dispatch candidates)
  - selected/requested/suggested campaign IDs
  - `fallback_used` / `activation_mismatch` flags
- Formalized runtime dispatchability gate to exclude both `closed` and `operator-gate` in fallback candidate selection and policy metadata.
- Updated runtime smoke verifier with explicit policy assertions and candidate-set visibility checks (`steamer_autonomous_handoff_shadow_runtime_smoke.py`).

## Verification (updated)
- `uv run python -m py_compile src/steamer_card_engine/dashboard/strategy_pipeline.py`
- `uv run pytest tests/test_dashboard.py -q`
- `cd frontend && npm run build`
- `python3 projects/steamer/tools/steamer_autonomous_handoff_shadow_runtime_smoke.py` (from `/root/.openclaw/workspace/StrategyExecuter_Steamer-Antigravity`)

## Residual checks
- Ensure existing `.state/steamer/autonomous_slow_cook_handoff_shadow.v1.json` in production includes the new `runtime_dispatch.selection` fields after next run of `steamer_autonomous_slow_cook_handoff_shadow.py`.
