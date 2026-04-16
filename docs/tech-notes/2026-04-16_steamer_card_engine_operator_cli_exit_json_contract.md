# 2026-04-16 — steamer-card-engine operator CLI exit / JSON contract

## Verdict

Land the smallest machine-readable contract patch on the existing operator broker-preflight lane.
Do not redesign command routing. Make the JSON payload say the same exit truth the shell already knows.

## What changed

- `operator probe-session`, `operator preflight-smoke`, and `operator live-smoke-readiness` now emit a top-level `cli_contract` object in JSON mode.
- `cli_contract` carries:
  - `version`
  - `command`
  - `exit_code`
  - `exit_class`
  - `status_key`
  - `status`
- This metadata is attached after the existing payload is assembled, so the command-specific truth surfaces stay intact.

## Why this slice

The repo already treated exit codes as part of the CLI contract, but automation still had to combine two channels of truth:

1. shell exit code outside the payload
2. command-specific status fields inside the payload

That is workable for humans, but brittle for downstream automation, receipts, and controller glue.
This patch makes the payload self-describing without inventing a new parallel schema.

## Scope discipline

- no new commands
- no exit-code remap
- no runtime topology change
- no attempt to normalize every legacy CLI surface in one pass

Only the active broker-preflight operator lane was hardened.

## Resulting contract

Example shape:

```json
{
  "cli_contract": {
    "version": "operator-cli/v1",
    "command": "operator preflight-smoke",
    "exit_code": 4,
    "exit_class": "operator-refused",
    "status_key": "preflight_status",
    "status": "blocked"
  }
}
```

Interpretation rules:

- `exit_code=0` -> `exit_class=success`
- `exit_code=4` -> `exit_class=operator-refused`
- `exit_code=5` -> `exit_class=confirmation-required`
- any other non-zero -> `exit_class=general-failure`

## Verification target

- `tests/test_cli.py` asserts the new `cli_contract` payload on seed probe, ready/blocked preflight, and pass/blocked/fail live-smoke outcomes.
- `docs/CLI_SPEC.md` now states the machine-readable envelope explicitly.

## Topology note

- contract truth changed: yes
- runtime topology changed: no
- cron topology changed: no
