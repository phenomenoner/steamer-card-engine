# 2026-04-17 — dashboard runtime dispatch truth adjudication

- status: done
- topology: unchanged
- scope: adjudicate whether `tests/test_dashboard.py` should expect `skipped_not_dispatchable` or `misconfigured_activation` for the current strategy-pipeline runtime surface

## Verdict
`misconfigured_activation` is the truthful expected state.

## Why
The runtime handoff shadow currently reports:
- requested / selected campaign: `2026-03-tw-intraday-shadow-vcp`
- runtime dispatch state: `misconfigured_activation`
- activation mismatch: `true`
- suggested fallback campaign: `2026-04-timesfm-regime-rank-assist`

Primary receipt:
- `/root/.openclaw/workspace/.state/steamer/autonomous_slow_cook_handoff_shadow.v1.json`

The requested campaign is not dispatchable at runtime because it is held at `phase=operator-gate` and `status=paused`. The dashboard selector logic also excludes `operator-gate` campaigns from fallback dispatchable candidates. That makes this an activation-target mismatch, not a generic skipped-not-dispatchable branch.

## Change made
- Updated `tests/test_dashboard.py` to assert `misconfigured_activation`
- Added assertions for:
  - `suggested_campaign_id == 2026-04-timesfm-regime-rank-assist`
  - `activation_mismatch is True`

## Boundary note
This change does **not** upgrade live-readiness.
It only aligns repo verifier expectations with the current runtime truth surface.
Real-money smoke remains unexecuted.

## Verification
- `uv run pytest -q tests/test_dashboard.py`

## Residual
- This patch aligns the current runtime-truth branch only. A dedicated test for the genuine `skipped_not_dispatchable` branch should still be added so that path does not go dark.
- If the runtime activation target is later changed to a dispatchable campaign, the truthful state may change again and the tests should move with the runtime receipt, not by assumption.
