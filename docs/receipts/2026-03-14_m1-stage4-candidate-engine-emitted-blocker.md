# M1 Stage 4 Receipt — candidate-engine-emitted replay-sim blocker package

Date (UTC): 2026-03-14

## Outcome

- `status`: **blocked**
- framing: Stage 4 was run as a serial lane to produce a **true candidate-engine-emitted** replay-sim bundle under the same scenario/execution-model contract as Stage 3.
- result: current repo truth does not yet provide a truthful candidate emission path, so no honest Stage 4 comparability receipt can be claimed yet.

### Stage-4 acceptance meaning used in this lane

For this receipt, “candidate-engine-emitted” means all of the following must be true:

1. bundle is produced by a candidate runtime path (not `sim normalize-baseline` same-source conversion),
2. bundle includes the full v1 artifact set under `runs/steamer-card-engine/<session_date>/<run_id>/`,
3. run manifest provenance names candidate engine runtime (not baseline normalizer),
4. `scenario_id` and canonicalized `execution_model` remain aligned with baseline for comparator eligibility.

## Scenario used (re-used from Stage 3)

- `scenario_id`: `tw-paper-sim.twse.2026-03-06.full-session`
- `session_date`: `2026-03-06`
- baseline source: `openclaw-async-coding-playbook/projects/trading-research/artifacts/tw-paper-sim/2026-03-06/`
- baseline bundle (existing):
  - `runs/baseline-bot/2026-03-06/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_baseline_20260314T200700Z/`

## What was tried

1. Attempted candidate replay run via CLI on the canonical date:

```bash
uv run steamer-card-engine replay run --deck examples/decks/tw_cash_intraday.toml --date 2026-03-06
```

Observed output:

```text
Placeholder replay job for deck=examples/decks/tw_cash_intraday.toml date=2026-03-06
```

2. Verified implementation surface for candidate emission:
   - `src/steamer_card_engine/cli.py:326` still routes replay to a placeholder print path.
   - `src/steamer_card_engine/runtime/components.py:45-49` has `ReplayRunner.feed()` incrementing a counter only; no artifact bundle emission path exists.

## Blocker evidence

- CLI replay implementation remains placeholder (`src/steamer_card_engine/cli.py:326`): `Placeholder {mode} job for deck=...`.
- Runtime replay component has no bundle writer path (`src/steamer_card_engine/runtime/components.py:45-49`); `ReplayRunner.feed()` only increments `processed_events`.
- Replay run attempt transcript is archived at `docs/receipts/artifacts/2026-03-14_stage4_replay-run_attempt.txt` and shows the placeholder response.
- Existing Stage 3 candidate bundle remains same-source normalizer output (`runs/steamer-card-engine/2026-03-06/replay-sim_tw-paper-sim-twse-2026-03-06-full-session_candidate_20260314T200700Z/run-manifest.json`, `provenance.engine_name=steamer-card-engine-baseline-normalizer`), which cannot be relabeled as candidate-engine behavior evidence.
- Candidate run directory listing after attempt is archived at `docs/receipts/artifacts/2026-03-14_stage4_candidate-run-dirs.txt` and shows no new Stage 4 candidate emission run.

## Compare status

- comparator run for Stage 4: **not executed**
- reason: no truthful candidate-engine-emitted bundle exists to compare against the baseline while keeping the same scenario identity / execution-model contract honest.

## Where it is stuck

- Candidate replay lane is still a placeholder interface and does not emit M1 artifact bundles.

## Next options

1. **Implement minimal truthful candidate replay emitter (recommended)**
   - scope: `replay run` emits v1 bundle with real event-log + explicit anomalies for unimplemented layers.
   - risk/time: medium risk, ~0.5–1.5 days; strongest path to an honest Stage 4 rerun.
2. **Add a dedicated `sim emit-candidate` command first, keep `replay run` untouched**
   - scope: ship bounded candidate emitter without changing replay UX semantics yet.
   - risk/time: medium risk, ~0.5–1 day; keeps blast radius smaller.
3. **Stay blocked and continue contract-only hardening**
   - scope: no candidate emission implementation yet; improve validator/comparator strictness only.
   - risk/time: low implementation risk, but does not advance Stage 4 evidence beyond Stage 3 plumbing.

## Topology update decision

- **No topology doc update was made.**
- Reason: durable topology/repo architecture did not change; this lane produced a capability blocker receipt, not a new runtime path.
