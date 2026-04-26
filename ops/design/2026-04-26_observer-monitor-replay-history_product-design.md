# 2026-04-26 — Observer Monitor historical replay product design

## Verdict

Add **Historical Replay** as a sibling mode beside the existing **Observer Monitor**, not as a replacement and not as browser execution control.

The current AWS demo proves one read-only observer session can be opened in-browser. The next product gap is browsing prior replay/live-sim sessions and comparing them without touching broker/runtime authority.

## User promise

An operator can answer, from the browser:

1. What happened in the current observed session?
2. What happened in prior replay/live-sim sessions?
3. How does this session compare with a selected baseline or candidate run?
4. Which artifact bundle is the source of truth for every chart, event, decision, order, fill, and health claim?

The promise is **review and comparison**, not control.

## IA / navigation recommendation

Recommended shell: **Steamer Observer** with two top-level tabs.

- **Monitor**
  - Existing single-session live observer view.
  - Default route for the AWS demo.
  - Shows freshness, websocket state, chart, timeline, position, orders/fills, and health.
- **Replay History**
  - New read-only history browser.
  - Session list with filters: date, symbol, market mode, scenario/deck, run type, freshness/result status.
  - Detail page reuses the Observer Monitor layout in replay-static mode.
  - Compare drawer/page supports baseline vs candidate, or current observer session vs selected historical run.

Route sketch:

- `/` redirects to `/monitor` in observer-only deployments.
- `/monitor/:sessionId?` opens current/selected observer bundle.
- `/history` lists historical replay/live-sim bundles.
- `/history/:sessionId` opens one historical bundle.
- `/history/compare?left=<sessionId>&right=<sessionId>` opens a bounded compare view.

Keep legacy Mission Control tabs out of the observer-only AWS surface unless explicitly enabled by deployment mode.

## Data / API surface needed

Extend the existing read-only `/api/observer/...` family rather than inventing a second authority surface.

Minimum API additions:

- `GET /api/observer/history/sessions`
  - Returns paginated session summaries.
  - Fields: `session_id`, `source_kind`, `source_path_ref`, `date`, `generated_at`, `engine_id`, `session_label`, `market_mode`, `symbol`, `timeframe`, `scenario_id`, `deck_id`, `run_type`, `freshness_state`, `latest_seq`, `event_count`, `candle_count`, `has_compare`, `tags`.
- `GET /api/observer/history/sessions/{session_id}/bootstrap`
  - Same shape as current observer bootstrap where possible.
- `GET /api/observer/history/sessions/{session_id}/candles?limit=&cursor=`
  - Static historical candles, capped and cursorable.
- `GET /api/observer/history/sessions/{session_id}/timeline?limit=&cursor=`
  - Static historical event/timeline rows, capped and cursorable.
- `GET /api/observer/history/compare?left_session_id=&right_session_id=`
  - Returns a compact compare summary plus links/refs to existing compare artifacts when available.

Repository/index needs:

- A `HistorySessionIndex` built from repo-local or mounted artifact roots.
- Stable session identity and source provenance, without exposing raw absolute private paths in public payloads.
- Adapter layer that can project existing replay/live-sim bundles into the observer bundle contract.
- Optional compare-artifact resolver for existing `comparisons/*/{summary.md,diff.json,compare-manifest.json}`.

Security/data rule: browser payloads stay sanitized. No credentials, broker/account objects, private runtime routing IDs, raw AWS paths, or write/control endpoints.

## Phased implementation slices

### Slice 0 — design approval only

- Approve this product shape.
- Decide whether AWS demo history should mount only sanitized fixture bundles first.
- No code changes.

### Slice 1 — local history index contract

- Add a read-only history index builder over a small local fixture set.
- Normalize historical sessions into observer-compatible metadata summaries.
- Tests prove stable ordering, pagination, and safe source refs.

### Slice 2 — history API, no frontend deep UI yet

- Add read-only history endpoints.
- Reuse existing observer repository/projector where possible.
- Tests cover not-found, malformed bundle, pagination caps, and no secret-ish fields.

### Slice 3 — Replay History list + detail page

- Add tab/nav and list filters.
- Open selected historical session in replay-static monitor layout.
- No compare UI yet.
- Browser build and dashboard tests pass.

### Slice 4 — bounded compare view

- Add baseline/candidate selection and compact compare panel.
- Use existing compare artifacts first.
- If no compare artifact exists, show `compare unavailable` with source refs instead of fabricating metrics.

### Slice 5 — AWS demo activation gate

- Deploy only after local closure.
- Mount a sanitized historical fixture/index root.
- Prove `/monitor`, `/history`, one historical detail, and one compare/unavailable path in browser.
- Re-run payload leakage spot review.

## Acceptance criteria

Product acceptance:

- Operator can switch between Monitor and Replay History without losing the observer-only mental model.
- At least one historical replay/live-sim session is discoverable, openable, and clearly labeled as historical/static.
- Every historical view exposes source provenance and generated time.
- Compare path never invents metrics when compare artifacts are missing.
- Current Monitor remains the default AWS demo landing page.

Technical acceptance:

- All new endpoints are GET-only and under `/api/observer/history/...`.
- Existing `/api/observer/sessions/...` behavior remains backward compatible.
- Pagination/limits prevent accidental huge payloads.
- Frontend handles empty history, stale/malformed bundles, not-found sessions, and compare-unavailable states.
- Tests cover API contract, index projection, frontend build, and leakage guard spot checks.

Deployment acceptance:

- AWS demo activation uses only sanitized historical artifacts.
- No live execution authority, broker control, auth widening, or public-write route is introduced.
- Kill switch remains the same observer/dashboard service stop path.

## Non-goals

- No browser order placement, broker mutation, card approval, or runtime control.
- No real-money smoke execution.
- No public multi-user product hardening in this slice.
- No full analytics warehouse or long-term storage migration.
- No private strategy-parameter disclosure.
- No requirement to make every legacy replay/comparison artifact browsable in the first release.

## Risks

- **Artifact heterogeneity:** older replay/compare bundles may not project cleanly into the observer contract. Mitigation: start with a curated fixture subset and mark unsupported bundles explicitly.
- **Source leakage:** historical artifact refs can expose private local/AWS paths. Mitigation: payload source refs must be logical IDs, not raw private paths.
- **UI confusion:** users may confuse static replay with live monitor. Mitigation: strong route labels, static badge, generated-at timestamp, no websocket-state styling on replay detail.
- **Compare theater:** missing compare artifacts may tempt synthetic or misleading deltas. Mitigation: compare view must degrade to `unavailable` with receipts.
- **Payload bloat:** historical timeline/candle payloads can become large. Mitigation: capped limits, cursors, and summary-first list loading.

## Explicit no-implementation note

This document is a product design recommendation only. It intentionally does **not** implement code, change runtime topology, deploy AWS changes, commit, push, or authorize any browser write/control surface.
