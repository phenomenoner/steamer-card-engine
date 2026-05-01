# 2026-05-02 — CLI-first roadmap from adapter probe to tradable stage

## Verdict

The route to "can trade" should advance through **seven fail-closed gates**:

```text
0 fixture probe
  -> 1 adapter contract hardening
  -> 2 replay-only simulation
  -> 3 local paper simulator / execution ledger
  -> 4 broker dry-run adapter, no order placement
  -> 5 live market observation + paper execution
  -> 6 CK-authorized tiny live canary
  -> 7 normal live authorization policy
```

Every risky action remains CLI-first, verifier-backed, and explicitly mode-gated. MCP may later wrap stable CLI/context surfaces, but it must not own runtime truth.

## Whole-picture promise

Build a path where `steamer-card-engine` can eventually issue real broker orders without hiding risk behind agent language.

The LLM/agent may explain, plan, and orchestrate. Deterministic CLI/contracts must decide readiness, execute, reconcile, and stop.

## Global invariants

- **CLI-first control**: every risky action has an explicit command and mode flag.
- **Verifier-backed movement**: each stage exits only with deterministic receipts.
- **Fail-closed defaults**: no broker keys, no live route, no order side effects unless explicitly authorized.
- **Mode separation**: `fixture`, `replay`, `paper`, `dry-run`, and `live` are separate modes with hard gates.
- **WAL closure**: every authority expansion needs decision, receipt, rollback, and topology statement.
- **No hidden live risk**: no stage should be able to accidentally trade.

## Stage 0 — Fixture-only adapter probe

Status: planned by `docs/tech-notes/2026-05-02_fixture_exchange_adapter_probe_plan.md`.

Purpose:
- prove adapter capability shape, JSON contract, sanitizer, and fail-closed behavior without broker SDK/network/credentials.

Candidate CLI:

```bash
steamer-card-engine adapter probe --fixture paper-only --json
```

Exit criteria:
- adapter loads from deterministic fixture
- emits `cli_contract.version = "cli-command/v1"`
- emits input hash / adapter version / schema version / no-network assertion
- tests prove paper-only/live reject/unknown-mode fail-closed/no state writes/no secret leakage
- topology unchanged

Verifier:

```bash
uv run pytest tests/test_broker_adapter_contract.py tests/test_cli.py
uv run ruff check src/steamer_card_engine/adapters src/steamer_card_engine/cli.py tests/test_broker_adapter_contract.py tests/test_cli.py
```

## Stage 1 — Adapter contract hardening

Purpose:
- make adapter behavior stable before connecting it to replay, runtime, or broker surfaces.

Candidate CLI:

```bash
steamer-card-engine adapter contract check --adapter fixture-paper-only --fixtures examples/probes/adapter_contract/ --json
steamer-card-engine adapter explain --adapter fixture-paper-only --json
```

Required schemas:
- input card/deck context
- normalized signal / order-intent candidate
- reject/no-op reason
- capability profile
- receipt envelope
- public sanitizer contract

Exit criteria:
- deterministic golden tests pass
- adapter never returns broker-native orders directly
- every skip/reject has a stable reason
- no ambiguous `trade/skip` state

## Stage 2 — Replay-only simulation

Purpose:
- prove adapter contract can run over historical/replay streams without trading.

Candidate CLI:

```bash
steamer-card-engine replay run \
  --adapter fixture-paper-only \
  --deck fixtures/deck.safe.json \
  --mode replay \
  --receipt out/replay.receipt.json
```

Exit criteria:
- replay produces deterministic decisions
- all generated intents remain simulation-only
- receipt includes replay range hash, fixture/deck hash, adapter hash, and result summary
- repeated replay diff is stable unless source hash changes

Red lines:
- replay imports live broker adapter
- runtime secrets/config discovered during replay
- non-reproducible replay without explained seed/source delta

## Stage 3 — Local paper simulator / execution ledger

Purpose:
- turn intents into simulated orders/fills against a controlled local ledger with no broker connectivity.

Candidate CLI:

```bash
steamer-card-engine paper run \
  --adapter fixture-paper-only \
  --deck fixtures/deck.safe.json \
  --paper-ledger .state/paper/ledger.sqlite \
  --receipt out/paper.receipt.json
```

