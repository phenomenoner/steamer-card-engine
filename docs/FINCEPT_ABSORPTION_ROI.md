# FinceptTerminal Absorption Map for Steamer

Status: planning input, remote-safe, no strategy-private params.
Source posture: FinceptTerminal was inspected as a pattern library only. Do not copy AGPL code.

## Verdict

The high-ROI absorption from FinceptTerminal is not its broad finance-terminal product surface. For Steamer, the useful material is the engineering seam around governed runtime contracts: provenance, market-data hub introspection, broker/session capability envelopes, and task/activity receipts.

This map is ordered by expected ROI for the current Steamer topology.

## ROI-ordered absorption items

### 1. Evidence Provenance Envelope + MarketDataHub stats

Contract draft: `docs/EVIDENCE_PROVENANCE_ENVELOPE_SPEC.md` defines the remote-safe, aggregate-only envelope and MarketDataHub stats/introspection target.

Current Steamer fit:
- `/workspace/steamer` already treats `.data/<host>/<date>.7z` as the local-only evidence source.
- `dt3` and `r6` already split short/long-focused broker-host evidence.
- `nohup_*.log` is already the authoritative run-meta source.
- Gate observability already uses aggregate reason codes: `no_trades`, `warmup_not_ready`, `insufficient_bars`, `other_reject`, `pass`.
- `steamer-card-engine` already names `MarketDataHub`, `FeaturePipeline`, `Recorder`, replay, and live-sim as first-class concepts.

Absorb:
- A compact provenance JSON for each local evidence archive or report.
- Source host, run date, archive hash, parser version, row counts, params-source pointer, schema version, and aggregate reason taxonomy.
- A `MarketDataHub` stats/introspection contract draft for subscriber counts, last event, stale state, errors, and replay/live parity checks.

Do not absorb:
- Fincept's broad connector sprawl.
- Any raw symbols, account data, strategy params, or raw trades into remote-safe docs.

Suggested first verifier:
- Given one local Steamer archive/report, produce an aggregate-only provenance envelope that points to source archive + parser version and explains zero/low coverage without exposing private edge material.

### 2. BrokerAdapter capability + normalized error envelope

Current Steamer fit:
- `steamer-card-engine` already defines `BrokerAdapter`, `ExecutionEngine`, `RiskGuard`, and the rule that cards emit intents rather than broker orders.
- Existing docs already require active account + `user_def` filtering for order lifecycle routing.
- Auth posture already recognizes reduced-permission API keys as an operator safety boundary.

Absorb:
- Capability profiles: marketdata/account/trade enabled, paper-only/live-enabled, supported actions, rate limits, and credential permission state.
- Normalized errors: auth, insufficient funds, invalid order, rate limit, network, exchange/broker unavailable, unknown.
- Result metadata: retryable, safe_to_replay, raw_ref, receipt_id.

Do not absorb:
- Strategy scripts directly calling broker APIs.
- Paper/live as a plain boolean flag without permission gating.
- Secrets passed through CLI args or broad subprocess environments.

Suggested verifier:
- A paper-only broker fixture rejects live submit without an explicit capability token and records a normalized receipt.

### 3. AuthSessionManager capability envelope

Current Steamer fit:
- `AuthSessionManager` is already a named shared module for marketdata + trading/account surfaces.
- The missing maturity layer is not login itself, but truthful session capability disclosure.

Absorb:
- Session health and capability facts: `marketdata_enabled`, `account_query_enabled`, `trade_enabled`, expiry/refresh hints, auth mode, account scope, and degraded-state reason.

Do not absorb:
- Treating successful login as proof of full trading readiness.

Suggested verifier:
- A session fixture can be logged in but trade-disabled; downstream broker submit must fail closed while marketdata remains allowed.

### 4. Strategy Powerhouse handoff task/activity receipts

Current Steamer fit:
- `strategy-powerhouse-framework` is research + packaging + control-plane support.
- It must stop at handoff to `steamer-card-engine`; it is not the live-sim runtime.

Absorb:
- Task activity events for intake, family selection, backtest estimate, synthetic verifier, engine handoff, WAL/topology closure.
- Final handoff JSON with verifier status, next target, and receipts.

Do not absorb:
- Fincept-style generic AI-agent sprawl.
- Runtime execution authority inside the research framework.

Suggested verifier:
- One synthetic-verifier handoff emits a machine-readable activity log and final engine handoff packet without runtime execution.

### 5. Limited control-plane tool registry

Current Steamer fit:
- Agent/operator assistance is useful, but live authority must remain in the operator plane.

Absorb:
- A small read-only tool registry for inspection: evidence lookup, latest report pointer, card/deck inspect, replay status, live-sim status.
- Every call emits a receipt.

Do not absorb:
- Hundreds of tools.
- Generic file/API/Python tools without permission gates.

Suggested verifier:
- A read-only `latest_evidence_report` tool returns a sanitized pointer and receipt, not raw private data.

## Implementation order

1. Evidence Provenance Envelope + MarketDataHub stats.
2. BrokerAdapter capability + normalized error envelope.
3. AuthSessionManager capability envelope.
4. Strategy Powerhouse handoff task/activity receipts.
5. Limited control-plane tool registry.

## Closure rule

Each item should move through the same Sakura Blade Dance loop:

1. Write the bounded plan and verifier.
2. Run a Claude second-brain review.
3. Dispatch one Minion implementation slice.
4. Integrate and verify.
5. Dispatch a Minion code-review slice.
6. Close receipts, then continue to the next ROI item.
