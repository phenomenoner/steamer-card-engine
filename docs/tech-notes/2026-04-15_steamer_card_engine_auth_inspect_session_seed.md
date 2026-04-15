# 2026-04-15 — steamer-card-engine auth inspect-session seed

## Why this slice landed

The product contracts have long promised `auth inspect-session --json`, but repo truth only exposed auth-profile inspection and operator posture.
That left a real gap between capability-posture docs and an actual inspectable session surface.

## What is now executable

- `steamer-card-engine auth inspect-session --auth-profile ... [--trading-day-status open|closed|unknown] [--json]`

The command currently exposes a **logical session** derived from the chosen auth profile plus operator-provided trading-day status.
It does not log in, does not attach broker connectivity, and does not claim a live runtime session exists.

## Returned truth surfaces

- session identity (`session_id`, `account_no`, `auth_mode`)
- capability posture (`marketdata_enabled`, `account_query_enabled`, `trade_enabled`)
- seed health posture (`logical-profile-only`, `marketdata_connection=not-connected`, `broker_connection=not-connected`)
- trading-day gate (`open|closed|unknown`) with explicit `live_allowed`
- boundary disclosure (`prepared-only`, `broker_connected=false`)

## Why this matters

This gives the next broker-preflight slice a real inspection surface to build on.
A later broker-connected preflight lane can replace the seed health/source fields without rewriting the contract shape from scratch.

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: no
- CLI auth/session surface changed: yes
