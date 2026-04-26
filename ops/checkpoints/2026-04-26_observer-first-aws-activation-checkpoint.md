# 2026-04-26 — observer-first AWS activation checkpoint

## Verdict

Observer-first monitor redeployed to the existing AWS demo host and is browser-openable.

URL:

- http://43.212.103.130/

## Instance / release

- AWS profile: `lyria-trading-ops`
- Region: `ap-east-2`
- Instance: `i-037aa8c8a534e878f`
- Public IP after start: `43.212.103.130`
- Release path: `/opt/trading/releases/steamer-card-engine-observer-first-20260426T153745Z-e3f3362-titlefix`
- Staged bundle: `s3://lyria-trading-ops-975050019139-ap-east-2/staging/steamer-card-engine-observer-first-20260426T153745Z-e3f3362-titlefix.tar.gz`

## Runtime env

```text
STEAMER_OBSERVER_BUNDLE_JSON=/opt/trading/shared/steamer-observer-demo/observer.bundle.json
STEAMER_OBSERVER_INCLUDE_MOCK=0
PYTHONPATH=/opt/trading/releases/steamer-card-engine-observer-first-20260426T153745Z-e3f3362-titlefix/src
```

Service command:

```bash
python -m uvicorn steamer_card_engine.dashboard.api:create_app --factory --host 0.0.0.0 --port 80
```

## Verification receipts

Remote host local smoke:

```text
GET /api/health -> {"status":"ok"}
GET / -> <title>Steamer Observer Monitor</title>
GET /api/observer/sessions -> sim-2026-03-13-2330, freshness=fresh
```

External smoke from operator host:

```text
GET http://43.212.103.130/api/health -> {"status":"ok"}
GET http://43.212.103.130/api/observer/sessions -> one sim observer session
observer-only frontend bundle forbidden API grep -> 0 hits for legacy dashboard APIs
```

Payload spot review:

- Checked `/api/observer/sessions`
- Checked `/api/observer/sessions/sim-2026-03-13-2330/bootstrap`
- Checked `/api/observer/sessions/sim-2026-03-13-2330/candles?limit=3`
- Checked `/api/observer/sessions/sim-2026-03-13-2330/timeline?limit=5`
- No spot hits for account / credential / secret / token / subnet / vpc / broker / routing_id / aws_access_key strings.

## Kill switch

Disable the exposed observer service without touching trading engine paths:

```bash
pkill -f 'uvicorn.*steamer_card_engine.dashboard.api:create_app'
# or, if needed:
fuser -k 80/tcp
```

## Topology statement

Temporary demo topology is active: the existing AWS managed VM is running one read-only observer/dashboard uvicorn process on port 80 for browser review.

No live execution authority, broker control wiring, auth boundary widening, or real-money action was added in this pass.

## Known limits

- URL is HTTP demo exposure, not the hardened authenticated/TLS boundary.
- Mounted session is the sanitized sim observer bundle from the existing demo path.
- This is suitable for CK browser review, not broader/public reuse.
