# 2026-04-23 — steamer-card-engine live observer sidecar v0 contract

## Verdict

The right next cut is a **read-only live observer sidecar** for `steamer-card-engine` on AWS live(sim), not a browser trading terminal and not a generic observability platform.

The opening proof is:

> one live(sim) engine instance can be opened in browser and observed truthfully, in near real time, with chart + order/position/timeline alignment, while keeping private strategy and infrastructure details out of the public repo and browser payloads.

## Why now

`steamer-card-engine` already has a real mission-control/dashboard line, but the current product edge is still mostly artifact- and replay-centered.

CK now wants a browser-openable surface that answers the live operator questions directly:
- what is the market doing now?
- what is the engine doing now?
- what orders / fills / positions exist now?
- is the run healthy or stale?

The real gate is therefore not another round of internal runtime plumbing. The real gate is a **safe product boundary** that can support a later non-stop implementation line without leaking alpha or accidentally expanding authority.

## Whole-picture promise

The sidecar should let an operator understand one live(sim) engine instance in about 10 seconds:
1. current market state
2. current engine state
3. current position / open orders / recent fills
4. latest decision and timeline context
5. freshness / staleness / degraded-state truth

Fake progress would be:
- shipping a pretty chart before the sanitized contract exists
- letting the browser consume raw engine or broker objects
- building a write-capable UI path "later" off the same service boundary
- calling the surface real-time while silent staleness is possible
- pushing example payloads, screenshots, or env hints that expose private internals

## Product cut

### What this is
- read-only browser observer for one engine instance
- terminal-like, operator-facing, low-noise UI
- chart + state + timeline surface
- private live data adapter -> sanitized projection -> browser UI
- public-repo-safe shell for future non-stop implementation

### What this is not
- browser order entry or cancel/replace surface
- remote control plane for engine/process management
- strategy explainability dump
- multi-engine / multi-symbol workspace in v1
- generic warehouse analytics product

## Hard boundary: public repo vs private runtime

### Public repo may contain
- UI code
- read-only API/projection service shell
- sanitized schema / TypeScript types / OpenAPI
- mock fixtures and replay-safe local demos
- docs for the observer contract and launch shape

### Public repo must not contain
- private adapter code or field-mapping logic
- real payload captures or prod logs
- real endpoint URLs / hostnames / network topology
- broker/session credentials, account identifiers, routing identifiers
- feature engineering details, thresholds, confidence values, alpha-bearing rationale
- screenshots that expose live values or internal structure

### Browser payload must be presentation-grade only
The browser should receive a **presentation-grade projection**, not an engine-grade event stream.

That means the browser payload must not include:
- raw broker/order objects
- exact account identifiers
- private model/feature values
- internal state-machine detail beyond coarse health states
- write-capable URLs/tokens/topics
- hidden control fields reserved for future use

## Recommended architecture

### Topology

```text
private engine/runtime
  -> private live adapter
  -> sanitized append-only observer stream
  -> read-only projection service
  -> browser UI
```

### Design rules
- the private live adapter is the only producer allowed to see engine-grade/runtime-grade state
- the projection service is structurally read-only
- the browser never talks directly to execution/broker services
- the observer path must be deploy-separated from the execution path
- the observer path should be kill-switchable without impacting the engine

### Backend split
1. **private adapter / ingest layer**
   - reads engine/runtime surfaces
   - sanitizes and emits observer-safe events
   - writes an append-only observer stream and latest-state projections

2. **read-only projection/API service**
   - serves bootstrap snapshots
   - serves recent candle/history windows
   - streams new observer events via WebSocket or SSE
   - cannot write back into engine state

### Frontend
- React + TypeScript
- TradingView Lightweight Charts for candle rendering
- terminal-like, dense, observer-only visual language

## Single-page layout v0

### Top bar
- engine name
- `live(sim)` badge
- symbol / timeframe
- feed freshness
- engine health state (`healthy | degraded | stale | halted`)

### Center chart
- candles
- entry markers
- exit markers
- pending-order markers
- current position reference band / average price line

### Right rail
- position card
- open orders
- last fill
- realized / unrealized PnL only if the source is already trusted and sanitized
- coarse risk flags

### Bottom tabs
- decision / event timeline
- orders and fills log
- health / incident notices
- data quality / freshness notices

## First bounded slice

### Scope
- one engine instance
- one active symbol
- one trading session
- read-only only

### Backend surfaces
- `GET /api/observer/sessions/{session_id}/bootstrap`
- `GET /api/observer/sessions/{session_id}/candles?limit=500`
- `GET /api/observer/sessions/{session_id}/timeline?limit=200`
- `WS /api/observer/sessions/{session_id}/stream`

### UI surfaces
- single observer page
- chart with markers
- position / orders / fills state
- health strip
- decision timeline

### Explicitly out of scope
- replay mode
- backtest overlays
- multi-engine switching
- parameter inspection
- strategy score / threshold / feature views
- pause / restart / arm / disarm buttons
- analytics warehouse / account dashboard expansion

## Event contract v0

All observer events should carry:
- `schema_version`
- `session_id`
- `engine_id`
- `seq`
- `event_id`
- `event_time`
- `ingest_time`
- `partial_data`
- `freshness_state`

Recommended observer event types:
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
- `session_started`
- `session_ended`

### Contract rules
- monotonic `seq` ordering per engine stream
- snapshot + stream recovery must be idempotent
- explicit nullable fields, no shape drift by omission
- coarse decision labels only, not raw strategy internals
- explicit staleness metadata so silent lag is impossible

## Deployment / auth posture

Minimum safe posture for AWS live(sim):
- private live adapter in private subnet / non-public path
- separate read-only projection service for browser use
- real auth in front of observer surface (OIDC/SSO or equivalent)
- TLS everywhere
- strict CORS, no wildcard origins
- short-lived browser sessions/tokens
- rate limiting / connection limiting
- observer kill switch independent from trading engine

## Verifier plan for MVP

The first implementation slice is done only if all checks pass:

1. **Truthfulness**
   - chart markers, timeline, orders/fills, and current position reconcile to the same underlying observer sequence for a sampled session

2. **Sanitization**
   - payload review proves no strategy internals, credentials, private account IDs, raw broker objects, or infra topology leak through the browser surfaces

3. **Freshness**
   - source timestamps and stale/degraded states are visible; silent staleness is not possible

4. **Recovery**
   - browser refresh or stream reconnect rebuilds the same state from bootstrap + subsequent events without duplicate drift

5. **Read-only boundary**
   - no UI route or backend route can mutate engine state directly or indirectly

## Architecture smells that must fail review

Reject or stop if any appears:
- same service/adapter handles both observer reads and trading writes
- browser can query engine DB/cache directly
- shared topic/namespace with execution control traffic
- timeline text grows into raw explainability / alpha leakage
- browser bundle contains real payloads, logs, or env hints from live(sim)
- the read-only promise is policy-only rather than structural

## Recommended implementation order

1. freeze the sanitized observer schema
2. build replay-safe/mock fixture mode for the observer UI
3. build bootstrap + stream projection service
4. land the single-page observer UI
5. connect one real live(sim) engine instance through the private adapter
6. verify sanitization and read-only boundary again before widening scope

## Topology statement

Topology unchanged.

This is a product-boundary and implementation-contract cut for a future sidecar line. It does not change the existing Steamer live execution topology or `steamer-card-engine` runtime authority.
