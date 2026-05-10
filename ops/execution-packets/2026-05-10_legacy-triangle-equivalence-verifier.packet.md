# Legacy triangle equivalence verifier — execution packet

## Verdict
Proceed. The next verifier slice should not treat historical `decisions.jsonl` as sole truth. Use a three-way comparison:

```text
A: historical legacy decisions.jsonl
B: latest legacy logic replayed from recorded ticks
C: steamer-card-engine compatibility/card replay
```

This separates historical bot drift from card-engine replication errors.

## Goal
Explain concrete causes of decision-trace differences between legacy bot history and steamer-card-engine, efficiently and reproducibly.

## Non-goals
- No broker/live execution.
- No PnL/fill equivalence yet.
- No remote push.
- No writes into Hermes/Xixi A2A handoff folders.

## Inputs
- Legacy data root: `/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data`
- Per session: `ticks.jsonl`, `decisions.jsonl`, optional `orders.jsonl`
- Latest legacy gate code from `/workspace/CC/StrategyExecuter_Steamer-Antigravity/magicbox/gates.py`
- Card-engine verifier code in this repo.

## Core method

### Lane A — historical legacy oracle
Read recorded `decisions.jsonl` as executed-history evidence. This includes strategy gate decisions and sometimes risk/order-layer block reasons (`no_funds`, `lot_limit_reached`).

### Lane B — latest legacy tick replay
Rebuild decision states from recorded `ticks.jsonl` using the latest available legacy logic, then emit a fresh decision trace. This is not historical truth; it is current-legacy-on-old-market-data truth.

### Lane C — card-engine candidate replay
Run the card-engine compatibility/card logic on the same replay states/events and emit candidate decision trace.

## Comparison matrix

| Pair | Meaning |
|---|---|
| A vs B | historical bot drift / policy/runtime changed since the recorded day |
| B vs C | current legacy semantics vs card-engine replication quality |
| A vs C | operational parity with recorded history; useful but not enough alone |

## Difference taxonomy

Classify each mismatch as one of:

1. `policy_lineage` — `market_gate`, thresholds, trend-conflict, honey-sweet buffer, entry pause changed.
2. `risk_order_layer` — historical decision row reflects `no_funds`, `lot_limit_reached`, or post-gate runtime blocking.
3. `feature_reconstruction` — latest replay cannot reconstruct `state` fields from ticks within tolerance.
4. `state_clock_alignment` — timestamp/session/open/trial-match ordering differs.
5. `gate_semantics` — B and C diverge after same state/config; likely card implementation issue.
6. `data_quality` — missing ticks, malformed rows, zero-byte files, timestamp gaps.
7. `unknown` — not enough evidence; must surface sample rows.

## Efficient execution plan

### Slice 1 — lineage classifier over existing artifacts
Use existing historical `decisions.jsonl` plus current verifier output to classify known full-sweep mismatches without replaying ticks yet.

Outputs:
- `runs/legacy-equivalence/<run>/lineage_classification.json`
- `runs/legacy-equivalence/<run>/lineage_report.md`

### Slice 2 — tick replay feasibility probe
Pick one PASS day and one FAIL day:
- PASS: `dt3/20260129`
- FAIL: `dt3/20260122`

Build a minimal state reconstruction probe from ticks for `REV_SHORT_AFTER_UP` fields only. Compare reconstructed state against nearest historical decision state on sampled symbols/timestamps.

Acceptance:
- Report field-level reconstruction error/tolerance.
- If state reconstruction cannot match, stop before claiming B-vs-C parity.

### Slice 3 — latest legacy replay emitter
Emit `latest_legacy_replay_decisions.jsonl` for a bounded session/symbol set.

Acceptance:
- deterministic output for same input ticks/config.
- explicit effective config.
- no broker/risk side effects.

### Slice 4 — three-way comparator
Compare A/B/C and produce:
- per-date summary
- mismatch class counts
- first divergence samples
- recommended fix per class

## Verifier commands target

```bash
uv run python -m steamer_card_engine.legacy_equivalence classify-lineage \
  --summary runs/legacy-equivalence/2026-05-10-revshort-multiday/summary.json \
  --output-dir runs/legacy-equivalence/2026-05-10-revshort-lineage

uv run python -m steamer_card_engine.legacy_tick_probe \
  --data-root /workspace/CC/StrategyExecuter_Steamer-Antigravity/.data \
  --machine dt3 --date 20260129 --gate REV_SHORT_AFTER_UP \
  --output-dir runs/legacy-equivalence/2026-05-10-tick-probe-20260129
```

## Closure condition
A useful next milestone is not “everything PASS”. It is:

```text
>=90% of full-sweep mismatches assigned to a concrete class
B-vs-C zero enter mismatches on one PASS day replay probe
all unknown classes have sample rows and next evidence needed
```

## Topology/config impact
Unchanged. Repo-local verifier tooling only.
