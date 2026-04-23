# Checkpoint — 2026-04-23 17:12 Asia/Taipei — AWS observer demo bring-up and next-gap checkpoint

## Verdict
Proceed, but do not confuse this with the intended product surface.
The AWS-hosted observer demo is now browser-openable and no longer black-screening, but the shipped UI is still the older Steamer Mission Control shell rather than the intended observer-first live monitor.

## What is now true
- AWS managed live-sim instance was powered on and used as the temporary host.
- `steamer-card-engine` observer demo bundle was packaged, uploaded, extracted, and served from the instance.
- Browser-openable surface reached:
  - `http://43.213.47.31/`
- observer APIs, strategy-powerhouse, and strategy-pipeline were all made reachable from the hosted surface.
- frontend black-screen root causes were reduced and repaired enough for the page to render:
  - lightweight-charts v5 marker API mismatch fixed
  - lightweight-charts v5 series API mismatch fixed (`addSeries(CandlestickSeries, ...)`)
  - root error boundary added
  - chart-local error fallback added
- websocket runtime blocker on AWS fixed by installing websocket support and restarting uvicorn.

## Current truthful product gap
The current hosted page is **not yet** the intended observer-first live monitor.
It is still the older mission-control shell with observer as one tab.
That means the remaining blocker is no longer basic hosting, but **product-surface mismatch**.

## Next to-dos
1. split observer into a dedicated live-monitor surface, not a tab inside mission-control
2. redesign layout around chart-first trading-monitor ergonomics
   - main price panel
   - right rail for position / orders / fills / health
   - lower event timeline
3. trim non-observer surfaces out of this deployment path
   - strategy-powerhouse
   - strategy-pipeline
   - legacy live-sim dashboard shell
4. decide whether the first live-monitor pass should stay demo-backed or attach directly to AWS live-sim artifacts
5. replace temporary workspace/symlink compatibility hacks with a formal deploy contract
6. add minimal authenticated boundary before any broader reuse of the URL

## Deployment/runtime receipts
- AWS instance: `i-037aa8c8a534e878f`
- public IP during this bring-up: `43.213.47.31`
- staged repo bundle:
  - `s3://lyria-trading-ops-975050019139-ap-east-2/staging/steamer-card-engine-observer-20260423T083358Z-9f9371a.tar.gz`
- staged dashboard context bundle:
  - `s3://lyria-trading-ops-975050019139-ap-east-2/staging/steamer-dashboard-context-20260423T084357Z.tar.gz`
- latest staged frontend fix bundle:
  - `s3://lyria-trading-ops-975050019139-ap-east-2/staging/steamer-observer-frontend-20260423T090507Z.tar.gz`

## Topology statement
Temporary runtime topology changed for this demo bring-up only:
- one AWS-hosted uvicorn observer/dashboard process was started on the managed live-sim VM
- temporary symlink compatibility layer was added so old workspace-relative artifact paths could resolve

The intended longer-term product topology is still unresolved and should be redesigned around an observer-first surface.
