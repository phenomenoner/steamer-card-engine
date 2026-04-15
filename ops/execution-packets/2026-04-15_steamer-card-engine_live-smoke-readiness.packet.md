# 2026-04-15 — steamer-card-engine live smoke readiness blade map

## Whole-picture promise

Move `steamer-card-engine` from "seed operator controls exist" to "operator can run one truthful, repeatable live-capability smoke sequence and get a pass/fail receipt bundle" without claiming broker-connected production readiness.

## Non-goal

- no real broker submission
- no hidden live activation
- no claim of full live-trading readiness
- no widening into dashboard or strategy-family work

## Serial queue board

1. **Blade 1 — smoke contract cut**
   - add a first-class CLI/operator surface that runs the bounded live-capability smoke sequence end-to-end
   - expected artifact: machine-readable smoke report with per-step pass/fail + receipt paths

2. **Blade 2 — verifier cut**
   - add focused pytest coverage for the smoke path
   - expected artifact: tests proving disarmed refusal, arm-live success, armed acceptance, flatten/disarm closure, and final disarmed status

3. **Blade 3 — operator-doc / topology / WAL cut**
   - update CLI spec / README / topology / tech note so repo truth matches runtime truth
   - expected artifact: docs point to the new smoke lane and keep prepared-only / not-broker-connected boundary explicit

4. **Blade 4 — cumulative diff second-brain review**
   - run one bounded final code/doc review over the cumulative diff
   - expected artifact: review note or no-material-issue receipt

## Verifier plan

- `uv run pytest -q tests/test_cli.py`
- optionally wider repo smoke if the diff touches shared paths materially
- manual CLI smoke on the new command in JSON mode

## Stop-loss

Stop and report if:
- the smoke command forces a larger operator-control redesign
- wrapper/tooling mechanics consume >2 loops before a core artifact exists
- the diff starts requiring real broker/session wiring

## Activation truth target

Prepared-only unless a future explicit activation step wires this into a real operator runtime. This slice is about smoke readiness, not live activation.
