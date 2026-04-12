# 2026-04-12 — dashboard campaign/controller fields for failed-auction-short

- status: done
- topology: unchanged
- scope: extend the Strategy Pipeline tab so operators can see the failed-auction-short campaign/controller truth directly from autonomous-slow-cook campaign artifacts

## What changed
- Strategy Pipeline API now reads the campaign pack for:
  - campaign id / status / phase
  - dispatchable
  - active candidate id
  - next action / worker type
  - cluster mode / window / max bounded slices
  - retry remaining
  - stale-after guidance
  - `research_autonomous` / `attach_autonomous` truth
- Frontend Strategy Pipeline tab now shows a dedicated **Campaign Controller** section.

## Verification
- `uv run pytest -q tests/test_dashboard.py`
- `python3 projects/steamer/lanes/autonomous-slow-cook/tools/dispatch_stub.py --campaign-id 2026-04-failed-auction-short-cluster-slow-cook`
- `frontend npm run build`

## Boundary
- read-only dashboard extension only
- no runtime activation was enabled by this slice
- attach authority remains human-gated
