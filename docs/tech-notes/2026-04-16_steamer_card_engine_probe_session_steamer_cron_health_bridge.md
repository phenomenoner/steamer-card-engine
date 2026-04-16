# 2026-04-16 — steamer-card-engine probe-session steamer-cron-health bridge

## Verdict

`operator probe-session` now has a truthful named upstream adapter.
The first production-worthy source is `steamer-cron-health`, not a new broker-side control path.

## Why this slice landed

The real gate was not inventing a richer seed snapshot.
It was wiring one truthful upstream source into the canonical probe contract so `probe-session -> preflight-smoke -> cron` could stop depending on fixtures.

## What changed

- Added `--probe-source` and `--probe-date` to:
  - `auth inspect-session`
  - `operator probe-session`
  - `operator preflight-smoke`
- Added named source adapter: `steamer-cron-health`
  - reads `/root/.openclaw/workspace/.state/steamer/cron-health/<YYYYMMDD>/stages/`
  - translates `aws_auth`, `ec2_power_on`, `ec2_kickoff`, `ec2_verify` into the canonical `session_status + connections` shape
- `probe_json` remains the manual/fixture override and takes precedence over `probe-source`
- `preflight-smoke` blocker codes now preserve failure family:
  - `auth`
  - `stale`
  - `disconnected`
  - `capability-mismatch`
- `boundary.broker_connected` now reflects the actual broker connection state instead of staying frozen at seed false

## Truth boundary

This adapter proves:
- marketdata readiness
- broker-attached runtime readiness

It does **not** independently prove account-query connectivity.
So the account surface remains explicit and non-assertive even when broker + marketdata are green.

## Verification receipts

- `uv run pytest -q tests/test_cli.py` -> `27 passed`
- `uv run steamer-card-engine operator probe-session --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --probe-source steamer-cron-health --probe-date 20260416 --json`
  - `probe_source=steamer-cron-health:20260416`
  - `marketdata=connected`
  - `broker=connected`
- `uv run steamer-card-engine operator preflight-smoke --deck examples/decks/tw_cash_intraday.toml --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --probe-source steamer-cron-health --probe-date 20260416 --state-file .state/operator_posture.json --receipt-dir .state/operator_receipts --json`
  - `preflight_status=ready`
  - `blockers=[]`

## Claude second-brain review

Standalone Claude CLI review verdict: conditional accept.
Main findings were:
- do not overclaim account-query connectivity from `ec2_verify`
- document `probe_json` precedence over `probe-source`
- protect missing-stage fallback with tests

Those follow-ups were folded back into the same slice before closure.

## Topology statement

- Runtime topology changed: yes, one named upstream truth adapter now feeds the canonical probe contract
- Scheduler topology changed: not in this slice alone
- Live authority changed: no
