# Changelog

## Unreleased

- Reworked the public README into a product-facing entrypoint with clearer boundaries between cards, decks, intents, adapters, receipts, and operator authority.
- Added `docs/LIVE_EXECUTION_GATE.md` to document the public live-execution gate contract.
- Documented the fill-source contract for live execution:
  - active filled callback is the primary low-latency path;
  - periodic broker readback is the safe-net reconciliation path;
  - P/L must never fall back to submitted limit prices.
- Clarified that historical receipts and tech notes are development evidence, not the public product entrypoint.

## 2026-05-05

- Added bounded Gate 5 live-execution support for a Taiwan cash-stock sell-first day-trade round trip.
- Added multi-symbol gate planning/execution support and a one-symbol live validation lane.
- Added entry filters for price, change percent, quantity, and day-trade capability.
- Added exit policy support for take-profit, stop-loss, and forced-cover time.
- Added active fill callback handling plus readback reconciliation in the NeoAPI broker adapter.
- Added tests for live fill-source selection and operator gate behavior.

## Earlier history

Earlier milestone receipts live under `docs/receipts/` and `docs/tech-notes/`. They are retained as development evidence and may contain implementation-era context; prefer README + top-level docs for public product orientation.
