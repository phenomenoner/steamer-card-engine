# 2026-04-16 — steamer-card-engine probe freshness / receipt contract

## Verdict

Land the smallest truthful contract patch on the existing operator JSON surface.
Do not redesign runtime state. Extend `probe-session`, `preflight-smoke`, and `live-smoke-readiness` so they say both readiness and freshness / receipt provenance.

## What changed

- `operator probe-session` now emits:
  - `probe_freshness`
  - `probe_receipt`
- `operator preflight-smoke` now bubbles the same metadata into its top-level JSON payload.
- `operator live-smoke-readiness` now carries the same metadata from the preflight gate, for both ready and blocked outcomes.
- `auth inspect-session` / named probe adapters now preserve the same truth under `boundary.probe_freshness` and `boundary.probe_receipt`.

## Truth boundary

- `steamer-cron-health` reports source-backed receipt pointers and observed timestamps from the stage receipt that actually drove the verdict.
- `--probe-json` reports the consumed file path as the receipt pointer, and only reports `observed_at` when the probe payload actually exposes a timestamp (`captured_at` or connection heartbeat).
- seed-only posture stays explicit:
  - `probe_freshness.status=seed-unverified`
  - `probe_receipt.kind=seed`
- no broker authority is claimed by this slice.

## Why this is the right slice

The gap was not missing readiness logic.
The gap was that operator truth could say `ready` or `blocked`, but not clearly answer:

- how fresh is this judgment?
- which receipt/file did it come from?

This patch closes that contract gap without expanding runtime scope.

## Verification receipts

- `uv run pytest -q tests/test_cli.py`
- `uv run ruff check src/steamer_card_engine/cli.py tests/test_cli.py`
- repo smoke:
  - `uv run steamer-card-engine operator probe-session --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --json`
  - `uv run steamer-card-engine operator preflight-smoke --deck examples/decks/tw_cash_intraday.toml --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --probe-json examples/probes/session_health.connected.json --json`

## Topology statement

- runtime topology changed: no
- contract truth changed: yes
- live authority changed: no
