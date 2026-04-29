# 2026-04-29 — Observer UI strategy-card IA slice 1

## Verdict

Strategy-card IA slice 1 is implemented locally and verifier-clean.

The UI now makes the two product modes explicit:

```text
Strategy Card
  ├─ Overview · trades / position / PnL / receipts
  └─ Symbol Detail · bar chart / execution state / orders / fills / timeline
```

## What changed

File changed:

```text
frontend/src/observer.tsx
```

Implemented:

- Selector language changed from generic `strategy/view` to:
  - `Strategy Card selector`
  - `Strategy Card view`
- View labels now explicitly separate:
  - `Overview · trades / position / PnL / receipts`
  - `Symbol Detail · {symbol}`
- Overview now summarizes truthful mounted sanitized data using existing observer APIs:
  - strategy sessions loaded/total
  - mounted symbols
  - open orders
  - fills/trades derived from timeline/last fill
  - position summary from mounted session data only
  - PnL explicitly unavailable when sanitized payload does not provide it
  - receipt/trust state
- Symbol Detail labels now make execution state obvious:
  - `Symbol Detail · Bar Chart`
  - `Symbol Detail · Execution State`
  - `Symbol Detail · Position`
  - `Symbol Detail · Open Orders`
  - `Symbol Detail · Last Fill / Trade`
  - `Symbol Detail · Timeline / Health`

## Boundary

No backend schema change was required.

No broker control, mutation path, runtime write-back, credential surface, account id, routing id, or private topology exposure was added.

Overview derives only from currently mounted sanitized observer bootstraps. It does not invent PnL.

## Verifier receipts

```text
npm --prefix frontend run build -> pass
./frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json -> pass
uv run pytest tests/test_dashboard.py tests/test_observer_sim.py tests/test_observer_bridge.py -q -> 33 passed
```

Build artifact after verifier:

```text
frontend/dist/assets/index-CVxPt2tU.js
frontend/dist/assets/index-BI1Jlmm-.css
```

## Deployment plan

If accepted, deploy as a read-only sidecar frontend overlay on top of the current chartfix release:

```text
base=/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-chartfix-20260429T032841Z-0fa5e9f
next=/opt/trading/releases/steamer-card-engine-observer-ui-v0-strategy-ia-slice1-<timestamp>-<commit>
```

Service remains:

```text
steamer-observer-dashboard.service
STEAMER_OBSERVER_BUNDLE_JSON=/opt/trading/shared/steamer-observer-live/20260427/observer.bundle.json
STEAMER_OBSERVER_INCLUDE_MOCK=0
```

## Rollback

Switch service back to previous chartfix release:

```text
/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-chartfix-20260429T032841Z-0fa5e9f
```

## Remaining product work

This slice makes the IA visible and truthful. Later slices can enrich the overview if/when the observer bundle includes true portfolio-level PnL or multi-symbol trade aggregates.
