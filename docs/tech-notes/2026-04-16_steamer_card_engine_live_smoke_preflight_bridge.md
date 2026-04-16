# 2026-04-16 — steamer-card-engine live-smoke preflight bridge

## Why this slice landed

`operator preflight-smoke` and `probe-session` already consumed the truthful probe contract (`--probe-json` / `--probe-source steamer-cron-health`), but `operator live-smoke-readiness` still ran as a seed-only sequence.

That mismatch let the bounded smoke lane skip the same upstream posture gate used by `probe-session -> preflight-smoke -> cron`.

## What changed

- `operator live-smoke-readiness` now accepts:
  - `--trading-day-status`
  - `--probe-json`
  - `--probe-source`
  - `--probe-date`
- before running arm/submit/flatten smoke steps, it runs the canonical preflight gate and records a `preflight-smoke-gate` step in the smoke bundle.
- when preflight is blocked, live-smoke exits with code `4` and returns a blocked smoke payload instead of pretending readiness.
- blocked runs still write the operator state file baseline through preflight inspection, but do not emit action receipts or enter the bounded smoke sequence.
- when preflight is ready, live-smoke continues unchanged through the bounded prepared-only smoke sequence.

## Truth boundary

- still prepared-only
- still no live trading
- still no auth reset/runtime mutation
- `steamer-cron-health` readiness remains truthful about account surface limits (account stays `not-connected` in that adapter)

## Verification

- `uv run pytest -q tests/test_cli.py -k "live_smoke_readiness"`
- `uv run pytest -q tests/test_cli.py -k "probe_session or preflight_smoke or live_smoke_readiness"`
- `uv run steamer-card-engine operator live-smoke-readiness --deck examples/decks/tw_cash_intraday.toml --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --probe-json examples/probes/session_health.connected.json --state-file <tmp>/operator_state.json --receipt-dir <tmp>/receipts --json`
