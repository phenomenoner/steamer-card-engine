# 2026-05-02 — Stage 3 paper ledger execution packet

## Verdict

Implement Stage 3 as a **repo-local, fixture-only paper execution backend** that consumes Stage 2 simulation intents and writes a deterministic local ledger.

This is not broker connectivity, not live observation, and not a PnL realism claim. It is the first durable local lifecycle/audit proof:

```text
simulation-only intent
  -> paper risk validation
  -> accepted/rejected local paper order
  -> deterministic simulated fill/cancel
  -> auditable ledger/account/PnL state
```

## Proposed CLI

```bash
steamer-card-engine paper run \
  --adapter fixture-paper-only \
  --fixtures examples/probes/adapter_contract \
  --paper-ledger .state/paper/ledger.sqlite \
  --receipt out/paper.receipt.json \
  --max-position 1 \
  --max-loss-placeholder 0 \
  --stale-signal-seconds 300 \
  --json

steamer-card-engine paper audit \
  --paper-ledger .state/paper/ledger.sqlite \
  --json
```

`paper reset` is intentionally deferred. Tests should use temporary ledgers rather than needing a reset command in the first slice.

## New module layout

```text
src/steamer_card_engine/paper/
  __init__.py
  ledger.py       # SQLite schema + append/read/audit helpers
  simulator.py    # intent -> risk -> lifecycle logic
  receipts.py     # deterministic receipt builder/helpers

tests/
  test_paper_simulator.py
  test_paper_cli.py
```

Keep CLI thin: parse args, call domain/service layer, attach `cli_contract`.

## Ledger location

Default: `.state/paper/ledger.sqlite`

Rules:
- repo-local only
- no `/workspace/steamer`
- no cron/runtime mutation
- no credentials/env reads
- tests use `tmp_path / "ledger.sqlite"`

SQLite is acceptable for Stage 3 because it gives deterministic local durability and simple audit queries.

## Ledger schema v1

### `paper_meta`

```sql
key TEXT PRIMARY KEY,
value TEXT NOT NULL
```

Required rows:
- `schema_version = paper-ledger/v1`
- `created_by = steamer-card-engine`
- `execution_backend = local-paper-only`
- `no_network = true`

### `paper_runs`

```sql
run_id TEXT PRIMARY KEY,
created_at TEXT NOT NULL,
adapter_id TEXT NOT NULL,
fixture_hash TEXT NOT NULL,
adapter_hash TEXT NOT NULL,
replay_hash TEXT NOT NULL,
input_hash TEXT NOT NULL,
risk_profile_hash TEXT NOT NULL,
receipt_hash TEXT NOT NULL,
status TEXT NOT NULL
```

### `paper_orders`

```sql
order_id TEXT PRIMARY KEY,
run_id TEXT NOT NULL,
request_id TEXT NOT NULL,
dedupe_key TEXT NOT NULL UNIQUE,
case_id TEXT,
symbol TEXT NOT NULL,
side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
quantity INTEGER NOT NULL CHECK(quantity > 0),
order_type TEXT NOT NULL,
status TEXT NOT NULL CHECK(status IN ('accepted', 'rejected', 'filled', 'cancelled')),
reason_code TEXT NOT NULL,
stable_reason TEXT NOT NULL,
created_at TEXT NOT NULL,
updated_at TEXT NOT NULL
```

### `paper_fills`

```sql
fill_id TEXT PRIMARY KEY,
order_id TEXT NOT NULL,
run_id TEXT NOT NULL,
symbol TEXT NOT NULL,
side TEXT NOT NULL,
quantity INTEGER NOT NULL,
fill_price REAL NOT NULL,
filled_at TEXT NOT NULL,
fill_model TEXT NOT NULL
```

Stage 3 fill model is deterministic placeholder only:

```text
fill_model = fixture-immediate-v1
fill_price = 1.0
```

No market realism claim.

### `paper_positions`

```sql
symbol TEXT PRIMARY KEY,
quantity INTEGER NOT NULL,
avg_price REAL NOT NULL,
realized_pnl REAL NOT NULL,
updated_at TEXT NOT NULL
```

### `paper_events`

```sql
event_id TEXT PRIMARY KEY,
run_id TEXT NOT NULL,
order_id TEXT,
event_type TEXT NOT NULL,
event_seq INTEGER NOT NULL,
payload_json TEXT NOT NULL,
event_hash TEXT NOT NULL,
created_at TEXT NOT NULL
```

Events:
- `intent_seen`
- `risk_rejected`
- `order_accepted`
- `order_filled`
- `order_cancelled`
- `audit_passed` / `audit_failed`

## Deterministic IDs

