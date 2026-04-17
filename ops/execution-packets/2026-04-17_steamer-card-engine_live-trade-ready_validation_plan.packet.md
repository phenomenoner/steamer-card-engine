# 2026-04-17 — steamer-card-engine live-trade-ready validation plan (non-real-money scope)

## Status
- planned
- topology: unchanged
- scope: push every validation surface except actual real-money submission to pass
- boundary: this packet explicitly excludes the final real-money smoke gate

## Verdict
Stop tying live-readiness validation to whether current `strategy-powerhouse` cards are good enough to trade.
For this line, `steamer-card-engine` should validate the execution/runtime/operator path with purpose-built simple strategy cards and split receipts, so we prove the system can produce entry/exit behavior without making strategy alpha the blocker.

## Whole-picture promise
Reach a truthful pre-live state where the repo can say:
- manifest/card/deck surfaces validate
- runtime can emit bounded intents from simple cards
- operator preflight/probe/gating path is green
- non-cash dispatch path is green and receipted
- entry/exit lifecycle test surfaces are covered in replay/live-sim or controlled stub lanes
- the only remaining unclosed gate is one explicit real-money smoke attempt

Fake progress would be:
- waiting on production-worthy strategy quality
- using complex existing cards whose behavior is hard to force during tests
- mixing strategy evaluation with execution-path verification

## Recommended bounded slice plan

### Slice 1 — introduce validation-only smoke cards and decks
Create a tiny validation pack independent of `strategy-powerhouse` quality.

Recommended cards:
1. `examples/cards/smoke_entry_once.toml`
   - emits one bounded buy intent when a trivial fixture condition is met
2. `examples/cards/smoke_exit_once.toml`
   - emits one bounded flatten/sell intent after a deterministic follow-up condition
3. `examples/cards/smoke_no_trade_guard.toml`
   - intentionally emits nothing so blocked/no-op branches are also testable

Recommended deck posture:
- one dedicated validation deck at `examples/decks/tw_cash_validation_smoke.toml`
- tiny symbol pool
- explicit risk policy tuned for deterministic testability, not alpha quality
- clearly marked non-production / validation-only status

Success condition:
- replay or live-sim can force at least one clean entry path and one clean exit path on demand

### Slice 2 — split the validation matrix by system responsibility
Do not ask one scenario to prove everything.

Validation families:
1. manifest contract validation
   - card/deck/global validate + inspect
2. runtime intent validation
   - simple cards emit expected intents under fixture events
3. risk / gating validation
   - invalid scope, blocked posture, and no-trade branches stay explicit
4. operator control validation
   - `probe-session`, `preflight-smoke`, `status`, `arm-live`, `submit-order-smoke`, `flatten`, `live-smoke-readiness`
5. dispatch-path validation
   - non-cash path traversal receipt remains green under current probe truth
6. lifecycle packaging validation
   - receipts and machine-readable artifacts are enough to reconstruct entry -> exit or explicit no-trade

Success condition:
- each family has its own verifier and receipt path

### Slice 3 — add deterministic scenario fixtures for entry/exit proof
Provide fixtures that let the smoke cards trigger both sides cleanly.

Minimum scenarios:
- entry accepted then flatten path available
- entry blocked by gate/disarmed posture
- no-trade expected path
- exit/flatten requested after entry state exists

Suggested verifier ownership:
- `tests/test_manifests.py` for validation cards/deck contract loading
- `tests/test_cli.py` for operator and manifest command surfaces
- `tests/test_dashboard.py` for runtime dispatch truth presentation

Success condition:
- the repo no longer depends on live market randomness or a good alpha card just to prove path traversal

### Slice 4 — close non-real-money validation receipts
After the validation pack lands, update the receipts so the repo can state exactly what is proven.

Must be explicit:
- what is now proven about entry/exit behavior
- what is still seed/stub-only
- that real-money smoke is still the only remaining production-facing gate

## Contract / boundary rules
- validation cards are for path proof, not alpha proof
- validation decks must be clearly separated from production/intended strategy decks
- cards emit intent; they must not reach broker order flow directly
- operator lane remains the only surface allowed to cross live gates
- a green non-real-money packet must never be phrased as broker-connected readiness

## Verifier plan
A truthful pass before real-money smoke should include:
1. `uv run steamer-card-engine author validate-card <validation-card>` for each smoke card
2. `uv run steamer-card-engine author validate-deck <validation-deck>`
3. focused tests for deterministic intent emission from smoke cards
4. focused tests for blocked/no-trade branches
5. `uv run pytest -q tests/test_dashboard.py`
6. relevant operator-control tests for `status|arm-live|submit-order-smoke|flatten|live-smoke-readiness`
7. fresh `operator preflight-smoke --json` pass on canonical probe truth
8. fresh `operator live-smoke-readiness --json` pass with receipt bundle
9. one compact receipt stating:
   - entry path proven in validation lane
   - exit/flatten path proven in validation lane
   - non-cash dispatch path proven
   - real-money smoke still unexecuted

## Delegation packet
If delegated to a worker, require this first artifact:
- proposed names/paths for smoke cards and smoke deck
- scenario matrix mapping each card to one verifier
- list of tests to add or update
- explicit note separating validation cards from strategy-quality evaluation

Stop-loss:
- stop if the diff starts optimizing strategy quality instead of testability
- stop if smoke cards begin inheriting complex strategy-powerhouse dependencies
- stop if broker-connected behavior is implied without real-money receipts

## Rollback / WAL closure
When this line lands, write back:
- validation card/deck docs or manifests
- test receipts
- updated non-real-money readiness receipt
- topology statement, expected `unchanged`
- one closure note that the remaining gate is only the explicit real-money smoke packet

## Tradeoffs / open risks
- purpose-built smoke cards add extra artifacts, but they buy deterministic verification and cleaner truth
- if the validation cards drift toward real strategy logic, the line will bloat and lose the point
- the repo still cannot claim production live-ready until the real-money smoke packet is executed successfully
