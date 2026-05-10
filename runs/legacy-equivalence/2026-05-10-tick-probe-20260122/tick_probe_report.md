# Legacy tick reconstruction feasibility probe

## Verdict
PASS_FEASIBLE

- dataset: `dt3/20260122`
- gate: `REV_SHORT_AFTER_UP`
- sampled decisions: 800
- symbols with ticks: 6
- tolerance: 1e-07

## Field reconstruction

| field | compared | mismatches | match rate | max abs error | mean abs error |
|---|---:|---:|---:|---:|---:|
| px | 800 | 0 | 1.0000 | 0.5 | 0.006625000000000023 |
| open_px | 800 | 0 | 1.0000 | 0.0 | 0.0 |
| max_seen | 800 | 0 | 1.0000 | 0.04999999999999716 | 6.249999999999645e-05 |
| min_seen | 800 | 0 | 1.0000 | 0.0 | 0.0 |

## Interpretation
This probe only tests whether core price-path fields can be reconstructed from ticks at historical decision timestamps.
It does not yet reconstruct EMA, slope, zigzag, VCP, or risk/order state.
