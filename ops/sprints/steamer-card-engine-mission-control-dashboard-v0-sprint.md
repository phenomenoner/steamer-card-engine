# Steamer Card Engine — Mission Control Dashboard v0 sprint

## Sprint goal / milestone

Ship the first **browser-openable, read-only Mission Control dashboard** for `steamer-card-engine` using real paired-live AWS capture lineage.

The milestone closes when a user can open one recent day in browser and understand:
- what happened
- which strategy surface dominated
- what anomalies exist
- what is worth drilling into

without chat archaeology.

## Rollout policy

- posture: active sprint, demo-first
- authority: read-only only
- execution posture: forward-mandatory inside declared boundaries
- report posture: batch ordinary progress; surface only real blockers/decisions
- opening fixture day: `20260402`
- opening fixture set: `20260331`, `20260401`, `20260402`

## Boundary note

This sprint owns a **browser observability surface** only.
It does **not** own:
- broker/operator control expansion
- Steamer native daily control-plane replacement
- strategy promotion authority
- live trading UI

## Forcing move

The forcing move is **Daily Command View on real data**.

If the day-bundle is not readable, nothing else counts as progress.

## 櫻花刀舞 — blade map / serial queue board

### Blade 0 — fixture truth contract
- goal: lock the demoable day set and the exact files that define it
- output:
  - fixture manifest / discovery rule
  - explicit truth note for zero-state transaction/PnL surfaces
- verifier:
  - the same 3 days resolve deterministically on any local run

### Blade 1 — aggregator day bundle
- goal: produce one normalized day bundle from existing run + compare artifacts
- output:
  - `daily_summary`
  - `strategy_card_summaries`
  - `anomalies`
  - `event_timeline`
  - `transaction_surface`
  - `empty_state_metadata`
- verifier:
  - `20260402` bundle can be generated from repo truth only

### Blade 2 — read-only API
- goal: expose dates + per-day bundle through FastAPI
- output:
  - `/api/dates`
  - `/api/days/{date}/summary`
  - `/api/days/{date}/cards`
  - `/api/days/{date}/compare`
  - `/api/days/{date}/events`
  - `/api/days/{date}/transactions`
- verifier:
  - local curl/browser requests return stable JSON

### Blade 3 — React shell + command strip
- goal: establish production-grade shell and first-screen hierarchy
- output:
  - app shell
  - date switcher
  - command strip
  - compare/anomaly summary cards
- verifier:
  - first screen answers the battle picture in ~10 seconds

### Blade 4 — strategy-card leaderboard + detail drawer
- goal: make card-level dominance legible
- output:
  - leaderboard
  - detail drawer
  - card content / config summary
  - reason distribution / anomaly links
- verifier:
  - slope `10` vs `2` identity is obvious on `20260402`

### Blade 5 — replay timeline + snapshot drilldown
- goal: make event flow explorable without leaving global context
- output:
  - timeline rail
  - event detail drawer
  - scenario/config snapshot surfaces
- verifier:
  - operator can open a concrete event and see supporting receipts

### Blade 6 — transaction/PnL panel with truthful zero-state contract
- goal: include the required surface without lying about current artifact richness
- output:
  - transaction table shell
  - PnL summary shell
  - explicit empty-state / incomplete-state messaging
- verifier:
  - UI distinguishes “no populated trade data in this compare bundle” from failure

### Blade 7 — production polish + handoff
- goal: make the opening cut feel operator-grade rather than hackathon-grade
- output:
  - loading/empty/error states
  - responsive layout sanity
  - screenshot receipts
  - launch/runbook
- verifier:
  - browser-openable handoff is good enough for CK review

## Stop conditions

Stop only for:
1. real blocker
2. risk change
3. scope/authority change
4. truthful completion
5. honest fatigue / quality threshold breach

## Risks

- fake progress through shell-first UI work
- pretending compare bundles already contain rich transaction surfaces
- letting the dashboard drift into a control plane
- widening into full analytics/history warehouse too early

## Docs / WAL sync checklist

When sprint truth changes, sync in the same pass:
- this sprint doc
- build packet tech note
- `docs/PRODUCT_SCOPE.md` if scope wording changes again
- push receipt
- memory note

If topology does not change, say so explicitly.

## Run journal

- 2026-04-06 — sprint opened after CK approved a browser mission-control line for `steamer-card-engine` and explicitly requested a formal build packet with `櫻花刀舞` planning.
- 2026-04-06 — remote repo selection locked to `phenomenoner/steamer-card-engine`; topology unchanged.
- 2026-04-06 — demo-fixture truth locked to paired-live AWS capture lineage already present in local `runs/` and `comparisons/` bundles, with `20260402` as the opening hero day.
