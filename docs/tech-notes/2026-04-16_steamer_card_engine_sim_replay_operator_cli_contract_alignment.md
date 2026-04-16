# 2026-04-16 — steamer-card-engine sim/replay and operator CLI contract alignment

## Verdict

Extend the same machine-readable CLI contract envelope across the active sim/replay lane.
Do not redesign sim artifacts. Do not remap exit codes. Just make JSON outputs and JSON error paths speak the same contract dialect.

## What changed

- `replay run` now emits `cli_contract` in JSON mode.
- `sim run-live` now emits `cli_contract` in JSON mode.
- `sim normalize-baseline` now emits `cli_contract` in JSON mode.
- `sim compare` now emits `cli_contract` in JSON mode for both pass and hard-fail (`exit_code=3`) outcomes.
- `SimCompareError` now stays machine-readable under `--json` instead of falling back to plain text.

## Contract envelope

The shared envelope version is now `cli-command/v1`.

Fields:
- `version`
- `command`
- `exit_code`
- `exit_class`
- `status_key`
- `status`

Examples:

```json
{
  "cli_contract": {
    "version": "cli-command/v1",
    "command": "sim compare",
    "exit_code": 3,
    "exit_class": "general-failure",
    "status_key": "status",
    "status": "fail"
  }
}
```

```json
{
  "cli_contract": {
    "version": "cli-command/v1",
    "command": "replay run",
    "exit_code": 2,
    "exit_class": "general-failure",
    "status_key": "status",
    "status": "error"
  }
}
```

## Why this slice

Before this patch, the active operator lane had a machine-readable exit contract, but sim/replay automation still had to special-case:

1. structured JSON on success
2. mixed JSON/plain-text behavior on command errors
3. different assumptions about where the primary gate field lived

That meant downstream controller glue could not treat the active execution lanes as one family.

## Scope discipline

- no command-surface expansion
- no exit-code remap
- no artifact-schema rewrite
- no attempt to normalize every legacy author/catalog/auth command in the same pass

This is only about the currently active execution family: replay, sim, and operator broker-preflight.

## Verification target

- `tests/test_cli.py` continues to assert operator-lane contract envelopes.
- `tests/test_sim_compare.py` now asserts:
  - `sim normalize-baseline`
  - `sim compare` fail/pass
  - `replay run` emit/dry-run/error
  - `sim run-live` emit/dry-run
- `docs/CLI_SPEC.md` now lists the aligned surfaces explicitly.

## Topology note

- contract truth changed: yes
- runtime topology changed: no
- cron topology changed: no
