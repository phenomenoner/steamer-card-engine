# 2026-04-28 — Observer UI v0 visual redeploy paused by live-sim cron

## Verdict

Steamer Observer UI v0 implementation and visual-parity redeploy are complete, but further live-demo browser review is paused because the AWS demo instance was later shut down by the live-sim cron lifecycle.

Do not treat the later unreachable demo URL as a UI deploy failure unless the instance is confirmed running and the observer process fails health checks.

## Current branch / commits

Repo: `/root/.openclaw/workspace/steamer-card-engine`
Branch: `feat/gemini-gamify-dashboard`

Relevant local commits:

```text
bad118e docs(observer): record visual parity redeploy
674aa95 style(observer): align ui v0 with design console density
a70babb docs(observer): record ui v0 aws deployment
e0ab4e0 feat(observer): ship ui v0 trust-first surface
```

Note: commits are local unless pushed separately.

## Implementation receipts

Implemented:

- Observer-only shell hierarchy with `Monitor / Replay History / Compare unavailable`
- Read-only trust strip and live/replay boundary language
- State Reconciliation panel for orders / fills / position
- Explicit derived / empty / unavailable / degraded presentation states
- Chart marker legend and replay frame affordance
- Receipt Drawer / Trust Anchor with sanitized receipt refs
- Visual parity CSS pass closer to the design artifact: warm palette, compact sticky nav, operator-console density, chart + 340px reconciliation rail

## Local verifier receipts

Last verified locally before AWS deploy/redeploy:

```text
VITE_STEAMER_SURFACE=observer npm --prefix frontend run build -> pass
./frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json -> pass
uv run pytest tests/test_dashboard.py tests/test_observer_sim.py tests/test_observer_bridge.py -q -> 33 passed
focused observer/history tests after visual pass -> 13 passed
forbidden/leak scans -> pass
```

## AWS deploy receipts before pause

Target:

```text
AWS_PROFILE=lyria-trading-ops
region=ap-east-2
instance=i-037aa8c8a534e878f
URL during deploy=http://43.213.18.125/
```

Initial UI v0 release:

```text
/opt/trading/releases/steamer-card-engine-observer-ui-v0-20260428T051549Z-e0ab4e0
s3://lyria-trading-ops-975050019139-ap-east-2/staging/steamer-card-engine-observer-ui-v0-20260428T051549Z-e0ab4e0.tar.gz
```

Visual parity redeploy release:

```text
/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-20260428T053753Z-674aa95
s3://lyria-trading-ops-975050019139-ap-east-2/staging/steamer-card-engine-observer-ui-v0-visual-20260428T053753Z-674aa95.tar.gz
```

Remote smoke after visual redeploy passed while the instance was running:

```text
GET /api/health -> {"status":"ok"}
GET / -> <title>Steamer Observer Monitor</title>
GET /api/observer/sessions -> 1 session, sim-2026-03-13-2330, freshness=fresh
remote CSS markers -> #d97757 / 340px rail / sticky nav / backdrop-filter / active tab underline present
remote JS markers -> State Reconciliation / Receipt Drawer / Trust Anchor / GAPS: present
forbidden scan -> pass
```

## Boundary statement

No broker control, live execution authority, credential/routing exposure, new public port, or security-group widening was added.

Deployment used the existing demo observer host and existing port 80 exposure only.

## Known packaging shim

The minimal deploy package still depends on symlinking fixture/context directories from the previous known-good observer release:

```text
comparisons -> previous release
runs        -> previous release
examples    -> previous release
docs        -> previous release
ops         -> previous release
```

This is a demo compatibility shim, not the desired final deploy contract. Tighten packaging later.

## Resume steps

When CK wants to resume live browser review:

1. Confirm/start the AWS demo instance:

```bash
AWS_PROFILE=lyria-trading-ops AWS_REGION=ap-east-2 aws ec2 describe-instances --instance-ids i-037aa8c8a534e878f --query 'Reservations[0].Instances[0].{State:State.Name,PublicIp:PublicIpAddress}' --output json
```

2. If stopped, start it only with explicit operator intent.

3. Re-run or inspect observer service on the latest visual release:

```text
/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-20260428T053753Z-674aa95
```

4. Expected runtime env:

```text
STEAMER_OBSERVER_BUNDLE_JSON=/opt/trading/shared/steamer-observer-demo/observer.bundle.json
STEAMER_OBSERVER_INCLUDE_MOCK=0
PYTHONPATH=/opt/trading/releases/steamer-card-engine-observer-ui-v0-visual-20260428T053753Z-674aa95/src
```

5. Expected service command:

```bash
python -m uvicorn steamer_card_engine.dashboard.api:create_app --factory --host 0.0.0.0 --port 80
```

6. Re-smoke:

```text
/api/health
/
/api/observer/sessions
remote asset markers
forbidden bundle scan
payload leak spot scan
```

## Stop gates

Stop before further AWS action if:

- the instance lifecycle is still controlled by a cron window not intended for review
- security group / public exposure changes are required
- mounted bundle path is missing or requires raw private payloads
- service start would interfere with live-sim/trading runtime paths
