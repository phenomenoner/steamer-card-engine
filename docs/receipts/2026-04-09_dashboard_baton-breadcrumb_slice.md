# 2026-04-09 — dashboard baton breadcrumb slice

## Verdict

Landed the smallest truthful breadcrumb on top of the active-family baton line.

- extended `/api/strategy-powerhouse` with a bounded `baton_line.breadcrumb` block
- rendered the breadcrumb above the existing baton cards in the Steamer Dashboard
- kept the line read-only and artifact-sourced
- topology did **not** change

## What the breadcrumb shows

1. last active-plan change timestamp from `.state/steamer/card-engine-morning-paired-lane/active_deck_plan.json`
2. current active-plan source packet path
3. last indexed baton source receipt when local campaign history can prove it
4. family/deck change summary with explicit unknown / not indexed fallback when prior deck truth is unavailable
5. divergence freshness from the indexed active-plan vs newer diverging proposal gap (`<=24h` = `fresh`; otherwise `stale`; incomplete truth = `unknown`)

## Local truth used

- active plan: `.state/steamer/card-engine-morning-paired-lane/active_deck_plan.json`
- proposal plan: `.state/steamer/card-engine-morning-paired-lane/proposed_distinct_families_20260409.json`
- indexed previous baton source:
  - `StrategyExecuter_Steamer-Antigravity/projects/steamer/lanes/autonomous-slow-cook/campaigns/2026-03-tw-intraday-shadow-vcp/STATE.json`
  - `StrategyExecuter_Steamer-Antigravity/projects/steamer/lanes/autonomous-slow-cook/campaigns/2026-03-tw-intraday-shadow-vcp/receipts/A08-governed-back-transition-2026-04-05T15-20-49+08-00.md`

## 五氣朝元 sweep

Changed rule/default wording only on the two 2026-04-09 tech notes.

Scanned the usual five surfaces for stale conflict:

1. repo `AGENTS.md` — already aligned; no new baton-authority conflict
2. repo `MEMORY.md` — no conflicting rule found
3. `docs/SETUP.md` — already aligned; no edit needed
4. tracked decision/authority surfaces — no rewrite needed
5. graph/doc-memory surfaces — not changed by this thin slice

Retired vs historical outcome:

- retired in place: the history-browser tech note now marks the breadcrumb as landed instead of leaving it as the next blade
- historical only: earlier baton-line closure receipt remains chronology/closure, not the authority surface for the new breadcrumb behavior

## Verifiers

- `uv run pytest -q tests/test_dashboard.py`
- `python3 - <<'PY' ... TestClient(create_app()).get("/api/strategy-powerhouse") ... PY`
- `npm run build`

## WAL / closure

- docs updated in place
- tests updated in place
- topology statement: **unchanged**
