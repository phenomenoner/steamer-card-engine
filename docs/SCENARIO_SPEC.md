# Scenario Spec

## Purpose

Define a shared scenario identity contract so `baseline-bot` and `steamer-card-engine` can be compared on the **same** test slice, not just "same day-ish" runs.

This is a companion contract to `SIM_ARTIFACT_SPEC.md`.

## Scope

In scope:

- stable `scenario_id`
- symbol set identity
- session date + intraday slice identity
- market event source identity
- timezone/calendar identity
- execution/cost model knobs
- determinism posture and seed disclosure

Out of scope:

- scheduling/orchestration details
- private operator data paths
- runtime implementation claims

## v1 shape (`scenario-spec/v1`)

ScenarioSpec can be emitted as `scenario-spec.json` (recommended) or represented equivalently in `run-manifest.json` fields.

```json
{
  "scenario_spec_version": "scenario-spec/v1",
  "scenario_id": "tw-gap-reclaim.twse.2026-03-11.full-session",
  "symbol_set": {
    "mode": "explicit-list",
    "symbols": ["2330", "2317"],
    "symbol_set_id": "tw-top-liquidity-20@2026-03-11"
  },
  "session_slice": {
    "session_date": "2026-03-11",
    "slice_label": "full-session",
    "start_local": "09:00:00",
    "end_local": "13:30:00"
  },
  "event_source": {
    "source_id": "twse-tick-v3",
    "source_kind": "recorded-stream",
    "source_ref": "dataset://twse/ticks/v3/2026-03-11",
    "time_range_utc": {
      "start": "2026-03-11T01:00:00Z",
      "end": "2026-03-11T05:30:00Z"
    },
    "adjustment_mode": "raw"
  },
  "market_clock": {
    "timezone": "Asia/Taipei",
    "calendar": "TWSE"
  },
  "execution_model": {
    "fee_model": "tw_cash_fee_v1",
    "tax_model": "tw_cash_tax_v1",
    "slippage_model": "none",
    "rounding_rule": "twd_round_half_up",
    "fill_model": "sim-fill-v1"
  },
  "determinism": {
    "mode": "fixed-seed",
    "random_seed": 42,
    "notes": null
  }
}
```

## Required fields (v1)

- `scenario_spec_version`
- `scenario_id`
- `symbol_set.mode` and either `symbol_set.symbols` or `symbol_set_id`
- `session_slice.session_date`
- `session_slice.start_local`, `session_slice.end_local`
- `event_source.source_id`
- `event_source.source_kind`
- `event_source.adjustment_mode`
- `market_clock.timezone`
- `market_clock.calendar`
- `execution_model.fee_model`
- `execution_model.tax_model`
- `execution_model.slippage_model`
- `execution_model.rounding_rule`
- `execution_model.fill_model`
- `determinism.mode`
- `determinism.random_seed` (nullable but explicit)

## `scenario_id` rules (v1)

`scenario_id` should be:

- stable for the same semantic scenario
- human-readable
- free of machine-local paths/secrets

Suggested composition:

`<strategy_or_deck>.<market>.<session_date>.<slice_label>[.<variant>]`

Use a separate hash/fingerprint (if needed) for strict equality checks; avoid making `scenario_id` itself unreadable.

## Determinism posture

- `fixed-seed`: random seed pinned; expected for baseline comparisons.
- `best-effort`: no intentional randomness, but runtime/event ordering may still vary.
- `nondeterministic`: randomness or nondeterministic scheduling is expected.

For baseline-vs-candidate parity checks, prefer `fixed-seed` whenever the simulator allows it.

## Relationship to SIM artifacts

- `run-manifest.json` remains the canonical run envelope.
- ScenarioSpec defines **what scenario was intended**; run-manifest/log files show **what happened**.
- Comparator should fail fast when ScenarioSpec identity mismatches before computing PnL/fill diffs.

## Adoption note (current reality)

At the docs seed stage, ScenarioSpec is a contract target.

- It is acceptable that current runtime paths do not yet emit full `scenario-spec.json`.
- Until then, teams should keep ScenarioSpec-equivalent fields explicit in `run-manifest.json`.
- Do not claim runtime parity support until ScenarioSpec is actually emitted and validated in both lanes.
