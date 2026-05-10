# Legacy tick reconstruction feasibility probe

## Verdict
PASS_FEASIBLE

- dataset: `dt3/20260129`
- gate: `REV_SHORT_AFTER_UP`
- sampled decisions: 800
- symbols with ticks: 10
- tolerance: 1e-07

## Field reconstruction

| field | compared | mismatches | match rate | max abs error | mean abs error |
|---|---:|---:|---:|---:|---:|
| px | 800 | 0 | 1.0000 | 0.5 | 0.010187499999999971 |
| open_px | 800 | 0 | 1.0000 | 0.0 | 0.0 |
| max_seen | 800 | 0 | 1.0000 | 0.10000000000000142 | 0.0004999999999999805 |
| min_seen | 800 | 0 | 1.0000 | 0.0 | 0.0 |

## Interpretation
This probe only tests whether core price-path fields can be reconstructed from ticks at historical decision timestamps.
It does not yet reconstruct EMA, slope, zigzag, VCP, or risk/order state.
