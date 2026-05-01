# CLI Specification

## Goal

The CLI is the primary management surface for cards, decks, auth profiles, replay/live-sim jobs, and operator controls.

It should be friendly to humans and automation, including agent-assisted workflows.

## Command families

### 1. Auth / Session commands

Used for validating auth profiles and inspecting logical session posture without inventing hidden state.

Examples:

```bash
steamer-card-engine auth validate-profile ./profiles/fubon.paper.toml
steamer-card-engine auth inspect-profile ./profiles/fubon.paper.toml
steamer-card-engine auth inspect-session --auth-profile ./profiles/fubon.live.toml --json
steamer-card-engine auth inspect-session --auth-profile ./profiles/fubon.live.toml --probe-json ./examples/probes/session_health.connected.json --json
steamer-card-engine auth inspect-session --auth-profile ./profiles/fubon.live.toml --probe-source steamer-cron-health --probe-date 20260416 --json
```

Responsibilities:

- validate login mode shape
- show capability expectations (market data only, trade enabled, etc.)
- inspect current logical session and health status
- help operators confirm the intended safety boundary before live expansion
- in seed runtime, `inspect-session` is a logical profile/session surface, not a broker-connected session attach
- the session/preflight lane should stabilize around a reusable `session_status + connections` health shape so later broker-connected work swaps data sources, not command contracts
- `--probe-json` remains the fixture/manual inlet for explicit external snapshots and takes precedence when both `--probe-json` and `--probe-source` are supplied
- `--probe-source steamer-cron-health` is the first named upstream truth adapter, translating Steamer cron-health stage files into the canonical probe contract without changing the CLI surface

### 2. Authoring commands

Used for creating and validating product artifacts.

Examples:

```bash
steamer-card-engine author init-card gap-reclaim
steamer-card-engine author validate-card ./cards/gap_reclaim.toml
steamer-card-engine author validate-deck ./decks/tw_cash_intraday.toml
steamer-card-engine author validate-global ./config/global.toml
steamer-card-engine author inspect-card ./cards/gap_reclaim.toml
steamer-card-engine author inspect-deck ./decks/tw_cash_intraday.toml --cards-dir ./cards
steamer-card-engine author inspect-global ./config/global.toml
```

Responsibilities:

- create scaffolds
- validate manifests
- inspect card metadata
- verify symbol-pool, capital-control, and feature-requirement shape
- package reproducible card/deck specs

### 3. Replay / Sim commands

Used for replay evaluation and live-sim execution paths with shared runtime contracts.

Examples:

```bash
steamer-card-engine replay run --deck ./examples/decks/tw_cash_intraday.toml --date 2026-03-11 --baseline-dir /path/to/legacy/baseline/day --scenario-spec ./scenarios/tw-gap-reclaim-20260311.json
steamer-card-engine replay inspect run-20260311-01
steamer-card-engine sim run-live --deck ./examples/decks/tw_cash_intraday.toml --session-date 2026-03-11 --baseline-dir /path/to/captured/baseline/day --dry-run --scenario-id tw-live-sim.twse.2026-03-11.full-session
```

Responsibilities:

- submit replay jobs
- run live-sim sessions without live broker execution
- inspect replay/live-sim outputs
- compare card variants
- capture and echo ScenarioSpec identity (`scenario_id` + core scenario knobs)
- export decision receipts

### 4. SIM comparability commands (M1 foundation)

Used for baseline normalization and baseline-vs-candidate bundle comparison in the sim-only M1 lane.

Examples:

```bash
steamer-card-engine sim normalize-baseline \
  --baseline-dir /path/to/legacy/baseline/day \
  --output-dir /tmp/baseline-bundle \
  --session-date 2026-03-13 \
  --scenario-id tw-paper-sim.twse.2026-03-13.full-session

steamer-card-engine sim compare \
  --baseline /tmp/baseline-bundle \
  --candidate /tmp/candidate-bundle \
  --output-dir /tmp/compare
```

Responsibilities:

- normalize legacy baseline artifacts (`decisions.jsonl` + tick/trade sources) into a v1-shaped bundle
- keep capability posture explicit (`trade_enabled=false`)
- emit comparator hard-fail reasons for scenario/execution-model mismatches
- write decision-grade compare outputs (`compare-manifest.json`, `diff.json`, `summary.md`) with reviewable mismatch reasons and machine-readable deltas
- support M1 evidence-pack acceptance workflow defined in `docs/M1_EVIDENCE_PACK_ACCEPTANCE_CONTRACT.md`

