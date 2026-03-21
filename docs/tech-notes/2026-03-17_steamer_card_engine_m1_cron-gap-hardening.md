# 2026-03-17 — Steamer Card Engine M1 cron-gap diagnosis + post-close hardening

## Trigger

Morning exception handling was needed before 09:00 Asia/Taipei to run a progress pass and recover truthful blocker state.
Question: why did "the original cron" not pull the line up, and what is the smallest safe fix?

## Root-cause verdict

1) **Schedule-semantics mismatch (primary):**
- Live controller job `f4ab2bcc-eb96-4463-8398-ca67b4dc0437` is scheduled at `13:40 Asia/Taipei`.
- It is a post-close **progress/controller** pass, not a pre-open launch line.
- Therefore it cannot satisfy a pre-09:00 expectation by design.

2) **Lane-role mismatch (primary):**
- The controller lane keeps sprint truth and gate status; it does not execute a `sim run-live` lane.
- Current truthful blocker remains: `steamer-card-engine sim run-live` is not implemented yet (CLI currently shows only `sim normalize-baseline` + `sim compare`).

3) **Manual-run receipt semantics (secondary confusion amplifier):**
- `openclaw cron run` acknowledges **enqueue**, not finished execution.
- An enqueue receipt is not proof that the run has started/finished; completion must be read from `openclaw cron runs --id ...` (or run logs).

## Gap vs CK standard

- Exception handling today is acceptable.
- But pre-fix posture lacked a dedicated post-close guardrail to page when:
  - the progress controller did not finish today, or
  - Stage 4 remained blocked by the relevant gate.

## Minimal hardening implemented

Added one bounded watchdog lane (post-close, silent-on-green):

- **New live cron job**: `909de5a3-b481-4e50-88fd-2c649c4b3829`
  - name: `watchdog: steamer-card-engine M1 post-close triage (silent-on-green)`
  - schedule: `14:15 Asia/Taipei`
  - role:
    1. alert if progress controller run is missing today
    2. alert if latest progress run finished non-OK
    3. triage Stage 4 blocker posture (`sim run-live` support + live-sim bundle presence)
  - green path: `NO_REPLY`

- **New checker script**:
  - `/root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_m1_postclose_watchdog.py`

- **Associated cron spec**:
  - `cron/jobs/909de5a3-b481-4e50-88fd-2c649c4b3829.md`

## Why this is the smallest correct fix

- No broad infra restart/reload path.
- No scope widening into implementing `sim run-live` itself.
- Keeps existing controller job semantics intact.
- Adds exactly one independent post-close verifier/triage lane that catches "line missing" + "gate blocked" conditions.

## Validation receipts

- script dry run:
  - `python3 .../steamer_card_engine_m1_postclose_watchdog.py`
  - observed output: `STEAMER_M1_POSTCLOSE WARN stage4_blocked reason=sim-run-live-missing ...`
- static check:
  - `python3 -m compileall .../steamer_card_engine_m1_postclose_watchdog.py`
- live scheduler add receipt:
  - `openclaw cron add ...` created `909de5a3-b481-4e50-88fd-2c649c4b3829`

## Topology statement

- **Topology changed (bounded):** one post-close watchdog job added for Steamer Card Engine M1 sprint line.
- **Boundary/capability unchanged:** still sim-only; no live trading / broker submission authority expansion.
