# 2026-04-12 — dashboard campaign-controller follow-up truth tightening

- status: done
- topology: unchanged
- scope: tighten the public/dashboard proof surface so campaign-controller readiness comes from campaign artifacts and current summary copy matches the closure-pack truth

## What changed
- `strategy_pipeline.py` summary now states the narrow public truth:
  - dispatch-ready for bounded research slices under guardrails
  - `research-autonomous-yes / attach-autonomous-no`
- readiness flags / stale-after values now derive from `STATE.json.autonomyReadiness` instead of hardcoded API values
- campaign state now carries `autonomyReadiness` as the machine-readable source-of-truth

## Verification
- `uv run pytest -q tests/test_dashboard.py`
- `frontend npm run build`
- `python3 projects/steamer/lanes/autonomous-slow-cook/tools/dispatch_stub.py --campaign-id 2026-04-failed-auction-short-cluster-slow-cook`

## Boundary
- read-only/dashboard/campaign-state tightening only
- no runtime activation change
- no attach authority change