### 5. Operator commands

Used for controlled runtime and live-adjacent governance.

Examples:

```bash
steamer-card-engine operator status --json
steamer-card-engine operator arm-live --deck examples/decks/tw_cash_intraday.toml --ttl-seconds 300 --auth-profile examples/profiles/tw_cash_password_auth.toml --confirm-live
steamer-card-engine operator disarm-live
steamer-card-engine operator flatten --mode final-auction
steamer-card-engine operator submit-order-smoke --symbol 2330 --side buy --quantity 1
steamer-card-engine operator live-smoke-readiness --deck examples/decks/tw_cash_intraday.toml --auth-profile examples/profiles/tw_cash_password_auth.toml --json
steamer-card-engine operator live-smoke-readiness --deck examples/decks/tw_cash_intraday.toml --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --probe-source steamer-cron-health --probe-date 20260416 --json
steamer-card-engine operator probe-session --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --json
steamer-card-engine operator probe-session --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --output ./.state/session_probe.json --json
steamer-card-engine operator probe-session --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --probe-source steamer-cron-health --probe-date 20260416 --json
steamer-card-engine operator preflight-smoke --deck examples/decks/tw_cash_intraday.toml --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --json
steamer-card-engine operator preflight-smoke --deck examples/decks/tw_cash_intraday.toml --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --probe-json examples/probes/session_health.connected.json --json
steamer-card-engine operator preflight-smoke --deck examples/decks/tw_cash_intraday.toml --auth-profile examples/profiles/tw_cash_password_auth.toml --trading-day-status open --probe-source steamer-cron-health --probe-date 20260416 --json
```

Responsibilities:

- inspect runtime health, capability, and posture in one view
- arm/disarm live mode with bounded TTL policy
- auto-disarm on TTL expiry (and invalid arm scope) when operator state is inspected/used
- enforce submission gate against non-active arm windows with explicit disarmed refusal for seed order-smoke checks
- write action receipts for arm/disarm/flatten/refusals
- run one bounded live-capability smoke sequence that first enforces the same truthful preflight posture (`--probe-json` / `--probe-source`) and then proves disarmed refusal -> bounded arming -> armed acceptance receipt -> flatten/disarm closure without broker submission
- when that preflight gate is blocked, `live-smoke-readiness` exits with code `4` and returns a blocked smoke payload instead of entering the smoke sequence
- emit a canonical session-health snapshot for downstream cron/preflight consumers
- support both fixture/manual snapshots (`--probe-json`) and named upstream truth adapters (`--probe-source`)
- expose explicit probe freshness + receipt metadata on `probe-session`, `preflight-smoke`, and `live-smoke-readiness` so operators can see how fresh the probe is and which receipt/file it came from
- classify preflight blockers cleanly by failure family (`auth`, `stale`, `disconnected`, `capability-mismatch`) instead of collapsing every miss into a generic not-connected state
- keep the account-query surface truthful: the current `steamer-cron-health` adapter proves broker + marketdata readiness, but does not independently assert account-query connectivity
- report whether the next broker-preflight step is blocked or ready, using logical session posture + operator baseline posture as the seed gate

Canonical probe truth metadata:

- `probe_source`: named source or manual probe identity
- `probe_freshness`: explicit freshness status, observed timestamp when known, and a short truth note
- `probe_receipt`: receipt/file pointer for the source actually consumed; seed posture remains explicit as unverified

Repo-side seed runner:

```bash
./ops/scripts/trading_day_preflight_seed.sh \
  examples/decks/tw_cash_intraday.toml \
  examples/profiles/tw_cash_password_auth.toml \
  open \
  examples/probes/session_health.connected.json
```

This runner exists so future trading-day cron wiring can bind one formal entrypoint instead of manually reconstructing the probe/preflight chain.

## Governance rules

- Authoring commands can be widely available.
- Replay and live-sim commands are broader, but still audited.
- Operator commands require stronger permissions and should map to explicit approvals.
- Auth/session inspection should expose capability boundaries clearly enough that a user can see whether trade permission is present.

