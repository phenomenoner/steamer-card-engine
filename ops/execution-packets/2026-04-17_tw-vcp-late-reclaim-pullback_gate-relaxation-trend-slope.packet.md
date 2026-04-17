# Execution packet — `tw-vcp-late-reclaim-pullback` minimal trend-slope gate relaxation

Status: **planning only / run pending / no activation implied**

## 1) Verdict

Choose the **gate-relaxation** lane only.
Do **not** draft a candidate-specific late-reclaim rule in this pass.

Reason:
- the latest loop-owned 3-day packet stayed at zero trade expression across all three clean archive-backed days
- the strongest repeated blocker in the underlying reports is the current family trend gate, not a clearly isolated candidate-specific failure
- inventing a bespoke late-reclaim rule now would overclaim beyond the evidence we actually have

## 2) Whole-picture promise

Answer one narrow question truthfully:

> if the current VCP family stack is left intact except for a minimal relaxation of `vcp_min_trend_slope`, does any trade expression appear for `tw-vcp-late-reclaim-pullback` under the same bounded replay window and same friction model?

If the answer is still no, the line gains strong evidence that the candidate is not merely buried by the current gate stack.
If the answer is yes, the next move can stay honest without inventing a new candidate-specific rule too early.

## 3) Recommended bounded slice

### Fixed comparison window
Use the same clean 3-day set already accepted by the loop:
- `20260211`
- `20260224`
- `20260225`

### Fixed execution/friction posture
Keep unchanged:
- execution model: `entry=ask, exit=bid`
- one trade per symbol/day
- `allow_blind_open=false`
- `stop_loss=-3`
- `take_profit=8`
- `trail_activate_at_pct=2.5`
- `trail_distance_pct=2`
- `vcp_window_sec=300`
- `vcp_tightness_pct=0.35`
- `vcp_breakout_vol_mult=2.5`

### One and only one gate change
Relax only:
- `vcp_min_trend_slope: 5.0 -> 2.0`

### Anchor ratio
Use the same comparison anchor already summarized in the latest loop packet:
- `dryup_ratio=0.8`

### Required outputs
For each day, record:
- `n_trades`
- `pnl_pct_sum`
- `pnl_pct_avg` if trades appear
- top gate reasons after the relaxation
- emitted trade list if any

## 4) Why this is the truthful lane

The current evidence points to gate suppression more directly than to candidate-specific rule weakness.

### Evidence read
From the accepted 3-day packet and cited raw reports:
- `20260211` remains zero-trade, with repeated top rejections shaped as `trend_not_strong_enough`
- those rejection examples include slopes near the current threshold, such as `2.16`, `2.07`, `2.03`, and `1.47`, while the active gate requires `>= 5.0`
- `20260225` is again dominated by `trend_not_strong_enough`, but many examples are still negative, so a minimal relaxation to `2.0` remains selective rather than collapsing the gate completely
- `20260224` is diagnostically thinner, but keeping the same day preserves comparability with the current accepted loop packet

This makes a **single-knob gate-relaxation** test cleaner than a bespoke candidate rewrite.

## 5) Contract / boundaries

### In scope
- one bounded replay/counterfactual follow-up
- same three days
- same friction model
- same family stack
- one gate change only: `vcp_min_trend_slope`

### Explicitly out of scope
- candidate-specific late-reclaim rule invention
- changing multiple gates at once
- widening the day set
- live-sim or broker-facing activation
- promotion claims

## 6) Honest outcome rubric

Allowed end states after the run:
- `backtest-pass` if objective-positive expression appears after friction with failure modes still bounded
- `hold` if trades appear but the result is not strong enough to promote
- `kill` if the minimal relaxation still produces no meaningful expression or only clearly non-credible expression
- `iterate` if some expression appears but one more equally bounded verifier is still needed

## 7) Verifier inputs / receipts grounding this packet

Primary loop truth:
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/projects/steamer/loops/steamer-alpha-harvest-loop/candidates/provisional/tw-vcp-late-reclaim-pullback.json`
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/projects/steamer/loops/steamer-alpha-harvest-loop/receipts/2026-04-16_bounded-backtest-packet_tw-vcp-late-reclaim-pullback_iterate_3day.md`
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/projects/steamer/loops/steamer-alpha-harvest-loop/BACKLOG.md`

Raw bounded-report inputs:
- `/workspace/steamer/reports/vcp-counterfactual-backtest-r6-20260211-20260224-024047+0800.json`
- `/workspace/steamer/reports/vcp-counterfactual-backtest-r6-20260224-20260224-142457+0800.json`
- `/workspace/steamer/reports/vcp-counterfactual-backtest-r6-20260225-20260225-142428+0800.json`

Historical candidate receipts:
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/projects/mandate-campaign-framework/campaigns/SL-C1-20260403-01/receipts/007_steamer_operator_gate_shadow_review_required.json`
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/projects/mandate-campaign-framework/campaigns/SL-C1-20260403-01/receipts/008_steamer_operator_gate_decision_replayed.json`
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/projects/mandate-campaign-framework/campaigns/SL-C1-20260403-01/artifacts/steamer/idea-scout/tw-vcp-late-reclaim-pullback.md`

Ownership / routing grounding:
- `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-26_backtest-loop-ownership-contract_with_strategy-powerhouse_and_mandate-framework.md`
- `/root/.openclaw/workspace/steamer-card-engine/ops/sprints/steamer-card-engine-p1-live-trading-capability-v0-sprint.md`

## 8) Expected downstream receipt shape

If this packet is run, the downstream receipt should state:
- baseline config and relaxed config
- same-day comparability preserved
- whether any trade expression appeared
- whether relaxation merely unlocked noise or produced credible signal
- final honest verdict: `backtest-pass` / `hold` / `kill` / `iterate`

## 9) Rollback / topology

Rollback posture:
- if this packet is rejected or never run, the latest truthful read remains the 3-day loop-owned `iterate` packet

Topology statement:
- runtime topology unchanged
- scheduler topology unchanged
- ownership topology unchanged
- this file is a bounded execution packet only, not a run receipt
