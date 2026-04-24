# 2026-04-23 — steamer-card-engine observer lifecycle source blocker

## Verdict

The current blocker for expanding the observer bundle from candles/health into truthful order/fill/position state is **absence of a non-empty lifecycle artifact lane**, not observer wiring.

## What was checked

### Recent live-sim candidate lane (2026-04-23)
Checked candidate run directories under:
- `runs/steamer-card-engine/2026-04-23/...`

Observed:
- `order-lifecycle.jsonl` exists but empty
- `fills.jsonl` exists but empty
- `positions.jsonl` exists but empty
- `execution-log.jsonl` exists but empty

### Nearest historical non-empty lane
Checked:
- `runs/steamer-card-engine/2026-03-17/live-sim_tw-live-sim-twse-2026-03-17-full-session_candidate_20260318T005626Z`
- `runs/steamer-card-engine/2026-03-18/live-sim_tw-live-sim-twse-2026-03-18-full-session_candidate_20260319T015318Z`

Observed:
- `execution-log.jsonl` is non-empty
- but `order-lifecycle.jsonl`, `fills.jsonl`, and `positions.jsonl` are still empty
- `run-manifest.json` shows `trade_enabled: false`
- run status is `partial`
- `execution-log.jsonl` rows are request-shaped only and use `qty: 0.0`

## Conclusion

The currently available run artifacts can support at most:
- request-intent style operator notes
- coarse request visibility

They cannot truthfully support:
- `order_submitted`
- `order_acknowledged`
- `fill_received`
- `position_updated`

for the browser observer, because the repo-visible artifact lanes do not currently expose non-empty lifecycle state.

## Safe posture

Until a real lifecycle source exists, observer should continue using:
- candles
- health/freshness
- session probe notes
- operator-visible notes

and must not synthesize fake fills/positions from request logs.

## Next recommended move

Find the first lane outside current repo-visible run artifacts that truthfully emits non-empty lifecycle state, for example:
- private broker/session-manager receipts
- private runtime state snapshots
- a newer live-smoke lane with actual lifecycle persistence enabled

Only after that should the private emitter add lifecycle event mapping.
