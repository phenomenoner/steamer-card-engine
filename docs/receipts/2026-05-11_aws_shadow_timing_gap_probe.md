# AWS shadow comparison timing gap probe — 2026-05-11

## Question

Why does independent candidate replay emit the same order shape as legacy actual orders, but at different times?

## Verdict

The first root cause is confirmed: **candidate replay used a too-permissive slope-down gate**.

Legacy runtime slope gate is not just `slope_1 <= threshold_1`; it uses a three-stage fallback:

```text
sl_1 < threshold_1
OR (sl_1 < 0 AND sl_2 < threshold_2)
OR (sl_1 < 0 AND sl_2 < 0 AND sl_3 < threshold_3)
```

Before this probe, replay effectively treated the first-window threshold too loosely and did not reproduce the full fallback semantics. That caused early entries, especially on 20260123.

## Patch

```text
src/steamer_card_engine/legacy_equivalence.py
  - added slope_cond_threshold / slope_cond_threshold_2 / slope_cond_threshold_3 defaults

src/steamer_card_engine/legacy_replay.py
  - changed replay slope_down_ok to match legacy three-stage slope fallback
```

## Results

### Before slope-gate fix

```text
20260123 max_abs_delta_seconds = 684.645048
  2367 candidate 09:34:38.518883 vs actual 09:39:41.330
  3323 candidate 09:35:43.952952 vs actual 09:47:08.598

20260127 max_abs_delta_seconds = 8.797583
  1301 candidate 10:25:56.685231 vs actual 10:26:01.153
  2337 candidate 11:14:02.496583 vs actual 11:13:53.699
```

### After slope-gate fix

```text
20260123 max_abs_delta_seconds = 191.042596
  2367 candidate 09:36:30.287404 vs actual 09:39:41.330
  3323 candidate 09:46:55.139121 vs actual 09:47:08.598

20260127 max_abs_delta_seconds = 8.797583
  1301 candidate 10:25:56.685231 vs actual 10:26:01.153
  2337 candidate 11:14:02.496583 vs actual 11:13:53.699
```

Order shape parity remains green:

```text
20260123 candidate_enter_vs_actual_order_submit: match=true, count=2 vs 2
20260127 candidate_enter_vs_actual_order_submit: match=true, count=2 vs 2
```

Timing parity is still not green:

```text
20260123: clock_alignment_diff remains, mainly 2367 at ~191s early
20260127: small clock_alignment_diff remains, 4.47s / 8.80s
```

## Interpretation

This is no longer an unknown mismatch. The largest gap was materially reduced by restoring legacy slope gate semantics, which means the candidate was too early because replay feature/gate semantics were not exact.

Remaining likely causes:

```text
- slope regression sampling window still differs from runtime `slope_down_ok` data path
- ZigZag state update ordering may still differ at symbol-tick boundaries
- tick stream ordering / duplicated timestamp treatment differs
- runtime order placement happens after decision trace by a few seconds
- 20260123 2367 may have an additional runtime blocker/cooldown/feature-state divergence not yet modeled
```

## Next timing-specific TODO

```text
P0-next: reproduce legacy `slope_down_ok` sampling path exactly, including price queue source, timestamp cutoff inclusivity, min-span behavior, and duplicate timestamp ordering. Then rerun 20260123/20260127 timing compare.
```

## Live confidence

```text
live_replacement_confidence=false
```

Do not treat order-shape parity as timing/replacement parity.