## Output conventions

The CLI should support:

- concise human-readable output by default
- structured JSON output for automation
- stable exit codes

For the active operator + sim/replay execution lanes, JSON output now carries a small self-describing contract envelope:

- `cli_contract.version`: current machine-readable payload contract version (`cli-command/v1`)
- `cli_contract.command`: canonical command identity (for example `operator preflight-smoke`)
- `cli_contract.exit_code`: the same exit code returned by the process
- `cli_contract.exit_class`: normalized family (`success`, `operator-refused`, `confirmation-required`, `general-failure`)
- `cli_contract.status_key` + `cli_contract.status`: which command-level field should be treated as the primary machine gate (`probe_status`, `preflight_status`, `smoke_status`, `status`, `mode`, `bundle_status`)

This keeps automation from having to reconstruct contract meaning from shell exit codes alone.

### Exit codes (current + recommended)

- `0`: success
- `1`: CLI usage error / unhandled command / general failure
- `2`: validation/normalization failure (manifest or sim command input/schema errors)
- `3`: comparison completed but failed hard gates (`sim compare` status=`fail`)
- `4`: operator action refused due to posture/capability mismatch (also used when `live-smoke-readiness` is blocked by the preflight gate)
- `5`: operator action refused due to missing explicit confirmation

(Tests already assert `2` for validation errors; keep this stable.)

JSON surfaces that currently emit `cli_contract`:

- `replay run`
- `sim run-live`
- `sim normalize-baseline`
- `sim compare`
- `operator probe-session`
- `operator preflight-smoke`
- `operator live-smoke-readiness`

Suggested flags:

- `--json`
- `--verbose`
- `--dry-run`
- `--strict`
- `--profile`

## State handling

The CLI should avoid magical hidden state.

Preferred inputs:

- explicit file paths
- explicit deck names
- explicit auth/profile selection
- explicit mode selection (`replay-sim`, `live-sim`, `live`)

The CLI should never make live authority ambiguous.

## Scenario identity inputs (contract target)

Replay/live-sim submissions should eventually accept one of:

- `--scenario-spec <path>` (preferred)
- explicit identity flags that can be converted into ScenarioSpec-equivalent fields

At minimum, submitted job metadata should carry:

- `scenario_id`
- symbol set identity
- session date/slice
- event source identity
- timezone/calendar
- execution/cost model knobs
- determinism posture + seed

Reference contract: `docs/SCENARIO_SPEC.md`.

Current reality: this is a docs-level target; strict runtime enforcement is not complete yet.

## v0.1 implementation notes

Current implementation status:

- ✅ `auth validate-profile` / `auth inspect-profile`
- ✅ `author validate-card` / `author inspect-card`
- ✅ `author validate-deck` / `author inspect-deck`
- ✅ `author validate-global` / `author inspect-global`
- ✅ `sim normalize-baseline` (legacy baseline → v1-shaped M1 bundle)
- ✅ `sim compare` (hard-fail gates + decision-grade compare report)
- ✅ `replay run` emits candidate v1 bundles (legacy-bridge emitter for M1, with explicit provenance)
- ✅ seed operator posture controls: `operator status|arm-live|disarm-live|flatten` + TTL policy + action receipts
- ✅ `operator submit-order-smoke` explicit refusal while disarmed (seed smoke surface; no broker submission)
- ✅ `operator live-smoke-readiness` pass/fail smoke bundle for the bounded live-capability sequence (still prepared-only; no broker submission)
- ✅ `operator preflight-smoke` truthful blocked/ready gate for the next broker-preflight step
- ✅ `operator probe-session` / `preflight-smoke` named upstream truth adapter for `steamer-cron-health` stage receipts
- ✅ canonical operator probe/preflight/live-smoke payloads now surface explicit `probe_freshness` + `probe_receipt` metadata instead of only point-in-time readiness
- ✅ operator auto-disarm now closes invalid arm-scope TTL metadata (missing/malformed `expires_at`) in addition to normal TTL expiry

Next evolution order remains:

1. launch replay jobs
2. inspect replay/live-sim receipts
3. expose guarded operator actions

## Suggested stable artifacts

Replay and live-sim jobs should converge on a stable artifact set such as:

- run manifest
- event source identity
- feature/synthesizer versions
- intent receipts
- risk/execution receipts
- summary metrics

