# Checkpoint — 2026-04-23 13:28 Asia/Taipei — observer private live attachment seam

## Line
`steamer-card-engine` live observer sidecar

## Current verdict
Proceed.
The line now has a rollbackable attachment seam for private live observer bundles without moving private mapping logic into the public-safe repo.

## What now stands
- Observer sidecar milestone landed locally.
- Observer private bridge landed locally.
- Observer API now reads from a repository/provider boundary instead of hard-coding one mock session id.
- Public-safe file attachment seam landed:
  - `STEAMER_OBSERVER_BUNDLE_JSON=<path[:path2...]>`
  - `STEAMER_OBSERVER_INCLUDE_MOCK=0|1`
- Attached bundles can provide `metadata + events` only; the repo-side bridge rebuilds bootstrap deterministically when `bootstrap` is omitted.
- Session list / bootstrap / candles / timeline / stream routes now work for attached sessions.

## Verifier state
- `uv run pytest tests/test_observer_bridge.py tests/test_dashboard.py -q` → `19 passed`
- `uv run ruff check src/steamer_card_engine/observer src/steamer_card_engine/dashboard/api.py tests/test_dashboard.py tests/test_observer_bridge.py` → pass
- `npm --prefix frontend run build` → pass

## Boundary that still holds
- observer remains structurally read-only
- public-safe repo still contains no private field mapping logic
- private adapter is still external to this repo surface
- remote auth / network hardening is still not the same thing as attachment; that phase remains ahead

## Next recommended move
Cut the first real **private live adapter bundle emitter** outside the public repo surface:
1. pick one truthful upstream source (`operator probe-session` / session manager / sanitized runtime receipt lane)
2. map it into `metadata + events` bundle output on a private runtime path
3. mount that path via `STEAMER_OBSERVER_BUNDLE_JSON`
4. prove one attached session renders and reconnects without contract drift or payload leakage

## Topology statement
Unchanged.
