# Legacy equivalence gap analysis — 2026-05-10

## Verdict

Yes: `steamer-card-engine` does not yet fully match the whole legacy trading mechanism. The gap is not just one missing strategy-card parameter. It is a boundary mismatch: the legacy bot blends signal gate, feature pipeline, active universe, runtime risk, broker/order state, and recorder behavior in one live loop; current card-engine cards mostly describe strategy family parameters plus capital/risk policy, but not the entire decision-producing runtime contract.

## What currently matches

- Pure `REV_SHORT_AFTER_UP` gate semantics can match historical `decisions.jsonl.state` exactly on compatible policy dates.
- Core price-path state can be reconstructed from recorded ticks if we use exchange `time`, ignore pre-open trial ticks, and handle same-timestamp ordering ambiguity.
- B-vs-C semantics can be made exact when C is generated from B state through card-engine gate evaluator.

## What does not fully match yet

### 1. Active universe / target-list contract

Legacy only evaluates symbols in its runtime active target list and account/session filters. Raw ticks contain more symbols than historical decisions. Card/deck manifests have `symbol_pool` / `symbol_scope`, but no explicit per-run active-universe lineage derived from the live bot.

Needed surface:

```text
RunUniverseSpec
- symbols evaluated
- source: config/list/runtime filter
- exclusions and reasons
- effective timestamp/date
```

This belongs more in scenario/run manifest than in an individual strategy card.

### 2. Market-data observation policy

Legacy state updates only on open/continuous ticks for price path; pre-open trial ticks are recorded but should not seed `open_px`, `max_seen`, or `min_seen`. Legacy also uses exchange `time`, not recorder receive time, for `now_ts`.

Needed surface:

```text
MarketObservationPolicy
- timestamp source: exchange_time_us
- include flags: isOpen/isContinuous
- exclude flags: isTrial for state path
- same timestamp ordering rule
```

This belongs in ScenarioSpec / event-source contract.

### 3. Feature pipeline spec

The card schema lists `feature_requirements`, but not enough to reproduce legacy feature values:

- time-aware EMA formula and seed
- zigzag threshold/hysteresis/cooldown/min-ticks
- slope windows and resample/median3 denoise method
- `sweet_ok` exact bounds and open/continuous differences
- high-update tolerance / `new_high_recent`

Needed surface:

```text
FeaturePipelineSpec
- feature_id/version
- formulas
- timestamp source
- warmup behavior
- tolerance/equality rules
```

This is not simply a strategy card parameter; it is shared substrate required by all cards.

### 4. Runtime policy lineage

The full sweep mismatches are mostly `policy_lineage`: historical dates used different runtime logic or config (`now_time_3` vs `now_time_5`, trend-conflict presence, honey-sweet semantics, etc.).

Needed surface:

```text
PolicyLineageSpec
- effective config hash
- legacy commit/hash if available
- scenario group id
- rule-version labels
```

This belongs in run/evidence metadata and scenario grouping.

### 5. Risk/order-layer decisions

Historical `decisions.jsonl` sometimes includes `no_funds`, `lot_limit_reached`, or entry-pause/runtime blockers. These are not pure strategy-card gate reasons.

Needed surface:

```text
RuntimeDecisionLayer
- gate_decision
- risk_decision
- sizing_decision
- order_decision
- final_decision
```

Card should stay pure signal unless explicitly promoted to a full execution card. Risk/order belongs in deck/execution policy and simulator/runtime receipts.

### 6. Recorder semantics

`decisions.jsonl` records every gate evaluation, and sometimes records extra system decisions after the initial gate pass. The row count and reason distribution therefore depend on recorder placement, not just strategy semantics.

Needed surface:

```text
DecisionTraceSchema
- row kind: gate_eval | risk_block | order_block | final_decision
- parent decision id / causality
- symbol/timestamp key
```

## Schema recommendation

Do not overload strategy card with everything.

Recommended split:

1. **Card manifest**: pure strategy signal family and strategy-owned parameters.
2. **Deck manifest**: capital/risk/execution-policy binding and allowed cards.
3. **ScenarioSpec**: event source, session slice, market clock, timestamp semantics.
4. **RunUniverseSpec**: evaluated symbols and target-list lineage.
5. **FeaturePipelineSpec**: exact indicator/state formulas and warmup behavior.
6. **DecisionTraceSchema**: layered decisions and causality.
7. **PolicyLineageSpec**: historical runtime/config grouping.

## Near-term implementation order

1. Keep `REV_SHORT_AFTER_UP` card/gate pure.
2. Add `triangle_compare` and classify A/B/C gaps at invariant level.
3. Add explicit `RunUniverseSpec` and `MarketObservationPolicy` to replay artifacts.
4. Expand latest-legacy replay feature reconstruction: sweet range, EMA, zigzag, slope.
5. Only then attempt exact per-symbol/timestamp matching beyond pre-09:30 smoke.

## Current artifact evidence

- Compatible decision-state verifier: `runs/legacy-equivalence/2026-05-10-revshort-compatible-multiday/`
- Lineage classifier: `runs/legacy-equivalence/2026-05-10-revshort-lineage/`
- Tick probes: `runs/legacy-equivalence/2026-05-10-tick-probe-20260129/`, `runs/legacy-equivalence/2026-05-10-tick-probe-20260122/`
- Latest legacy replay smoke: `runs/legacy-equivalence/2026-05-10-latest-legacy-replay-20260129-pre930/`

## Topology impact

No topology change. This is repo-local verifier/replay tooling only.
