# Execution packet — steamer-card-engine live observer sidecar v0

## Objective

Build the first truthful **read-only browser observer** for one `steamer-card-engine` live(sim) engine instance.

The opening proof is not "full remote trading" and not "generic dashboard polish".
The opening proof is:

> a browser can open one live(sim) session and watch chart + decision timeline + orders/fills + position + health update coherently from a sanitized observer contract.

## Authoritative inputs

- `docs/tech-notes/2026-04-23_steamer_card_engine_live_observer_sidecar_v0_contract.md`
- `docs/ARCHITECTURE.md`
- `docs/tech-notes/2026-04-06_steamer_card_engine_mission-control_dashboard_v0_build-packet.md`
- `docs/tech-notes/2026-04-09_steamer_dashboard_tabbed_strategy_powerhouse_surface.md`
- `docs/tech-notes/2026-04-15_steamer_card_engine_preflight_smoke_seed.md`
- `docs/tech-notes/2026-04-16_steamer_card_engine_probe_json_inlet.md`

## Topology note

Topology unchanged.

This packet introduces a **sidecar observer product slice** only.
It does not grant browser control authority and does not replace the existing CLI/operator/runtime surfaces.

## Bounded slice

### In scope
- one engine instance
- one active symbol
- one session observer page
- bootstrap snapshot API
- candle/history API
- append-only observer stream
- chart markers for entry/exit/pending order
- position / open orders / last fill cards
- engine health strip
- decision/event timeline
- explicit stale/degraded notices
- mock/replay-safe local fixture mode for frontend/backend development

### Out of scope
- write actions of any kind
- pause/restart/arm/disarm controls
- replay workstation / backtest comparison overlays
- multi-engine / multi-symbol workspace
- deep PnL analytics
- raw strategy/rationale dumps
- direct browser access to broker/execution/engine data stores

## Boundary rules

### Public-repo-safe only
Anything committed to the public repo must be safe if leaked.

Allowed:
- UI code
- read-only projection/API shell
- sanitized schemas and types
- mocked/synthetic fixtures
- launch/run docs

Forbidden:
- private adapter code
- real payload captures
- real account/session/order-routing identifiers
- hostnames/VPC topology/internal URLs
- alpha-bearing thresholds/features/confidence fields
- screenshots/logs from real live(sim)

### Structural read-only rule
The observer service must be structurally incapable of writes.
If a design requires reusing execution write paths "temporarily", stop and recut the slice.

## Suggested file shape

- `frontend/` observer page + components
- `src/steamer_card_engine/observer/` projection models + API layer
- `src/steamer_card_engine/observer/schema.py` or equivalent sanitized event contract
- `tests/test_observer_*.py`
- `tests/frontend/*` for minimal UI contract verification
- mock fixtures under a clearly synthetic path

## First artifact expected

Before touching polished UI, produce the observer contract and one mocked bootstrap/stream pair:
- schema/types for snapshot + events
- a tiny mock projection service or fixture loader
- one browser page that renders candles + markers + right-rail state from synthetic data

That is the first honest proving edge.

## API contract (seed)

- `GET /api/observer/sessions/{session_id}/bootstrap`
- `GET /api/observer/sessions/{session_id}/candles?limit=500`
- `GET /api/observer/sessions/{session_id}/timeline?limit=200`
- `WS /api/observer/sessions/{session_id}/stream`

## Event contract seed

Required envelope fields:
- `schema_version`
- `session_id`
- `engine_id`
- `seq`
- `event_id`
- `event_time`
- `ingest_time`
- `partial_data`
- `freshness_state`

Required event families:
- `candle_bar`
- `decision_recorded`
- `order_submitted`
- `order_acknowledged`
- `fill_received`
- `position_updated`
- `engine_state_changed`
- `health_alert`
- `data_gap_detected`
- `operator_visible_note`

## Verifiers

### Must-pass
1. mocked/synthetic page loads locally
2. chart renders candle series and marker overlays from the same event sequence
3. refresh/reconnect rebuilds state from bootstrap + stream without duplicate drift
4. stale/degraded state is visibly surfaced from freshness metadata
5. read-only boundary check confirms no mutating routes or hidden control actions
6. payload scan confirms no forbidden fields in snapshot or stream

### Nice-to-have
- lightweight screenshot receipt for the synthetic page
- frontend unit test for marker/timeline reconciliation
- reconnect smoke for WebSocket/SSE fallback posture

## Stop-loss

Stop and report if any is true:
- contract design drifts into UI polish before schema/bootstrap/stream exist
- same root-cause hypothesis already had 2 meaningful attempts
- observer and execution paths start sharing write-capable plumbing
- live payload examples become necessary to keep moving
- the slice expands beyond one engine / one symbol / one page before the verifier passes

## Delivery posture

- contract-first
- read-only by structure, not by promise alone
- chart truth > terminal theater
- sanitization before live wiring
- future non-stop implementation should inherit this packet, not re-decide the boundary mid-flight
