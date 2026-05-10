# AWS shadow comparison timing gap closed — 2026-05-11

## Verdict

Timing gap root cause found and fixed for the independent replay actual-entry smoke set.

```text
order shape parity: PASS
timing parity: PASS
live_replacement_confidence: false
```

Live replacement confidence remains false because broker/account snapshots, exit/stop/trailing parity, pending order lifecycle, and live AWS same-machine observer enablement are still not complete.

## Root cause

The remaining timing difference was caused by replay feature drift in `slope_down_ok` sampling.

Legacy runtime does not run regression directly on raw ticks. It does:

```text
recent ticks -> resample_ticks_to_seconds(last price per second, forward-fill) -> median3_filter -> regression angle
```

The replay path had been calculating slope directly over raw tick observations. That made slope thresholds cross at different times, producing early candidate enter intents.

## Patch

```text
src/steamer_card_engine/legacy_replay.py
  - added pure-Python resample_and_median3_for_angle
  - regression_angle now mirrors legacy resample + median3 + angle path
```

This builds on the prior patch that restored legacy's three-stage slope fallback:

```text
sl_1 < threshold_1
OR (sl_1 < 0 AND sl_2 < threshold_2)
OR (sl_1 < 0 AND sl_2 < 0 AND sl_3 < threshold_3)
```

## Before / after

### Original independent replay

```text
20260123 max_abs_delta_seconds = 684.645048
20260127 max_abs_delta_seconds = 8.797583
```

### After slope fallback fix only

```text
20260123 max_abs_delta_seconds = 191.042596
20260127 max_abs_delta_seconds = 8.797583
```

### After resample + median3 fix

```text
20260123 max_abs_delta_seconds = 0.041462
20260127 max_abs_delta_seconds = 0.047904
```

Both are within the current 2-second timing tolerance.

## Final candidate timings

```text
20260123
  2367 candidate 09:39:41.289333 vs actual 09:39:41.330
  3323 candidate 09:47:08.556538 vs actual 09:47:08.598

20260127
  1301 candidate 10:26:01.105096 vs actual 10:26:01.153
  2337 candidate 11:13:53.654741 vs actual 11:13:53.699
```

## Artifacts

```text
runs/legacy-equivalence/2026-05-11-latest-legacy-replay-20260123-resamplefix/
runs/legacy-equivalence/2026-05-11-latest-legacy-replay-20260127-resamplefix/
runs/legacy-equivalence/2026-05-11-order-intent-resamplefix-20260123/
runs/legacy-equivalence/2026-05-11-order-intent-resamplefix-20260127/
```

## Interpretation

For the current two historical actual-entry days, independent replay now matches legacy actual enter order shape and timing.

This closes the specific `clock_alignment_diff` blocker for entry-order replay smoke, but it does not close the broader real-money replacement gate.

## Remaining gates before real-money validation

```text
- broker/account snapshot parity
- exit/stop/trailing order intent reconstruction
- pending order lifecycle parity
- AWS same-machine shadow observer enablement and multiple stable daily receipts
```