Exit criteria:
- simulated lifecycle works: intent -> validation -> accepted/rejected -> simulated fill/cancel -> account/PnL state simulation
- fail-closed constraints proven: max position, max loss, duplicate-order guard, stale signal guard
- `paper audit` proves ledger consistency

Red lines:
- paper mode can route to broker
- risk checks are advisory only
- missing kill-switch path

## Stage 4 — Broker adapter dry-run, no order placement

Purpose:
- validate broker integration shape without placing orders.

Entry condition:
- explicit CK authorization to inspect broker adapter surface and credential boundary.

Candidate CLI:

```bash
steamer-card-engine broker preflight \
  --broker <name> \
  --mode dry-run \
  --no-place-orders \
  --receipt out/broker-preflight.receipt.json
```

Required behavior:
- auth/config availability checked privately
- broker API connectivity or mock transport verified
- order translation tested against synthetic order payloads
- receipt redacts account/auth/symbol-private details

Exit criteria:
- broker dry-run receipt passes `redact-check`
- tests prove `--no-place-orders` guard cannot be bypassed accidentally
- no account IDs, secrets, raw broker payloads, or private symbol lists in public artifacts

## Stage 5 — Live market observation + paper execution

Purpose:
- observe live market data, but execute only in paper ledger.

Entry condition:
- CK authorizes live market-data observation; no live order permission.

Candidate CLI:

```bash
steamer-card-engine observe paper \
  --adapter fixture-paper-only \
  --market-source live \
  --execution paper \
  --risk-profile conservative \
  --duration 30m \
  --receipt out/live-paper.receipt.json
```

Exit criteria:
- bounded live observation runs
- generated orders are paper-only and risk-checked
- process has no live order route
- receipt proves execution backend was paper
- stale data / market-data outage fails closed

Paper trading can be authorized here, but only as **paper execution with live observation**, not live broker placement.

## Stage 6 — CK-authorized tiny live canary

Purpose:
- prove one tightly bounded live order path after explicit authorization.

Entry conditions:
- CK explicitly authorizes live canary with limits
- paper observation receipts reviewed
- broker dry-run receipts accepted
- risk envelope written: max notional, max order count, allowed session window, kill switch, cancel-on-error behavior
- no private strategy params exposed in chat/report

Safer two-step CLI:

```bash
steamer-card-engine live canary plan \
  --risk-envelope envelopes/canary.json \
  --max-orders 1 \
  --receipt out/live-canary-plan.receipt.json

steamer-card-engine live canary execute \
  --plan out/live-canary-plan.receipt.json \
  --require-confirm \
  --receipt out/live-canary.receipt.json
```

Exit criteria for first "can trade" stage:
- one bounded live smoke has end-to-end receipt
- no hidden residual position
- operator state disarmed
- rollback/flatten path proven or actual result named
- WAL/receipt explicitly says what is and is not production-ready

## Stage 7 — Normal live authorization policy

Purpose:
- define how the system graduates from one tiny canary to repeatable, bounded live authorization.

Entry conditions:
- Stage 6 canary closed cleanly
- CK approves a live authorization policy separately
- production risk envelope, monitoring, reconciliation, and rollback are documented and tested

Required policy surfaces:
- live allowlist / account boundary
- max order count / max notional / max daily loss
- session windows
- duplicate-order and stale-data guards
- kill switch and flatten workflow
- incident/postmortem receipt workflow
- authority expiry and re-approval cadence

Exit criteria:
- normal live mode remains opt-in and bounded
- operator can reconstruct every action from receipts
- no agent-only or MCP-only path can bypass CLI gates

## Non-negotiable red lines across all stages

- no LLM-owned trading truth
- no MCP-first runtime dependency
- no hidden live authority from natural language
- no credentials or raw vendor payloads in committed artifacts
- no `/workspace/steamer` mutation until a specific bridge slice authorizes it
- no cron/runtime topology changes without a separate topology receipt
- no claim of alpha quality or production strategy worthiness from adapter tests
- no stage may accidentally trade

## Recommended next implementation order

1. Implement Stage 0 fixture adapter probe.
2. Re-run docs/test closure and commit locally.
3. Only then design Stage 1 against the actual contract/golden-fixture shape.
4. Keep Stages 4-7 blocked until CK explicitly authorizes credential/broker/live-observation/live-order boundaries.

## Topology statement

This roadmap changes repo planning truth only.
Runtime topology changed: no.
Scheduler topology changed: no.
Broker/account authority changed: no.
