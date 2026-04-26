# 2026-04-26 — Observer Monitor Replay History UI/UX recommendations

## Verdict

Add Historical Replay as a **read-only sibling surface** beside the existing Observer Monitor, not as an execution control or strategy dashboard. The UX should let an operator browse prior sanitized observer bundles, replay one session in event order, and compare two sessions at a glance without widening browser-visible data beyond the observer contract.

No implementation was performed in this pass. This document is UI/UX recommendation only.

## Screen map

1. **Observer Monitor / Live**
   - Current observer-first session surface.
   - Keeps live freshness, chart, orders, fills, position, health, and append-only event timeline.
2. **Replay History / Library**
   - List of available prior sessions or bundles.
   - Filter by date, symbol, strategy/card label if already sanitized, run mode, freshness outcome, and bundle status.
3. **Replay Detail**
   - Single prior session replay with scrubber, event timeline, chart cursor, orders/fills/position panels, and receipt metadata.
4. **Compare**
   - Two-session comparison view: baseline vs candidate, synchronized timeline, key deltas, and side-by-side event/position summaries.
5. **Receipt Drawer**
   - Collapsible read-only metadata: bundle path/id, generated_at, schema version, sanitizer version if present, and verifier/checkpoint links.

## Navigation model

- Top-level segmented navigation: **Live Monitor | Replay History | Compare**.
- Live Monitor remains the default landing view for observer-only deployments.
- Replay History opens from a persistent secondary action: `Browse prior sessions`.
- Replay Detail is URL-addressable by sanitized `session_id` or bundle id.
- Compare is entered from:
  - selecting two rows in Replay History, or
  - `Compare with...` from Replay Detail.
- Browser back/forward should preserve selected session, replay timestamp, filters, and compare pair.

## Key components

- **Session Library Table**
  - Columns: session time, symbol/universe, mode, duration, event count, fills count, final position state, freshness status, bundle status.
  - Row actions: open replay, compare, copy receipt id/path.
- **Replay Scrubber**
  - Event-index and wall-clock modes.
  - Play/pause, step event, jump to order/fill/position update, speed selector.
- **Synchronized Chart Cursor**
  - Cursor follows selected event and highlights nearest candle.
  - Marker legend for order submitted, acknowledged, fill received, position updated, stream end.
- **Event Timeline**
  - Append-only ordering, filterable by event type, with current event pinned during playback.
- **State Panels**
  - Orders, fills, and position panels show state at selected replay point, not just final state.
- **Compare Delta Strip**
  - Compact top band: duration delta, event count delta, fill count delta, final position delta, freshness/degraded flags.
- **Receipt Drawer**
  - Makes provenance visible without turning the UX into an ops log dump.

## Empty, loading, and error states

- **No history configured**: explain that no replay bundles are mounted; link to deployment/operator setup docs when available.
- **No results after filters**: show active filters and offer `Clear filters`.
- **Bundle loading**: skeleton table/detail panels with clear `Loading sanitized observer bundle...` label.
- **Replay stream unavailable**: allow static replay from bundle if event data exists; mark live stream features unavailable.
- **Malformed or partial bundle**: block replay, show safe error summary, schema/version, and receipt id/path if available.
- **Compare mismatch**: if sessions cannot be aligned by event or time, fall back to side-by-side summaries and explain why sync is disabled.
- **Stale/degraded data**: prominent banner above replay/compare content, matching the live monitor freshness language.

## Visual hierarchy

1. **Safety and provenance first**: read-only badge, session identity, freshness/degraded status, generated timestamp.
2. **Market shape second**: chart with replay cursor and event markers.
3. **Execution state third**: orders/fills/position at selected replay point.
4. **Timeline fourth**: full event log for audit and navigation.
5. **Receipts last**: drawer-level details available on demand.

Use a calm audit-console style: high contrast for stale/error/degraded states, restrained color for event markers, and no trading-action affordances.

## Operator review workflow

1. Operator opens Live Monitor for current session truth.
2. Operator clicks `Browse prior sessions` after a demo/live-sim run.
3. In Replay History, operator filters to the target date/session and checks freshness/bundle status.
4. Operator opens Replay Detail, plays or steps through key event transitions.
5. Operator opens Receipt Drawer to confirm provenance and sanitizer/schema metadata.
6. If reviewing a new deployment or card change, operator selects a baseline session and opens Compare.
7. Operator records findings outside the UI; the replay surface remains read-only and performs no approvals, edits, or execution actions.

## Responsive considerations

- Desktop: three-column replay layout, chart center, timeline rail right, state panels below or left.
- Tablet: chart first, collapsible timeline/state tabs, sticky replay scrubber.
- Mobile: history browsing and receipt checks only; replay detail becomes stacked cards with event stepping, not dense side-by-side compare.
- Compare view should require tablet/desktop width for synchronized charts; on mobile, show summary deltas and prompt to use a wider screen for full compare.
- Keep critical freshness/read-only/provenance badges sticky across breakpoints.

## Acceptance checklist

- [ ] Historical Replay is reachable beside, not inside, the Live Monitor core layout.
- [ ] Live Monitor remains the default landing surface.
- [ ] Replay History can browse prior sanitized sessions without exposing raw broker/account/model internals.
- [ ] Replay Detail can step through event order and show state at the selected point.
- [ ] Compare can select two sessions and show baseline/candidate deltas.
- [ ] Empty, loading, malformed, stale, degraded, and no-results states are explicit.
- [ ] Receipt/provenance details are visible on demand.
- [ ] No UI element implies live trading control, approval, mutation, or strategy tuning.
- [ ] Mobile/tablet layouts degrade gracefully and preserve safety/provenance signals.
- [ ] This recommendation remains implementation-neutral until a separate execution packet is approved.
