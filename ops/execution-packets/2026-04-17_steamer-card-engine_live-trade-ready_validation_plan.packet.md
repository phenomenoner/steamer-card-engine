# 2026-04-17 — steamer-card-engine live-trade-ready validation plan (reassessed to the true pre-real-money gate)

## Status
- retired in place
- retired_on: 2026-04-17
- topology: unchanged
- retirement_reason: all planned slices landed; this packet is no longer an active execution surface
- successor_surface: `docs/receipts/2026-04-17_live_trade_ready_validation_closure.md`
- target claim achieved: repo truthfully advances to **only real-money smoke remains**
- boundary: this packet still excludes actual real-money submission
- reassessed on: 2026-04-17
- closure receipt: `docs/receipts/2026-04-17_live_trade_ready_validation_closure.md`
- full suite: `74 passed in 23.79s`
- cross-validation: second-brain final review passed

## Verdict
Retired in place.
This packet has finished its job and now serves only as the historical blade map for how the line reached closure.
The live truth surface is the closure receipt: `docs/receipts/2026-04-17_live_trade_ready_validation_closure.md`.

## Whole-picture promise
Reach a truthful repo state where `steamer-card-engine` can say:
- validation smoke cards and deck are real repo artifacts, not prose-only placeholders
- the validation deck resolves into real runtime card factories
- deterministic entry, exit, and no-trade behavior are proven through repo runtime lanes, not only isolated unit tests
- operator preflight and bounded non-cash control flow pass on the validation deck
- non-cash dispatch-path proof is current and receipted
- the only remaining production-facing gate is one explicit real-money smoke attempt

Fake progress would be:
- treating smoke-card unit tests and manifest tests as if they already prove deck-to-runtime execution
- inheriting operator greenness from `tw_cash_intraday.toml` and pretending it transfers to `tw_cash_validation_smoke.toml`
- marking the current partial receipt as closure without new artifacts

## What is already closed
1. **Manifest / authoring contract**
   - `tests/test_manifests.py`
   - smoke cards + smoke deck validate and summarize correctly

2. **Authoring CLI surface**
   - `tests/test_cli.py`
   - `author validate-card` and `author inspect-deck --json` cover the smoke pack

3. **Deterministic smoke-card runtime unit behavior**
   - `src/steamer_card_engine/cards/validation_smoke.py`
   - `tests/test_validation_smoke_cards.py`
   - entry, exit-gated, and no-trade branches are covered

4. **Operator-control bounded smoke on the existing operator lane**
   - `tests/test_cli.py`
   - `status`, `arm-live`, `submit-order-smoke`, `flatten`, `preflight-smoke`, `live-smoke-readiness`

5. **Non-cash dispatch-path traversal**
   - receipt: `docs/receipts/2026-04-17_non_cash_dispatch_path_traversal.md`
   - bounded seven-step sequence is proven and receipted

## Recommended bounded slice plan

### Slice 5 — bind validation deck manifests to the runtime registry
Status: done (2026-04-17)

Landed artifacts:
- `src/steamer_card_engine/validation_runtime.py`
- `tests/test_validation_smoke_runtime_bridge.py`
- `docs/receipts/2026-04-17_validation_smoke_runtime_path.md`

Outcome:
- the validation deck now resolves through the repo runtime bridge into the real smoke-card factories
- the prior manifest/runtime split is closed by a single verifier-backed path

---

### Slice 6 — prove deterministic entry/exit/no-trade through replay or live-sim
Status: done (2026-04-17)

Landed artifacts:
- `docs/receipts/artifacts/2026-04-17_validation_smoke_runtime_path.json`
- `docs/receipts/2026-04-17_validation_smoke_runtime_path.md`

Proven scenarios:
1. entry accepted
2. blocked exit without `position_open`
3. exit after entry-state exists
4. explicit no-trade

Boundary held:
- deterministic runtime proof only
- no broker-connected behavior
- no strategy-alpha claims

---

### Slice 7 — rerun bounded operator smoke against the validation deck itself
Status: done (2026-04-17)

