# 2026-04-16 — steamer-card-engine broker-preflight contract skeleton

## Why this slice landed

`inspect-session` and `preflight-smoke` existed, but their health disclosure still depended on seed-local placeholder fields.
That was enough for truthful blocking, but not yet enough to guarantee a clean swap into a broker-connected implementation.

## What changed

The repo now treats broker-preflight health as a stable contract shape:

- `session_status.session_state`
- `session_status.renewal_state`
- `session_status.connections.marketdata`
- `session_status.connections.broker`
- `session_status.connections.account`

Each connection carries:
- `state`
- `detail`
- `last_heartbeat_at`
- `last_error`

Seed runtime still reports `not-connected`, which is correct.
The point of this slice is not activation. The point is that later broker/session integration can replace the source of truth without changing the operator-facing contract.

## Code alignment

- `auth inspect-session` now emits the stable `session_status + connections` shape
- `operator preflight-smoke` consumes that shape rather than ad hoc string fields
- adapter base models now include health/status dataclasses that match the future replacement path

## Boundary statement

- still prepared-only
- still not broker-connected
- still no trading-day cron activation
- but the next broker-connected slice is now a source replacement problem, not a contract rewrite problem

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: no
- Contract truth changed: yes
