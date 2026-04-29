# 2026-04-29 — Steamer Observer strategy-card IA slice 1

## Verdict

Implement the first verifier-backed IA slice for Steamer Observer:

```text
Strategy Card
  ├─ Overview: trades / position / PnL truth / receipt state
  └─ Symbol Detail: bar chart / per-symbol execution detail / orders / fills / position / timeline
```

## Whole-picture promise

The monitor should stop feeling like a generic dashboard. Operators should know whether they are looking at:

1. a strategy-card portfolio overview, or
2. a symbol-level execution trace for that strategy.

Fake progress: only restyling panels without making the two modes obvious and verifiable.

## Bounded slice

Frontend-first slice in `frontend/src/observer.tsx` + minimal CSS/tests/docs if needed:

- Rename/clarify the current selectors and headers so the IA is explicit:
  - Strategy Card selector
  - View selector with `Overview` and `Symbol Detail` semantics
- Make Overview a real strategy-card summary surface using currently available sanitized bundle truth:
  - strategy sessions count
  - mounted symbols count
  - aggregate open orders count
  - fill/trade count from timeline/bootstrap where available
  - net/position summary only from mounted session data; if unavailable, explicit unavailable reason
  - PnL: show unavailable unless payload provides truthful value
  - receipt/trust state
- Make Symbol Detail clearly show:
  - bar/candle chart
  - selected symbol/session
  - execution detail panels: open orders, fills, position, health/incidents, timeline
- Do not add broker control or mutation paths.

## Contract / boundaries

Inputs:

- `/api/observer/sessions`
- `/api/observer/sessions/{session_id}/bootstrap`
- websocket stream updates already used by current UI

Outputs:

- Browser UI only.
- No API schema changes unless necessary; prefer deriving from existing sanitized payload.

State changes:

- Repo code/docs only.
- Optional AWS redeploy after review if verifier passes.

Invariants:

- No fake PnL.
- No broker control.
- No runtime write-back.
- No credential/account/routing leakage.
- Empty/degraded/unavailable states stay explicit.

## Verifier plan

Minimum before merge/deploy:

```bash
npm --prefix frontend run build
./frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json
uv run pytest tests/test_dashboard.py tests/test_observer_sim.py tests/test_observer_bridge.py -q
```

Focused checks:

- Built JS contains visible copy for `Strategy Card Overview` and `Symbol Detail`.
- Existing observer forbidden/leak scan remains clean if available.
- Manual/API receipt confirms mounted session has candles and chart default still works.

## Rollback

Revert this slice commit or switch AWS service back to previous chartfix release:

```text
/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-chartfix-20260429T032841Z-0fa5e9f
```

## Stop-loss

Stop and report if:

- implementing overview requires new backend schema beyond trivial derivation;
- PnL/trade aggregation would become synthetic or misleading;
- TypeScript/chart behavior breaks and cannot be fixed in two focused attempts;
- the slice starts turning into a broader dashboard rewrite.