Landed artifacts:
- `docs/receipts/artifacts/2026-04-17_validation_smoke_operator_preflight.json`
- `docs/receipts/artifacts/2026-04-17_validation_smoke_operator_lane.json`
- `docs/receipts/2026-04-17_validation_smoke_operator_lane.md`
- `tests/test_validation_smoke_operator_lane.py`

Outcome:
- bounded operator proof now runs on `examples/decks/tw_cash_validation_smoke.toml` itself
- this proof is no longer inherited from `tw_cash_intraday.toml`
- boundary remains prepared-only / non-cash

---

### Slice 8 — close risk/gating and lifecycle packaging truthfully
Status: done (2026-04-17)

Landed artifacts:
- `docs/receipts/artifacts/2026-04-17_validation_smoke_readiness_bundle.json`
- validation-deck-specific blocker coverage in `tests/test_validation_smoke_operator_lane.py`

Outcome:
- lifecycle packaging is now reconstructable from one compact readiness bundle
- the bundle explicitly ties together manifest, runtime, operator, and dispatch-path proof

---

### Slice 9 — flip the repo claim with one consolidated readiness receipt
Status: done (2026-04-17)

Landed artifact:
- `docs/receipts/2026-04-17_live_trade_ready_validation_closure.md`

Outcome:
- the closure receipt cites the new artifacts from Slices 5-8
- the repo claim is now truthfully flipped to: only explicit real-money smoke remains

## Contract / boundary rules
- validation smoke cards exist for path proof, not alpha proof
- validation smoke deck must stay explicitly non-production
- cards may emit intents, never broker orders
- operator lane is the only surface allowed to approach live gates
- operator proof on `tw_cash_intraday.toml` does not automatically prove `tw_cash_validation_smoke.toml`
- a green non-cash packet must never be described as broker-connected readiness
- no slice may claim closure without a **new** artifact path

## Verifier plan
Executed verifier set:
1. focused pytest lane: `45 passed in 0.40s`
   - artifact: `docs/receipts/artifacts/2026-04-17_validation_smoke_pytest.txt`
2. full repo suite: `74 passed in 23.79s`
3. runtime bridge artifact: `docs/receipts/artifacts/2026-04-17_validation_smoke_runtime_path.json`
4. validation-deck preflight artifact: `docs/receipts/artifacts/2026-04-17_validation_smoke_operator_preflight.json`
5. validation-deck live-smoke artifact: `docs/receipts/artifacts/2026-04-17_validation_smoke_operator_lane.json`
6. readiness bundle: `docs/receipts/artifacts/2026-04-17_validation_smoke_readiness_bundle.json`
7. closure receipt: `docs/receipts/2026-04-17_live_trade_ready_validation_closure.md`

## Delegation packet
If any slice is delegated, require this first artifact back before broader coding:
- exact target file(s)
- exact verifier assertion(s)
- exact artifact path(s)
- explicit note of what this slice does **not** prove

Stop-loss:
- stop if the work drifts into strategy optimization instead of validation-path proof
- stop if the validation deck begins borrowing production strategy complexity
- stop if operator proof is attempted only on `tw_cash_intraday.toml` and presented as validation-deck proof
- stop if a slice tries to claim closure without adding a new receipt or artifact

## Rollback / WAL closure
When this line truly reaches the pre-real-money state, write back:
- any new tests and validation fixtures
- runtime-lane receipt for validation smoke deck execution
- validation-deck operator-lane receipt
- consolidated readiness JSON bundle
- final closure receipt saying only real-money smoke remains
- topology statement, expected: `unchanged`

## Tradeoffs / open risks
- the extra verifier artifacts were worth it because they removed the only honest ambiguity in this line
- the line stayed bounded and did not drift into strategy optimization
- remaining unproven surfaces are intentionally subsumed by the explicit real-money smoke gate

## Second-brain cross-validation
Final second-brain review verdict: pass.
- the repo can now honestly claim that only explicit real-money smoke remains
- packet status is safe to flip to done
- only cosmetic tightening was suggested: clarify that the real-money smoke gate subsumes broker-connected lifecycle and fill semantics
