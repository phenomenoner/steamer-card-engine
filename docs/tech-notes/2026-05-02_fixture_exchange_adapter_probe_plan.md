# 2026-05-02 — Fixture Exchange Adapter Probe implementation plan

## Verdict

Implement the first CLI-first exchange-adapter slice as a **fixture-only adapter probe**, not as live broker connectivity.

The proving edge is contract shape, capability normalization, sanitized JSON receipts, and fail-closed behavior.

## Whole-picture promise

Move `steamer-card-engine` toward a real exchange/broker integration path without letting LLMs, MCP, or vendor SDKs become the first source of trading truth.

The stable product spine remains:

```text
Strategy Powerhouse handoff
  -> steamer-card-engine card/deck/replay/live-sim runtime
  -> CLI-first adapter contract
  -> deterministic risk/preflight gates
  -> broker adapter only after explicit authorization
```

## Bounded slice

Add a read-only fixture-backed command:

```bash
steamer-card-engine adapter probe --fixture paper-only --json
```

This command should:

- construct a deterministic fixture adapter/capability profile
- emit a public JSON contract with `cli_contract.version = "cli-command/v1"`
- show adapter identity, capability profile, logical session posture, preflight decision, normalized receipt, dispatch boundary, and topology status
- fail closed for unsupported execution modes
- prove sanitizer behavior for secret-like/vendor fields
- avoid all persistent state writes

## Contract / boundaries

### Allowed files / surfaces

- `src/steamer_card_engine/adapters/base.py`
- new `src/steamer_card_engine/adapters/fixture_exchange.py`
- `src/steamer_card_engine/cli.py`
- `tests/test_broker_adapter_contract.py`
- `tests/test_cli.py`
- `docs/ADAPTER_SPEC.md`
- `docs/CLI_SPEC.md`
- `docs/TOPOLOGY.md`
- optional sanitized example fixture under `examples/probes/`

### JSON contract sketch

```json
{
  "cli_contract": { "version": "cli-command/v1" },
  "adapter": {
    "id": "fixture-paper-only",
    "vendor": "fixture",
    "version": "v0"
  },
  "capabilities": {
    "marketdata_enabled": true,
    "account_query_enabled": false,
    "trade_enabled": true,
    "paper_trading_enabled": true,
    "live_trading_enabled": false,
    "supported_actions": ["submit", "cancel"]
  },
  "session_posture": "fixture_only",
  "preflight": {
    "decision": "allow",
    "execution_mode": "paper",
    "reason": "fixture paper-only capability allows paper preflight"
  },
  "receipt": {
    "status": "ok",
    "normalized": true,
    "raw_ref": "fixture:paper-only"
  },
  "dispatch": "fixture-only; no broker SDK; no live order",
  "topology_changed": false
}
```

### Red lines for this slice

- no Fubon / Neo / broker SDK imports
- no credential, env, certificate, or account-path reads
- no network calls
- no submit/cancel/replace against real venues
- no `/workspace/steamer` reads or writes
- no cron/runtime topology changes
- no coupling to operator arm/disarm state
- no claim of paper/live trading readiness
- no raw vendor payload in public JSON

## Verifier plan

Run from repo root:

```bash
uv run pytest tests/test_broker_adapter_contract.py tests/test_cli.py
uv run ruff check src/steamer_card_engine/adapters src/steamer_card_engine/cli.py tests/test_broker_adapter_contract.py tests/test_cli.py
```

Counterfactual tests must prove:

1. fixture probe succeeds and emits `dispatch = fixture-only; no broker SDK; no live order`
2. `paper-only` fixture rejects `live` execution mode before dispatch
3. unknown execution mode fails closed
4. public JSON contains no `token`, `password`, `api_key`, `secret`, `cert`, raw vendor payload, or env dump
5. `cli_contract.version == "cli-command/v1"`
6. command does not create or modify operator state / receipt files
7. docs and JSON both say topology unchanged

## Delegation packet

Objective:

> Implement `steamer-card-engine adapter probe --fixture paper-only --json` as a fixture-only, read-only adapter contract probe.

Scope:

- add deterministic fixture adapter/capability objects
- add CLI command and JSON contract
- add tests and docs
- preserve existing operator/live-smoke semantics

Stop-loss:

- stop if existing CLI parser structure makes a new `adapter` family non-trivial; return a minimal patch plan rather than broad refactor
- stop if implementation would need SDK/network/credentials/private runtime state
- stop if tests require touching live operator state or cron wrappers

Expected return:

- diff summary
- verifier output
- topology statement
- any deferred risk

## Rollback / WAL closure

Rollback is a local git revert of the implementation commit.

Closure must include:

- test/ruff receipts
- docs update receipt
- explicit topology statement: runtime/config/cron topology unchanged
- local commit only unless CK separately authorizes push

## Deferred stages toward trading

This slice intentionally defers:

- real broker adapter
- SDK login/session lifecycle
- account positions/balances
- runtime `ExecutionEngine` integration
- paper/live order submit
- cron/preflight wiring
- `/workspace/steamer` private bridge
- production capability detection

Those belong in later gated slices after the fixture probe contract is pinned.
