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

Use a separate fingerprint for strict equality checks (required for M1 evidence runs; see `scenario_fingerprint` below); avoid making `scenario_id` itself unreadable.

## `scenario_fingerprint` (v1; required for M1 evidence)

For M1 evidence runs, `scenario_fingerprint` is the **hard equality key** (not `scenario_id`).

Definition (normative):

- `scenario_fingerprint` = `sha256_hex(canonical_json_bytes(ScenarioSpec))`
- the canonical JSON is produced by:
  - UTF‑8 encoding
  - object keys **sorted**
  - **no insignificant whitespace**
  - non-ASCII characters kept as-is (NOT `\uXXXX` escaped)
  - arrays preserved in-order
  - excluding any `scenario_fingerprint` field itself (if present in a wrapper)

Practical rule:

- If you have `scenario-spec.json`, compute the fingerprint as the SHA256 of its **canonicalized** JSON payload.
- If ScenarioSpec is embedded in `run-manifest.json`, compute the fingerprint over the embedded ScenarioSpec object with the same canonicalization rules.

Reference pseudocode:

```python
import hashlib, json

def canonical_json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def scenario_fingerprint(spec_obj: dict) -> str:
    return hashlib.sha256(canonical_json_bytes(spec_obj)).hexdigest()
```

Comparator rule:

- Evidence comparisons must fail fast if `scenario_fingerprint` differs between baseline and candidate.

## Determinism posture

- `fixed-seed`: random seed pinned; expected for baseline comparisons.
- `best-effort`: no intentional randomness, but runtime/event ordering may still vary.
- `nondeterministic`: randomness or nondeterministic scheduling is expected.

For baseline-vs-candidate parity checks, prefer `fixed-seed` whenever the simulator allows it.

## Relationship to SIM artifacts

- `run-manifest.json` remains the canonical run envelope.
- ScenarioSpec defines **what scenario was intended**; run-manifest/log files show **what happened**.
- Comparator should fail fast when ScenarioSpec identity mismatches before computing PnL/fill diffs.
- For M1 SIM-comparability evidence runs, equality of a ScenarioSpec fingerprint/hash should be treated as a hard requirement; human-readable `scenario_id` alone is not sufficient.

## Adoption note (current reality)

At the docs seed stage, ScenarioSpec is a contract target.

- It is acceptable that current runtime paths do not yet emit full `scenario-spec.json`.
- Until then, teams should keep ScenarioSpec-equivalent fields explicit in `run-manifest.json`.
- Do not claim runtime parity support until ScenarioSpec is actually emitted and validated in both lanes.
