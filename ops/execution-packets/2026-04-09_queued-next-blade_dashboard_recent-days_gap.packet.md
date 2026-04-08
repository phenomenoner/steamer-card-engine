# Queued next blade — why dashboard is not showing recent days data

- recorded: 2026-04-09
- scope: bounded diagnostic only; do not derail the primary morning top3 packet
- verdict: **cheap obvious root cause found**

## Root cause
The current Mission Control dashboard was wired as a **March replay-fixture demo surface**, not a generic recent-days browser.

The bounded diagnosis came out as a combination, not a single bug:

1. `docs/SETUP.md`
   - explicitly said: `Mission Control dashboard demo (read-only, March fixtures only)`
   - fixture set named there: `2026-03-06`, `2026-03-10`, `2026-03-12`

2. `src/steamer_card_engine/dashboard/fixtures.py`
   - `discover_fixture_days()` only accepted replay-style comparison directory names
   - recent Steamer/SCE outputs such as `manual-live-paired-20260408-...` never matched, so `/api/dates` could not list them even though their `compare-manifest.json` files were valid

3. `src/steamer_card_engine/dashboard/aggregator.py`
   - expected `diff["scaffold_placeholders"]`, which exists in the March replay compares but is absent from the newer manual-live decision-grade diffs
   - so the dashboard needed one more truth fix besides discovery: newer compare-manifest families needed graceful normalization for the slightly different diff shape

## Cheap evidence
From the local repo state during the top3 packet:

- `comparisons/` total dirs: `37`
- dirs matching dashboard fixture regex: `5`
- recent non-matching dirs include:
  - `manual-live-paired-20260408-entry-mode-long-one-vcp-vcp-min-trend-slope-10-...`
  - `manual-live-paired-20260408-entry-mode-long-one-vcp-vcp-min-trend-slope-2-...`
  - `prep-tw_vcp_dryup_plus_reclaim_s{2,5,10}-...-20260409`

So the dashboard is not missing recent data ingestion; it is **filtering recent comparison families out by contract**.

## Closure
The smallest useful fix has now landed:

- discovery is manifest-driven instead of replay-name-regex-driven
- the dashboard resolves baseline/candidate bundle dirs from `compare-manifest.json` and uses same-session bundle dates as the fixture key
- same-date compare variants collapse to one representative date entry with a documented selection rule: pass status, then comparison family priority (`manual-live-paired` > `replay-sim` > `prep` > `phase3` > other), then comparison directory name
- manual-live diffs that omit `scaffold_placeholders` now load truthfully instead of crashing
- docs were recut from March-only wording to the current committed fixture index (`2026-03-06` → `2026-04-08`)

## Remaining boundary
- topology unchanged
- the browser surface is still **one representative compare bundle per session date**, not a full multi-scenario-per-day browser
- recent manual-live dates now appear, but same-date variants are intentionally collapsed rather than rendered as separate dashboard cards
