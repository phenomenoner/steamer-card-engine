# Checkpoint — 2026-04-23 11:38 Asia/Taipei — live observer sidecar

## Line
`steamer-card-engine` live observer sidecar for AWS live(sim)

## Current verdict
Proceed.
The line is now frozen as a **read-only live observer** product cut, not a browser trading terminal.

## What was completed
- Cross-validated the line on both product and security dimensions.
- Froze the public-safe product boundary and first bounded slice.
- Landed public-safe planning artifacts in `steamer-card-engine`:
  - `docs/tech-notes/2026-04-23_steamer_card_engine_live_observer_sidecar_v0_contract.md`
  - `ops/execution-packets/2026-04-23_steamer-card-engine_live-observer-sidecar-v0.packet.md`
- Landed private decision/WAL closure in `lyria-working-ledger`:
  - `DECISIONS/2026-04-23.md`

## Push receipts
- `steamer-card-engine`: `c20edeb` — `docs: freeze live observer sidecar v0 contract`
- `lyria-working-ledger`: `a928fc8` — `decision: freeze steamer live observer sidecar boundary`

## Boundary that must hold
- observer != control plane
- public repo != private adapter
- browser payload != engine-grade event stream
- read-only must be structural, not just UX-level

## First bounded implementation slice
- one engine instance
- one symbol
- one session
- read-only only
- bootstrap snapshot API
- candle/history API
- append-only observer stream
- chart markers + position/orders/fills + health + decision timeline

## Next recommended move
Open `櫻花刀舞 non-stop` implementation with this sequence:
1. observer schema / types
2. mock bootstrap + mock stream
3. single-page observer UI skeleton
4. chart + marker overlays
5. snapshot/stream reconciliation

## Implementation progress receipt (12:0x update)
- Landed `src/steamer_card_engine/observer/` with sanitized mock observer schema + seed session bundle.
- Wired read-only observer routes into `src/steamer_card_engine/dashboard/api.py`:
  - `GET /api/observer/sessions`
  - `GET /api/observer/sessions/{session_id}/bootstrap`
  - `GET /api/observer/sessions/{session_id}/candles`
  - `GET /api/observer/sessions/{session_id}/timeline`
  - `WS /api/observer/sessions/{session_id}/stream`
- Landed frontend observer tab and single-page surface in:
  - `frontend/src/observer.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/styles.css`
- Landed Lightweight Charts dependency and synthetic marker overlays from the same sanitized event sequence.
- Added backend verifier coverage for bootstrap/candles/timeline/websocket tail recovery in `tests/test_dashboard.py`.
- Verifiers passed:
  - `./.venv/bin/pytest tests/test_dashboard.py -q` -> `12 passed`
  - `npm --prefix frontend run build` -> pass
- Follow-up hygiene fix landed in `pyproject.toml`: migrated deprecated `tool.uv.dev-dependencies` to `dependency-groups.dev`, then re-ran `pytest` successfully.

## Review absorption update
- Ran a second-brain review pass and absorbed the bounded fixes that were real for this slice:
  - invalid websocket `after_seq` now returns an explicit error payload and closes with client-error semantics instead of silently replaying from zero
  - stream-order payloads now carry `submitted_at`, keeping snapshot and stream order shapes aligned
  - observer timeline now uses the bootstrap snapshot as the single source of truth on initial load instead of fetching a divergent second timeline immediately
  - frontend marker overlays now align event markers to candle bar times, so Lightweight Charts receives marker timestamps that match rendered bars
  - order-submitted markers now reflect side (`buy` / `sell`) instead of always rendering as buy markers
  - incident accumulation is capped to avoid unbounded growth during longer sessions
  - added observer negative-path coverage for unknown session bootstrap and invalid websocket `after_seq`
- Re-verifiers passed after the hardening pass:
  - `./.venv/bin/ruff check src/steamer_card_engine/dashboard/api.py src/steamer_card_engine/observer tests/test_dashboard.py`
  - `./.venv/bin/pytest tests/test_dashboard.py -q` -> `12 passed`
  - `npm --prefix frontend run build` -> pass

## Private bridge v0 progress
- Landed public-safe observer bridge planning artifacts:
  - `docs/tech-notes/2026-04-23_steamer_card_engine_observer_private_bridge_v0.md`
  - `ops/execution-packets/2026-04-23_steamer-card-engine_observer-private-bridge-v0.packet.md`
- Landed `src/steamer_card_engine/observer/bridge.py` as a deterministic read-only projection layer that rebuilds bootstrap state from sanitized observer events.
- Refactored the mock observer path to rebuild bootstrap through the bridge instead of duplicating snapshot presentation state by hand.
- Added focused bridge tests in `tests/test_observer_bridge.py`.
- Verifiers passed for the bridge slice:
  - `ruff check src/steamer_card_engine/observer src/steamer_card_engine/dashboard/api.py tests/test_dashboard.py tests/test_observer_bridge.py`
  - `pytest tests/test_dashboard.py tests/test_observer_bridge.py -q` -> `17 passed`
  - `npm --prefix frontend run build` -> pass
- Claude review on bridge v0 produced real fixes and they were absorbed immediately:
  - `apply()` is now explicit mutating contract instead of mutating plus returning state
  - `to_bar_time()` now rejects invalid timestamp shapes instead of silently truncating garbage
  - `order_acknowledged` no longer fabricates phantom orders when sequence history is missing
  - incremental `apply()` / duplicate-seq / health-gap event behavior is now test-covered
- Meaningful next gate remains unchanged: real private live adapter attachment is still separate and intentionally not landed in the public-safe repo.

## Next recommended move
1. absorb bounded code-review findings for bridge v0 if any
2. commit the bridge slice as the next local milestone
3. then cut the first private-adapter attachment packet against the new projection boundary

## Topology statement
Unchanged.
