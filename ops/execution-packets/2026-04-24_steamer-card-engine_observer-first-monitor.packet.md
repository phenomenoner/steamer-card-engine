# Execution packet — observer-first monitor

## Mission

Turn the current observer tab into an observer-first monitor deployment path for `steamer-card-engine`, while preserving the read-only public-safe observer boundary.

## Authority / risk envelope

Allowed in this packet:

- frontend refactor for observer-only mode
- frontend state handling for empty sessions, websocket lifecycle, freshness banner, malformed stream handling
- atomic local JSON writing for repo-native sim observer bundle output
- tests/docs/checkpoint updates

Not allowed in this packet:

- live execution authority changes
- broker/control/browser write routes
- public URL widening
- auth/permission changes
- AWS deploy without a separate activation gate

## Required slices

### Slice A — observer-only shell split

Acceptance:

- observer-only frontend mode exists, preferably `VITE_STEAMER_SURFACE=observer`
- observer-only mode loads no non-observer API surfaces
- default tabbed dashboard remains available
- frontend build passes

Files likely touched:

- `frontend/src/App.tsx`
- `frontend/src/observer.tsx`
- `frontend/src/styles.css`

### Slice B — atomic bundle write

Acceptance:

- `write_sim_observer_bundle_json()` writes via same-directory temp file + rename
- existing sim observer tests pass
- no new private mapping logic enters repo

Files likely touched:

- `src/steamer_card_engine/observer/sim.py`
- `tests/test_observer_sim.py`

### Slice C — operator state UI

Acceptance:

- no-session state is explicit
- websocket state is visible
- `stream_end`, close, error, malformed JSON are handled without root crash
- lagging/stale/degraded has a prominent banner

Files likely touched:

- `frontend/src/observer.tsx`
- `frontend/src/styles.css`

### Slice D — closure

Run:

```bash
uv run pytest tests/test_observer_sim.py tests/test_observer_bridge.py tests/test_dashboard.py tests/test_sim_compare.py -q
uv run ruff check src/steamer_card_engine/observer/sim.py tests/test_observer_sim.py
npm --prefix frontend run build
```

Write checkpoint:

- `ops/checkpoints/2026-04-24_observer-first-monitor-local-closure-checkpoint.md`

## Stop-loss

Stop and report if:

- observer-only mode requires removing the legacy dashboard rather than gating it
- private adapter/broker mapping is needed to complete the local slice
- browser payload requires raw runtime/broker objects
- verifier failure points to broad dashboard architecture rather than bounded observer code

## Topology statement

No runtime/execution topology change is authorized by this packet.
AWS activation remains a later gate after local closure.
