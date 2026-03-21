# 2026-03-18 — Steamer Card Engine M1 live-sim timing alignment note

## Trigger

CK flagged an operation-detail mismatch after the first truthful Stage 4 `live-sim` bundle was emitted manually during market hours on 2026-03-18.

Question:
- if `live-sim-attached` is meant to represent **same-day market attachment**, does the current automation surface express that standard truthfully?

## Current truth

- First truthful Stage 4 bundle now exists:
  - `steamer-card-engine/runs/steamer-card-engine/2026-03-17/live-sim_tw-live-sim-twse-2026-03-17-full-session_candidate_20260318T005626Z/`
- It was emitted manually at about **2026-03-18 08:56 Asia/Taipei** using the checked-in helper:
  - `/root/.openclaw/workspace/steamer-card-engine/tools/steamer_card_engine_stage4_live_sim_first_run.py`
- The current live automation around the sprint is still:
  - progress controller `f4ab2bcc-eb96-4463-8398-ca67b4dc0437` at **13:40 Asia/Taipei**
  - post-close watchdog `909de5a3-b481-4e50-88fd-2c649c4b3829` at **14:15 Asia/Taipei`

## Alignment verdict

- Under the **written sprint contract**, Stage 4 is closed: the required first truthful `run_type=live-sim` bundle now exists.
- Under CK's stated **operation-detail standard**, the old 13:40 / 14:15 automation should **not** be mistaken for canonical `live-sim-attached` timing if the intended meaning is same-day morning market attachment.
- That follow-up is now **resolved** by the 2026-03-20 promotion:
  - strategy-powerhouse-governed canonical morning paired lane at `09:05` Asia/Taipei
  - receipt: `projects/steamer/TECH_NOTES/2026-03-20_steamer_canonical-morning_paired-lane_promotion.md`

## What stays true

- Authority remains sim-only.
- No broker-submission semantics were widened.
- The final chosen shape is still **strategy-powerhouse-governed coordination**, not an independent `steamer-card-engine` launcher rail.

## Resolution summary

Chosen canonical contract:
1. **Morning-attachment contract under strategy-powerhouse governance**
   - `live-sim-attached` means the paired compare surface belongs to the same-day morning evidence chain.
   - it is attached after same-day `verify`, not after post-close progress/watchdog timing.
2. **No independent launcher rail**
   - the promotion must remain coordinated under the broader Steamer strategy-powerhouse operating surface.

## Decision (CK, 2026-03-18)

- `steamer-card-engine` automation timing should **not** become an independently-starting line.
- Its future automation posture should be coordinated under the broader **Steamer strategy powerhouse** operating surface instead of being treated as a separate morning launcher.
- Near-term implication:
  - keep the truthful Stage 4 bundle receipt
  - do **not** reinterpret the current 13:40 / 14:15 controller+watchdog pair as the final canonical automation shape
  - defer the integrated timing/coordination arrangement until after confirming `steamer-card-engine` operation success in context

## Recommended current reading

- Do **not** reopen Stage 4; its milestone truth already stands.
- Read this note as the historical mismatch diagnosis.
- Read `projects/steamer/TECH_NOTES/2026-03-20_steamer_canonical-morning_paired-lane_promotion.md` as the closure receipt for the timing-semantics follow-up.
