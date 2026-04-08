# 2026-04-09 — dashboard history-source index slice

- repo: `steamer-card-engine`
- branch: `feat/gemini-gamify-dashboard`
- topology changed: **no**

## Verdict

Landed the smallest useful shared history-source index helper for the Strategy Powerhouse dashboard slice.

The dashboard no longer depends on hand-wired dated paths for:

- distinct-family proposal / packet / bounded-backtest / verifier discovery
- family-specific blocker-surgery / parameter-estimate discovery
- latest indexed baton-source receipt lookup for the current active family

All of this remains local-artifact, read-only, and non-authoritative.

## What changed

- added `src/steamer_card_engine/dashboard/history_source_index.py`
- the helper now:
  - finds the latest `proposed_distinct_families_*.json`
  - derives the proposal day from that plan
  - resolves the matching distinct-family morning packet / bounded backtest / synthetic verifier pair for that day
  - indexes per-family source coverage from those shared artifacts plus recognized family-specific suffix packets
  - indexes current-family baton-transition receipts from autonomous-slow-cook campaign history without changing any execution state
- rewired `strategy_powerhouse.py` to consume that helper for history links, verifier paths, family-specific packet discovery, and baton breadcrumb source lookup
- added a focused test proving the helper indexes the current three candidate families truthfully

## Verifiers / smokes

- `uv run pytest -q tests/test_dashboard.py`
- `uv run ruff check src/steamer_card_engine/dashboard/history_source_index.py src/steamer_card_engine/dashboard/strategy_powerhouse.py tests/test_dashboard.py`
- `npm run build` in `frontend/`
- API smoke via `TestClient(create_app())` confirming:
  - `cards == 3`
  - `history_event_count == 14`
  - `verifier_receipt_count == 3`
  - baton breadcrumb stays `indexed`
  - last baton source still resolves to `A08-governed-back-transition-2026-04-05T15-20-49+08-00.md`

## Boundary / topology statement

- still read-only local artifact discovery only
- still no broker / order / auth control
- still no governance mutation
- `steamer-card-engine` remains the execution surface
- `strategy-powerhouse` remains research / packaging / control-plane support only
- topology changed: **no**

## 五氣朝元 / stale-rule check

No rule/default wording changed in this slice.

A bounded stale-rule check was still performed on the touched dashboard docs/sprint surfaces, and no conflicting older authority surface was found. Earlier 2026-04-09 notes remain chronological receipts only.

## Remaining limits

The helper is intentionally thin:

- family-specific extras still rely on a small recognized suffix registry, not an open-ended warehouse
- baton discovery only indexes the latest activation receipt for campaigns whose current `STATE.json` still points at that active family
- richer multi-packet family histories should stay additive and read-only if expanded later
