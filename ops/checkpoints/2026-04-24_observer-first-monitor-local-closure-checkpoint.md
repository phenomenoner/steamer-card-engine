# 2026-04-24 — observer-first monitor local closure checkpoint

## Scope closed

- Added `VITE_STEAMER_SURFACE=observer` frontend mode that renders the observer monitor directly before the legacy dashboard hooks/fetches are mounted.
- Preserved default dashboard mode and existing tabbed shell.
- Hardened `ObserverSurface` state handling:
  - explicit no-session state
  - visible websocket lifecycle (`idle`, `connecting`, `live`, `ended`, `closed`, `error`)
  - `stream_end`, close, error, malformed JSON handling without root crash
  - sequence-gap detection
  - prominent attention banner for stale/lagging/degraded freshness or stream degradation
  - marker cap at 80
- Made `write_sim_observer_bundle_json()` atomic via same-directory temp file, file fsync, `os.replace()`, and best-effort parent-directory fsync.
- Added an atomic replacement invariant test for the sim observer writer.
- Added a public-safe `partial_data` allowlist test plus public event scalar scan so sim observer bundles fail fast if broker/account/infra/private-looking fields drift into browser-visible payloads.
- Wrote post-P1 backlog parking the strategy-family verifier decision and real-money smoke gate until after this closure.

## Changed files

- `frontend/src/App.tsx`
- `frontend/src/observer.tsx`
- `frontend/src/styles.css`
- `src/steamer_card_engine/observer/sim.py`
- `tests/test_observer_sim.py`
- `ops/checkpoints/2026-04-24_observer-first-monitor-local-closure-checkpoint.md`
- `ops/backlog/2026-04-26_steamer-post-observer-p1-backlog.md`

## Verifier receipts

```text
uv run pytest tests/test_observer_sim.py tests/test_observer_bridge.py tests/test_dashboard.py tests/test_sim_compare.py -q
........................................                                 [100%]
40 passed in 21.53s
```

```text
uv run ruff check src/steamer_card_engine/observer/sim.py tests/test_observer_sim.py
All checks passed!
```

```text
npm --prefix frontend run build
✓ built in 1.86s
```

```text
VITE_STEAMER_SURFACE=observer npm --prefix frontend run build
✓ built in 1.96s
```

```text
VITE_STEAMER_SURFACE=observer npm --prefix frontend run build
rg "api/dates|strategy-powerhouse|strategy-pipeline|/api/days|/api/cards|/api/timeline" frontend/dist
none
```

## QA check

Minion QA verdict: conditional pass from the provided diff summary, with no blockers. Follow-up hardening applied before closure:

- parent-directory fsync after atomic replace
- broader public event scalar scan in observer sim tests
- explicit observer-only forbidden API bundle grep verifier

## Topology statement

No runtime or execution topology changed. This remains a local read-only observer-sidecar/product-surface slice. No AWS deployment, auth, network boundary, broker mapping, or live execution authority was touched.

## Blockers

None for the requested local slices.
