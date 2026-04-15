# Strategy Powerhouse handoff accepted — TimesFM regime-rank assist

- recorded: 2026-04-15
- source: `strategy-powerhouse-framework/docs/packets/2026-04-15_timesfm_regime_rank_assist.packet.md`
- family / candidate: `timesfm_regime_rank_assist`
- acceptance state: **accepted as observation-only research handoff**
- intended surface: `replay` planning first, `live-sim observation` only after verifier truth exists

## Why this is accepted

This handoff is small enough to be honest and useful:
- it does not pretend TimesFM zero-shot sign prediction is already tradable alpha
- it keeps the first slice at benchmark / regime-helper level
- it defines explicit kill criteria against simple baselines
- it preserves `steamer-card-engine` as the downstream execution surface instead of silently mutating active runtime truth

## Bounded downstream contract

`steamer-card-engine` accepts this as a **research-facing execution packet**, not an activation order.
That means:
- the family may be carried as a proposal / observation candidate
- no card or deck becomes active from this packet alone
- no live trading authority is implied
- no replay or live-sim claim should be made until a real verifier receipt exists

## Expected verifier bridge

The next truthful bridge is one of these two, in order:

1. **Rank / bucket baseline receipt**
   - prove TimesFM-derived ranking beats dumb baselines on daily or 30m walk-forward tests
2. **Intraday regime helper receipt**
   - prove TimesFM-derived volatility or range-expansion filtering improves an existing intraday family without pretending to predict direction directly

If neither bridge passes, retire the packet.

## Safe handling rules

- Treat TimesFM outputs as feature / filter / benchmark candidates only.
- Do not attach point-forecast sign directly to order intent.
- Do not claim handoff readiness beyond `proposal only` until verifier truth exists.
- Keep any private symbol universe, thresholds, and raw evidence outside this repo unless already approved for local-only intake.

## Topology statement

- topology unchanged
- `strategy-powerhouse-framework` remains research / packaging / control-plane only
- `steamer-card-engine` remains execution / card-deck / replay / live-sim surface
- this file is an acceptance receipt for a bounded packet, not activation proof

## What counts as completion of this handoff

Completion for this pass means only:
1. the packet exists in the framework repo
2. the downstream acceptance receipt exists in `steamer-card-engine`
3. both are pushed
4. WAL records the decision and topology truth

Anything beyond that needs a separate verifier lane.
