# 2026-04-24 — steamer-card-engine observer-first monitor spec

## Verdict

Cut the next product slice as an **observer-first monitor**, not as another tab in the legacy Mission Control shell.

The current repository already proves the important data path: simulated lifecycle artifacts can become sanitized observer bundles, mount through the read-only observer API, and render chart / orders / fills / position / health in the browser. The remaining product mismatch is the surrounding shell and activation posture.

## Promise

A browser-openable read-only trading monitor for exactly one sanitized engine session.

It should answer, at a glance:

1. What session am I looking at?
2. Is the data fresh, lagging, stale, or degraded?
3. What is the latest price shape?
4. What position / order / fill state is visible?
5. What just happened, in append-only event order?
6. Can the browser reconnect without sequence drift?

It must not become a control plane, strategy explanation UI, or generic dashboard.

## Non-goals

- No browser-side execution controls.
- No broker/account/raw runtime payloads in browser-visible JSON.
- No strategy thresholds, score bands, model features, or alpha-bearing internals.
- No multi-session orchestration in this slice.
- No public URL widening before auth/network boundary is explicit.

## Current truth

Already true:

- observer repository boundary exists
- `STEAMER_OBSERVER_BUNDLE_JSON=<path[:path2...]>` mounts sanitized bundles
- `STEAMER_OBSERVER_INCLUDE_MOCK=0` can hide the mock session
- sim lifecycle events can project:
  - `order_submitted`
  - `order_acknowledged`
  - `fill_received`
  - `position_updated`
- dashboard tests cover mount / bootstrap / candles / timeline / stream
- frontend build passes

Still false / incomplete:

- hosted page is still a legacy Mission Control shell with observer as one tab
- observer-only deployment still drags unrelated fetches and failure surfaces
- bundle writer is not yet atomic, despite the emitter contract requiring atomic replace
- frontend does not explicitly model empty session, websocket connection state, or reconnect posture
- remote AWS activation is not yet security-hardened beyond demo bring-up

## Product cut

### Slice A — observer-only shell split

Goal: make the observer deployment path load only the observer surface.

Acceptance:

- an observer-only app path/mode renders `ObserverSurface` without fetching:
  - `/api/dates`
  - `/api/strategy-powerhouse`
  - `/api/strategy-pipeline`
  - live-sim deck APIs
- existing full dashboard mode still works
- observer-only mode preserves current chart / rail / timeline layout
- frontend build passes

Recommended implementation:

- add an environment-driven mode, e.g. `VITE_STEAMER_SURFACE=observer`
- in observer-only mode, `App` returns an observer monitor shell directly
- keep current tabbed dashboard as the default unless deployment chooses observer mode

### Slice B — atomic bundle write contract

Goal: make repo-native bundle writing match the private emitter contract.

Acceptance:

- `write_sim_observer_bundle_json()` writes to a same-directory temporary file and renames into place
- output directory creation remains automatic
- tests still prove emitted bundle mounts via `STEAMER_OBSERVER_BUNDLE_JSON`
- no partial bundle is visible to the observer repository during normal writes

### Slice C — operator-grade observer state UI

Goal: make stale / reconnect / empty-session states visible.

Acceptance:

- empty session list renders an explicit no-session state instead of throwing on `sessions.items[0]`
- websocket lifecycle is visible as `connecting / live / ended / closed / error`
- stale / degraded freshness gets a prominent banner, not only a small chip
- stream messages with `stream_end` update UI state
- malformed stream payloads do not root-crash the UI

### Slice D — local closure proof

Goal: prove the observer-first surface is locally ready for AWS demo redeploy.

Acceptance:

- targeted pytest passes:
  - `tests/test_observer_sim.py`
  - `tests/test_observer_bridge.py`
  - `tests/test_dashboard.py`
  - `tests/test_sim_compare.py`
- frontend build passes
- checkpoint records changed files, verifier receipts, and topology statement

## AWS activation gate

Only after local closure, run a separate AWS activation pass.

Required before claiming AWS activation:

- observer-only frontend bundle is deployed, not the legacy shell path
- mounted session uses a sanitized bundle path
- mock session disabled when validating private/session truth
- browser opens remotely
- refresh/reconnect is tested
- payload review confirms no sensitive field leakage
- remote boundary is clearly named as demo-only or authenticated/hardened
- kill switch path is documented

## Blade map

1. Spec freeze and second-brain review
2. Slice A: observer-only shell split
3. Slice B: atomic bundle writer
4. Slice C: visible connection/freshness states
5. Local verifier closure
6. AWS demo activation gate
7. WAL / checkpoint / stale-rule hygiene

## Topology statement

No execution topology change in this spec.
This recuts the browser/deployment product surface around the existing read-only observer sidecar boundary.
