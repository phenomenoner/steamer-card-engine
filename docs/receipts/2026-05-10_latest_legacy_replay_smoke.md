# Latest legacy replay smoke — 2026-05-10

## Verdict

A bounded latest-legacy replay emitter now exists for `REV_SHORT_AFTER_UP`.

This is not full A/B/C closure yet. It is the first B-lane smoke: recorded ticks -> reconstructed latest-legacy-compatible decision trace.

## Implementation

```text
src/steamer_card_engine/legacy_replay.py
tests/test_legacy_replay.py
```

Smoke artifact:

```text
runs/legacy-equivalence/2026-05-10-latest-legacy-replay-20260129-pre930/latest_legacy_replay_summary.json
runs/legacy-equivalence/2026-05-10-latest-legacy-replay-20260129-pre930/latest_legacy_replay_decisions.jsonl
```

## Smoke run

Dataset:

```text
dt3/20260129
REV_SHORT_AFTER_UP
slice: <= 09:30:00 local
```

Historical A slice:

```text
rows=50,014
enter_true=0
reason_top:
- now_time_5: 46,163
- sweet: 3,841
- blocked_blind_open: 10
```

Latest replay B smoke:

```text
rows=50,549
enter_true=0
reason_top:
- now_time_5: 50,381
- sweet: 158
- blocked_blind_open: 10
```

## Interpretation

The important smoke gate passed: B emits deterministic rows from ticks and matches the pre-09:30 no-entry invariant.

The reason distribution is not yet expected to match exactly because:

- historical A uses live bot target/universe and exact sweet-range implementation;
- B currently reconstructs a bounded active universe from historical symbols and uses a permissive local sweet proxy;
- B is still a replay emitter smoke, not a complete legacy runtime clone.

The prior tick probe established core price fields are reconstructable. This smoke establishes decision emission can be generated from ticks without broker/live side effects.

## Next required blade

Implement `triangle_compare`:

```text
A: historical decisions.jsonl
B: latest_legacy_replay_decisions.jsonl
C: card-engine candidate trace
```

First compare time-sliced invariants and reason distributions, then move to exact per-symbol/timestamp matching only after universe and sweet-range policy are made explicit.

## Tests

```text
uv run pytest tests/test_legacy_equivalence.py tests/test_legacy_lineage_and_tick_probe.py tests/test_legacy_replay.py tests/test_sim_compare.py -q
```

Expected: all pass.

## Topology/config impact

Unchanged. No cron, gateway, live monitor, broker, or remote topology changed.
