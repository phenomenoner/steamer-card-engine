# 2026-04-29 — Observer UI visual chartfix + next IA contract

## Verdict

The public AWS Steamer Observer demo is now running the visual-parity UI plus a chart visibility hotfix.

The immediate bug was not missing candle data. The API bootstrap contained chart candles, but the frontend defaulted to `Portfolio Overview`, where the UI intentionally renders a truthful placeholder instead of the symbol chart. A second mismatch made the chart path easy to miss: the mounted session key was `1314.TW`, while the strategy symbol universe listed `1314`.

## Current public demo receipt

Target:

```text
AWS_PROFILE=lyria-trading-ops
region=ap-east-2
instance=i-037aa8c8a534e878f
URL=http://43.213.34.167/
service=steamer-observer-dashboard.service
```

Active release after hotfix:

```text
/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-chartfix-20260429T032841Z-0fa5e9f
```

External smoke:

```text
GET /api/health -> 200 OK / {"status":"ok"}
GET / -> <title>Steamer Observer Monitor</title>
frontend asset -> /assets/index-CmKmRVC9.js
GET /api/observer/sessions -> default_session_id=aws-live-sim-20260427, symbol_pool.symbol_count=16
GET /api/observer/sessions/aws-live-sim-20260427/bootstrap -> symbol=1314.TW, candles=200, latest_seq=229
```

Live-sim boundary check after deploy:

```text
/opt/trading/current/.venv/bin/python -m strategy_async remained running; no live-sim restart or broker-control change.
```

## Code change

File changed:

```text
frontend/src/observer.tsx
```

Implemented:

- default selected view now prefers a mounted symbol session over `Portfolio Overview`
- symbol session resolution now aliases Taiwan stock symbols between bare and suffixed forms:
  - `1314` -> `1314.TW`
  - `1314.TW` -> `1314`
- mounted session lookup uses the alias resolver for both strategy-local and global `session_ids_by_symbol`

Local verification before deploy:

```text
npm --prefix frontend run build -> pass
./frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json -> pass
```

## CK review feedback captured

CK confirmed the updated UI is closer to the design artifact, but the next product gap is IA clarity rather than styling alone:

1. Select strategy card -> overview should show portfolio/trade-level truth:
   - trades
   - position
   - PnL only when truthful
   - lane health / receipt state
2. Select strategy card -> symbol should show:
   - bar/candle chart
   - strategy execution detail on that symbol
   - orders / fills / position for that symbol
   - timeline / decision / incident context for that symbol

Current state after chartfix:

- symbol chart path is visible by default when a mounted session exists
- portfolio overview still remains a truthful placeholder and is not yet the real strategy-card overview surface
- strategy-card selection exists as a shell, but the two product modes are not yet visually obvious enough

## Next IA acceptance contract

Next slice should make the split explicit:

```text
Strategy Card
  ├─ Overview: portfolio / trades / position / PnL / receipts
  └─ Symbol Detail: bar chart / per-symbol execution / timeline / orders / fills / position
```

Acceptance criteria:

- `Overview` is not a dead placeholder when strategy-level summary data exists.
- Overview must never invent PnL; if unavailable, show explicit `unavailable` reason + receipt lane.
- Symbol selector must distinguish:
  - mounted symbols with chart/session detail
  - universe symbols without mounted observer session
- The primary chart must be visible by default for the current mounted live-sim session.
- Strategy-card and symbol modes must be obvious in the header, not hidden in helper copy.
- No broker control, runtime write-back, credentials, account ids, or private runtime topology may enter browser payloads.

## Rollback

Revert service to previous visual release if needed:

```text
/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-20260428T053753Z-674aa95
```

The code-level rollback is reverting the `frontend/src/observer.tsx` alias/default-view change.

## Topology note

This pass changed only the read-only observer sidecar/frontend release. It did not widen security groups, add broker authority, change live-sim runtime code, or alter the live-sim process.