That keeps agent-assisted workflows reviewable instead of theatrical.

### Adapter probe commands

Stage 0 adapter work is pinned to a fixture-only probe:

```bash
steamer-card-engine adapter probe --fixture paper-only --json
```

The JSON payload uses the shared `cli_contract.version = "cli-command/v1"` envelope and reports adapter identity, capabilities, fixture-only session posture, preflight decision, sanitized normalized receipt, dispatch boundary, and `topology_changed=false`.

`--execution-mode live` and unknown modes fail closed with exit code `4` before dispatch. This command does not read credentials, connect to brokers, write operator state, or claim broker/paper/live readiness beyond the deterministic fixture.

### 7. Adapter fixture contract commands

Used for CLI-first adapter hardening without broker connectivity.

Examples:

```bash
steamer-card-engine adapter probe --fixture paper-only --json
steamer-card-engine adapter explain --adapter fixture-paper-only --json
steamer-card-engine adapter contract check --adapter fixture-paper-only --fixtures examples/probes/adapter_contract --json
steamer-card-engine adapter replay --adapter fixture-paper-only --fixtures examples/probes/adapter_contract --json
```

Responsibilities:

- expose adapter identity, capability profile, dispatch boundary, and topology status
- pin the Stage 1 machine-readable contract for input context, normalized signal/order-intent candidate, reject/no-op reasons, receipt envelope, and sanitizer behavior
- run deterministic golden fixture checks with stable reason codes (`paper_preflight_allowed`, `capability_mismatch`, `signal_no_action`)
- run a Stage 2 replay-only fixture stream that emits `adapter-replay/v1`, replay/fixture/adapter/input hashes, deterministic decisions, and simulation-only intents
- never emit broker-native orders; candidates remain normalized intent only with dispatch suppressed
- keep the surface fixture-only: no broker SDK, network, credential/env/certificate reads, `/workspace/steamer` state, or operator arm/disarm coupling

All JSON outputs include `cli_contract.version = "cli-command/v1"`.

### 8. Paper ledger commands

Stage 3 local paper execution uses a repo-local SQLite ledger and remains fixture-only:

```bash
steamer-card-engine paper run --adapter fixture-paper-only --fixtures examples/probes/adapter_contract --paper-ledger .state/paper/ledger.sqlite --receipt out/paper.receipt.json --json
steamer-card-engine paper audit --paper-ledger .state/paper/ledger.sqlite --json
```

Both commands emit `cli_contract.version = "cli-command/v1"`, `no_network=true`, and `topology_changed=false`. `paper run` emits `paper-run/v1`; `paper audit` emits `paper-audit/v1`. PnL is placeholder-only and must not be described as market-real.

### 9. Broker dry-run mock commands

Stage 4a broker dry-run is mock-only and requires the no-place-orders guard:

```bash
steamer-card-engine broker preflight --broker mock-fixture --mode dry-run --no-place-orders --mock-transport fixture --fixtures examples/probes/broker_dry_run --receipt docs/receipts/artifacts/2026-05-02_stage4a_broker_preflight_mock.receipt.json --json
steamer-card-engine broker redact-check --receipt docs/receipts/artifacts/2026-05-02_stage4a_broker_preflight_mock.receipt.json --json
```

`broker preflight` emits `broker-dry-run-preflight/v1`; `broker redact-check` emits `broker-dry-run-redact-check/v1`. This slice is mock transport only: no real SDK, network, credentials, account/session inspect, order placement, or live-readiness claim.

### 10. Observe-paper fixture live-shape command

Stage 5a observe-paper is fixture-only and paper-ledger-only:

```bash
steamer-card-engine observe paper --adapter fixture-paper-only --market-source fixture-live-shape --fixtures examples/probes/live_observe --execution paper --paper-ledger .state/paper/observe-ledger.sqlite --risk-profile conservative --duration-seconds 60 --stale-market-data-seconds 5 --receipt out/live-paper.receipt.json --json
```

The command emits `observe-paper-run/v1`, uses the shared `cli_contract.version = "cli-command/v1"`, and requires `--market-source fixture-live-shape` plus `--execution paper`. `--market-source live` is intentionally refused in Stage 5a; real live market-data observation is Stage 5b and requires separate CK authorization.
