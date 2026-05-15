# AWS shadow comparison daily intake/preflight — 2026-05-14

## Verdict
PASS_SHADOW_PREFLIGHT_DRY_RUN

## Intake decision
- CK stock-code batch before 09:00 TPE: yes, provided at `2026-05-14 08:53`
- Selection source: `ck_provided_stock_code_batch`
- Symbol count: 28
- Symbols: `2303, 2313, 2301, 6282, 3665, 4919, 2454, 4977, 4979, 3363, 3653, 3661, 7750, 3707, 2449, 6805, 6442, 3189, 8112, 8271, 4967, 1711, 6202, 4968, 6568, 3552, 1533, 6229`

This supersedes the earlier fallback to the existing AWS sim watchlist.

## Safety boundary
- Distinct from existing AWS sim: true
- EC2 start/stop/lifecycle mutation: not performed
- Live broker orders: not submitted
- Remote SSM/EC2 command: not run
- Local/read-only preflight only

## Receipts
- Repo run dir: `runs/shadow-comparison/2026-05-14-daily-intake-preflight-0856`
- State receipt: `/root/.openclaw/workspace/.state/aws-shadow-comparison-intake-20260514-0856/daily-intake-preflight-receipt.json`
- CK-provided symbols: `/root/.openclaw/workspace/.state/aws-shadow-comparison-intake-20260514-0856/ck-provided-symbols-20260514-0853.json`
- Preflight summary: `/root/.openclaw/workspace/.state/aws-shadow-comparison-intake-20260514-0856/shadow_lane_preflight_summary.json`

## Next
Use CK-provided 28-symbol batch for today’s AWS shadow comparison intake. Keep observer-only/no-order/no-lifecycle invariant.
