# steamer-card-engine

> Card-oriented runtime seed for Taiwan cash-stock intraday strategy research, replay, live simulation, and operator-gated broker execution.

`steamer-card-engine` turns strategy ideas into versioned **cards**, groups them into governed **decks**, and routes approved intents through replay/live-sim/live execution contracts with audit-friendly receipts.

It is intentionally **agent-assisted, operator-governed**: agents may help author, validate, replay, and prepare gates; live broker authority remains behind explicit operator controls.

## What this project is

- A docs-first and CLI-first product surface for Taiwan cash-stock intraday strategy operations.
- A card/deck runtime model that separates strategy intent from risk governance and broker execution.
- A replay-first system: contracts should be testable before live authority expands.
- A bounded live-execution seed with arm/disarm gates, dry-run defaults, and broker-adapter receipts.

## What it is not

- Not a turnkey production trading system.
- Not unrestricted autonomous live trading.
- Not a promise of profitability, reliability, or broker availability.
- Not a place to store real credentials, account numbers, private receipts, or operator machine paths.

## Core concepts

| Concept | Meaning |
|---|---|
| Card | Versioned strategy unit. It declares entry/exit logic, symbol scope, feature needs, and risk hints. It emits intents; it does not own broker authority. |
| Deck | Governance bundle for one or more cards. It applies shared universe, risk, and execution policy. |
| Intent | Strategy action proposal. It must pass risk and operator gates before becoming an execution request. |
| Adapter | Boundary to market data, broker execution, or account state. Adapters must preserve receipts and avoid leaking vendor-specific details into card logic. |
| Receipt | Structured evidence of what happened: inputs, gates, decisions, execution status, and safe redactions. |

## Current product shape

```text
Authoring / Management Plane
  CLI -> Card Spec -> Deck Spec -> Global Config -> Replay Jobs
   |      validates, inspects, packages, and prepares operator-reviewed changes

Execution Plane
  AuthSessionManager
      +-> MarketDataAdapter -> MarketDataHub -> FeaturePipeline -> CardRuntime
      +-> Broker/Account Adapter -------------------------------> ExecutionEngine

  CardRuntime -> IntentAggregator -> RiskGuard -> ExecutionEngine -> BrokerAdapter
          |              |               |                |
          +---- Recorder / Audit Trail / ReplayRunner / LiveSim -+
```

The main boundary is simple: **cards produce intent; operator-governed runtime decides whether anything can touch a broker.**

## Live execution posture

Live execution is deliberately narrow and gate-based:

- CLI defaults to dry-run.
- Live mode requires explicit arm, explicit `--mode live`, explicit confirmation, and broker secret directory configuration outside the repo.
- Account/session matching is checked before broker submission.
- Day-trade exits must be bounded by policy: take-profit, stop-loss, and/or forced-cover time.
- Fill prices must come from execution fills, not submitted limit prices.

Recent Gate 5 work added the production design pattern for fill handling:

1. use the broker's active filled callback as the low-latency primary fill source;
2. compute position/P/L from fill data (`filled_avg_price`, `filled_price`, or reconciled `filled_money / filled_qty`);
3. run periodic `get_order_results` readback as a safe-net for missed callbacks;
4. write `fill_source` in receipts so operators can tell whether the callback path or readback path supplied the fill.

See [`docs/LIVE_EXECUTION_GATE.md`](docs/LIVE_EXECUTION_GATE.md) for the public contract.

## Public docs map

- [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md) — product promise, users, scope, non-goals.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — plane split, runtime components, event/fill lifecycle.
- [`docs/CARD_SPEC.md`](docs/CARD_SPEC.md) — card manifest model.
- [`docs/CLI_SPEC.md`](docs/CLI_SPEC.md) — stable CLI surface and machine-readable behavior.
- [`docs/AUTH_AND_SESSION_MODEL.md`](docs/AUTH_AND_SESSION_MODEL.md) — auth/session posture and capability boundaries.
- [`docs/DAYTRADING_GUARDRAILS.md`](docs/DAYTRADING_GUARDRAILS.md) — day-trading risk and exit guardrails.
- [`docs/LIVE_EXECUTION_GATE.md`](docs/LIVE_EXECUTION_GATE.md) — bounded live execution gate and fill-source contract.
- [`docs/LIVE_MONITOR_SIDECAR.md`](docs/LIVE_MONITOR_SIDECAR.md) — 唯讀 dashboard / live monitor sidecar 邊界、runtime store、API 與安全姿態。
- [`docs/SETUP.md`](docs/SETUP.md) — development setup.
- [`CHANGELOG.md`](CHANGELOG.md) — public release notes.

Historical `docs/receipts/` and `docs/tech-notes/` files are development evidence. Treat them as implementation history, not the public product entrypoint.

## Quickstart

```bash
uv sync
uv run steamer-card-engine --help

# Validate examples
uv run steamer-card-engine author validate-card examples/cards/gap_reclaim.toml
uv run steamer-card-engine author validate-deck examples/decks/tw_cash_intraday.toml
uv run steamer-card-engine author validate-global examples/config/global.toml

# Inspect manifests
uv run steamer-card-engine author inspect-card examples/cards/gap_reclaim.toml
uv run steamer-card-engine author inspect-deck examples/decks/tw_cash_intraday.toml --cards-dir examples/cards

# Operator-gated dry-run examples stay dry-run unless explicitly armed and confirmed.
uv run steamer-card-engine operator plan-real-trade-gate \
  --deck examples/decks/tw_cash_real_trade_gate_stage1_short_first.toml \
  --auth-profile examples/profiles/tw_cash_password_auth.toml \
  --symbol 1314 --quantity 1000 --shortable-symbol 1314 --json
```

## Safety notes

- Do not commit credentials, account numbers, private broker receipts, SSM/AWS paths, or real operator machine paths.
- Keep live broker execution behind explicit operator gates.
- Prefer dry-run/replay/live-sim evidence before expanding live authority.
- Public docs should describe contracts and behavior, not private operational incidents.

## Live monitor sidecar

The dashboard / live monitor lives inside this repository as a **read-only sidecar** under `steamer_card_engine.dashboard.*`.

It can index runtime artifacts into a local SQLite store and expose read-only API/UI surfaces, but it must not submit broker orders, mutate strategy policy, or hold broker authority. See [`docs/LIVE_MONITOR_SIDECAR.md`](docs/LIVE_MONITOR_SIDECAR.md) for the public contract.

## Status

This repository is an evolving seed product. It has useful CLI contracts, manifests, tests, bounded live-execution scaffolding, and a read-only monitor sidecar, but it should still be treated as pre-production until replay/live-sim/live gates are hardened across more scenarios.