Use stable hashes, not wall-clock randomness.

```text
run_id = paper-run:{sha256(adapter_id + replay_hash + ledger_schema_version + risk_profile_hash)[:16]}
order_id = paper-order:{sha256(run_id + request_id + symbol + side + quantity + order_type)[:16]}
dedupe_key = sha256(adapter_id + case_id + request_id + symbol + side + quantity + order_type)
fill_id = paper-fill:{sha256(order_id + fill_model + quantity + fill_price)[:16]}
```

Use deterministic timestamps inside Stage 3 receipts unless the implementation already has a stable created-at convention. If wall-clock time is included, keep it out of canonical hashes.

## `paper run` receipt contract

Required fields:

```json
{
  "schema_version": "paper-run/v1",
  "ledger_schema_version": "paper-ledger/v1",
  "adapter": {"id": "fixture-paper-only", "vendor": "fixture", "version": "v0"},
  "mode": "paper",
  "execution": "local-ledger-only",
  "ledger": {"path": ".state/paper/ledger.sqlite", "backend": "sqlite"},
  "hashes": {
    "run_id": "...",
    "replay_hash": "...",
    "fixture_hash": "...",
    "adapter_hash": "...",
    "input_hash": "...",
    "risk_profile_hash": "...",
    "receipt_hash": "..."
  },
  "risk": {
    "decision": "pass|fail",
    "max_position": 1,
    "max_loss_placeholder": 0,
    "stale_signal_seconds": 300,
    "duplicate_order_guard": true,
    "stale_signal_guard": true,
    "failures": []
  },
  "summary": {
    "intents_seen": 1,
    "orders_accepted": 1,
    "orders_rejected": 0,
    "fills": 1,
    "cancels": 0,
    "broker_native_order_count": 0
  },
  "no_network": true,
  "topology_changed": false,
  "live_readiness_claim": false
}
```

## Risk gates

Minimum fail-closed gates:

1. **max position**
   - reject if resulting absolute position would exceed `--max-position`.
2. **max loss placeholder**
   - Stage 3 can keep `0` or placeholder semantics, but must label it as placeholder and never claim market-real PnL.
3. **duplicate order guard**
   - reject duplicate `dedupe_key` on rerun unless an explicit replay/idempotent mode is designed.
4. **stale signal guard**
   - Stage 3 fixtures should carry a deterministic logical timestamp or sequence; if absent, receipt must say stale guard is not evidence of market freshness.
5. **broker-native order guard**
   - any broker-native order payload count > 0 fails the run.

## `paper audit` contract

Required output:

```json
{
  "schema_version": "paper-audit/v1",
  "ledger_schema_version": "paper-ledger/v1",
  "decision": "pass|fail",
  "counts": {
    "orders": 0,
    "accepted": 0,
    "rejected": 0,
    "fills": 0,
    "cancels": 0,
    "events": 0
  },
  "account_summary": {
    "positions": [],
    "realized_pnl": 0.0,
    "pnl_model": "fixture-placeholder-v1"
  },
  "invariant_failures": [],
  "no_network": true,
  "topology_changed": false
}
```

Audit invariants:
- meta schema exists
- every fill references an order
- filled orders have fill rows
- no broker-native orders exist
- positions reconcile with fills
- duplicate keys are unique by schema
- event hashes are present and deterministic

## Tests / verifier plan

Focused tests:

```bash
uv run pytest tests/test_paper_simulator.py tests/test_paper_cli.py tests/test_broker_adapter_contract.py tests/test_cli.py
uv run ruff check src/steamer_card_engine/paper src/steamer_card_engine/adapters/fixture_exchange.py src/steamer_card_engine/cli.py tests/test_paper_simulator.py tests/test_paper_cli.py
```

Counterfactuals:
- paper run creates ledger + receipt and audit passes
- repeated run with same dedupe keys fails closed or is explicitly idempotent with unchanged state
- max-position violation rejects
- broker-native order presence fails
- unknown adapter fails closed before ledger mutation
- audit detects corrupted/missing fill/order linkage
- outputs contain no credential/secret/raw vendor payload strings
- topology remains unchanged

## Red lines

- no Fubon / Neo / broker SDK imports
- no network
- no credential/env/cert reads
- no `/workspace/steamer` reads or writes
- no cron/runtime topology changes
- no operator arm/disarm coupling
- no live readiness claim
- no market-real PnL claim

## Rollback / closure

Rollback is a local git revert of the implementation commit and deletion of local test ledgers.

Closure must include:
- pytest + ruff receipts
- `paper run` smoke receipt
- `paper audit` smoke receipt
- topology statement: runtime/config/cron unchanged
- docs ingest + scoped memory
