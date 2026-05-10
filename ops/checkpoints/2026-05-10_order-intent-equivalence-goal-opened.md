# WAL — order intent equivalence goal opened — 2026-05-10

## Change

Opened the legacy-vs-steamer-card-engine order-intent equivalence goal and landed replay order-intent compare v1.

## Why now

CK's real target is replacing the legacy bot with `steamer-card-engine`; before real-money validation, we need high confidence that both engines emit the same order intent under the same market/account state. CK also requested an AWS shadow comparison plan that reuses the existing daily sim machine without start/stop conflicts.

## Artifacts

```text
ops/execution-packets/2026-05-10_order-intent-equivalence-goal.packet.md
src/steamer_card_engine/order_intent_compare.py
tests/test_order_intent_compare.py
docs/AWS_SHADOW_COMPARISON_LANE_PLAN_2026-05-10.md
docs/receipts/2026-05-10_order_intent_equivalence_goal_opened.md
runs/legacy-equivalence/2026-05-10-order-intent-20260123/
runs/legacy-equivalence/2026-05-10-order-intent-20260127/
runs/legacy-equivalence/2026-05-10-order-intent-20260129-pre930-independent/
```

## Results

Replay order-intent v1 checks entry-order intent signature:

```text
symbol, action, side, quantity, price_basis, order_type, order_time_in_force
```

Historical actual-order smoke days:

```text
20260123: PASS_ENTER_INTENT_SMOKE_ONLY, independent_candidate=false, live_replacement_confidence=false
  legacy enter decisions: 2
  actual legacy enter order_submit rows: 2

20260127: PASS_ENTER_INTENT_SMOKE_ONLY, independent_candidate=false, live_replacement_confidence=false
  legacy enter decisions: 2
  actual legacy enter order_submit rows: 2
```

Independent candidate no-entry smoke:

```text
20260129 <=09:30: PASS_ENTER_INTENT_SMOKE_INDEPENDENT_CANDIDATE, independent_candidate=true, live_replacement_confidence=false
  legacy enter decisions: 0
  candidate enter decisions: 0
```

## Critical truth label

The actual-order smokes use legacy decisions as candidate input, so candidate-vs-legacy comparison is tautological there. The meaningful check is legacy enter decision -> actual legacy order_submit shape. The independent 20260129 smoke has no entry orders. Therefore the current evidence is necessary but not sufficient and must not be interpreted as live replacement confidence.

## AWS schedule inspection

Existing daily EC2 sim lifecycle specs found:

```text
08:25 power-on/readiness        5137f344-041a-48be-933e-edd7ce34607f
08:35 online sim kickoff        e7ee7135-1378-40bf-a5c6-e23aa8757648
08:45 verify+autoheal           337bf8c5-bde8-4ab8-af54-36cbba4c5dbd
13:40 archive/upload            32bf7bac-be39-443d-bf7d-30d2fb496b50
13:46 stop guardrail            c2eeb4f3-6a84-4910-ac7a-25938dda18da
```

Live `openclaw cron list` showed only `c2eeb4f3-6a84-4910-ac7a-25938dda18da` as current stop guardrail. A stale local spec referenced `0e831eea-ceff-42c6-b904-740b76dc3745`; do not treat that as live unless future readback says otherwise.

## Decision

Do not install a new lifecycle cron. Future shadow lane should be an observer worker launched by the existing 08:35 kickoff and archived by the existing 13:40 archive job.

## Verification

```text
uv run pytest tests/test_order_intent_compare.py tests/test_triangle_compare.py tests/test_legacy_replay.py tests/test_legacy_lineage_and_tick_probe.py tests/test_legacy_equivalence.py tests/test_sim_compare.py -q
```

Observed: `29 passed`.

## Rollback

Revert the local commit for this WAL and related files. No live topology changed.

## Topology

Unchanged in this slice. AWS shadow lane is plan/dry-run only; no cron added/enabled.
