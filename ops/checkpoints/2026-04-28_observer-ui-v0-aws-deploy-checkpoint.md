# 2026-04-28 — Steamer Observer UI v0 AWS deploy checkpoint

## Verdict

Steamer Observer UI v0 was deployed to the existing AWS demo observer host and is browser-openable.

This was a read-only observer UI deployment only. No broker control, live execution authority, security-group widening, new public port, or credential/routing exposure was added.

## Local implementation scope

Implemented UI slices:

- Observer shell hierarchy: `Monitor / Replay History / Compare unavailable`
- Read-only trust strip and live/replay identity separation
- Live freshness vs stream-link status split, including textual sequence-gap cue
- State Reconciliation panel for orders / fills / position
- Explicit `derived`, `empty`, `unavailable`, degraded-state copy
- Chart marker legend and replay frame affordance
- Receipt Drawer / Trust Anchor with sanitized receipt refs
- TypeScript env typing fix via `frontend/src/vite-env.d.ts`

## Local verifier receipts

```text
VITE_STEAMER_SURFACE=observer npm --prefix frontend run build -> pass
./frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json -> pass
uv run pytest tests/test_dashboard.py tests/test_observer_sim.py tests/test_observer_bridge.py -q -> 33 passed
forbidden bundle scan -> pass
required UI text scan -> pass
```

Forbidden scan terms included write/mutation and leakage indicators:

```text
/api/orders, /api/cancel, /api/modify, admin, secrets,
account_id, routing_id, bearer, aws_secret, aws_access_key,
/Users/, /home/, submit_order, cancel_order, modify_order, broker_token
```

## QA / UIUX review receipts

- QA/safety review: conditional pass, no blockers.
  - Fixed after review: neutralized derived-state success coloring, hardened receipt ref sanitizer for protocol/query/fragment cases, removed dead diagnostics copy, hid empty compare ref.
- UIUX review: conditional pass, no blockers.
  - Fixed after review: textual `GAPS: N` stream cue, inline trust-strip dedupe, replay bundle pill uses sanitized receipt basename, live session label surfaced.

## AWS target

- AWS profile: `lyria-trading-ops`
- Region: `ap-east-2`
- Instance: `i-037aa8c8a534e878f`
- Current public IP during deploy: `43.213.18.125`
- URL: `http://43.213.18.125/`
- Code commit deployed: `e0ab4e0`
- Release path: `/opt/trading/releases/steamer-card-engine-observer-ui-v0-20260428T051549Z-e0ab4e0`
- Staged bundle: `s3://lyria-trading-ops-975050019139-ap-east-2/staging/steamer-card-engine-observer-ui-v0-20260428T051549Z-e0ab4e0.tar.gz`
- Runtime env:

```text
STEAMER_OBSERVER_BUNDLE_JSON=/opt/trading/shared/steamer-observer-demo/observer.bundle.json
STEAMER_OBSERVER_INCLUDE_MOCK=0
PYTHONPATH=<release>/src
```

Service command:

```bash
python -m uvicorn steamer_card_engine.dashboard.api:create_app --factory --host 0.0.0.0 --port 80
```

## Deployment notes

The remote host had no active observer process on port 80 at deploy start, but SSM was online. The first minimal package lacked `comparisons/`, which the observer repository still touches during app boot for fixture fallback. The deployed release therefore symlinks these runtime fixture/context directories from the previous known-good observer release:

```text
comparisons -> previous release
runs        -> previous release
examples    -> previous release
docs        -> previous release
ops         -> previous release
```

This did not change execution authority or browser write surface. It is a packaging compatibility shim for the current demo topology.

## Remote smoke receipts

External smoke from operator host:

```text
GET http://43.213.18.125/api/health -> {"status":"ok"}
GET http://43.213.18.125/ -> <title>Steamer Observer Monitor</title>
GET http://43.213.18.125/api/observer/sessions -> 1 session, sim-2026-03-13-2330, freshness=fresh
remote frontend bundle required text -> State Reconciliation / Receipt Drawer / Trust Anchor / GAPS: / NO BROKER CONTROL / derived · not trust anchor present
remote frontend forbidden scan -> pass
remote /api/openapi.json mutation spot scan -> pass
observer payload leak spot scan -> pass
```

Payload spot review checked:

- `/api/observer/sessions`
- `/api/observer/sessions/sim-2026-03-13-2330/bootstrap`
- `/api/openapi.json`

No spot hits for account / credential / secret / token / subnet / vpc / broker / routing_id / aws_access_key strings.

## Kill switch

Disable the exposed observer service without touching trading engine paths:

```bash
pkill -f 'uvicorn.*steamer_card_engine.dashboard.api:create_app'
# or, if needed:
fuser -k 80/tcp
```

## Topology statement

Temporary demo topology remains active: the existing AWS managed VM runs one read-only observer/dashboard uvicorn process on port 80 for CK browser review.

No live execution authority, broker control wiring, auth boundary widening, public port widening, or real-money action was added in this pass.

## Known limits

- URL is HTTP demo exposure, not hardened authenticated/TLS production.
- Mounted session is the sanitized sim observer bundle from the existing demo path.
- Symlinked fixture/context directories preserve current demo compatibility; package contract should be tightened later.
- Suitable for CK browser review, not broader/public reuse.

## Visual parity follow-up

After CK reviewed the first deployed page, the UI was judged too close to the older engineering dashboard and too far from the design artifact. A visual parity CSS pass was applied and redeployed to the same demo host.

- Commit: `674aa95` (`style(observer): align ui v0 with design console density`)
- Release path: `/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-20260428T053753Z-674aa95`
- Staged bundle: `s3://lyria-trading-ops-975050019139-ap-east-2/staging/steamer-card-engine-observer-ui-v0-visual-20260428T053753Z-674aa95.tar.gz`

Visual pass changed only CSS/layout density and did not alter API/backend behavior:

- warmer v1-style palette
- sticky compact top navigation
- full-width operator console layout
- 340px reconciliation rail
- reduced card gaps and rounded-card feel
- chart/rail split closer to design artifact

Remote smoke after visual pass:

```text
GET /api/health -> {"status":"ok"}
GET / -> <title>Steamer Observer Monitor</title>
remote CSS markers -> #d97757 / 340px rail / sticky nav / backdrop-filter / active tab underline present
remote JS markers -> State Reconciliation / Receipt Drawer / Trust Anchor / GAPS: present
GET /api/observer/sessions -> 1 session, sim-2026-03-13-2330, freshness=fresh
forbidden scan -> pass
```
