# Triangle trace compare report

## Verdict
PASS_BC_SEMANTICS

## Trace summaries

### A_historical
- rows: 50014
- enter_true: 0
- symbol_count: 10
- reason_top20: `{'now_time_5': 46163, 'sweet': 3841, 'blocked_blind_open': 10}`

### B_latest_legacy_replay
- rows: 50549
- enter_true: 0
- symbol_count: 10
- reason_top20: `{'now_time_5': 50381, 'sweet': 158, 'blocked_blind_open': 10}`

### C_card_candidate
- rows: 50549
- enter_true: 0
- symbol_count: 10
- reason_top20: `{'now_time_5': 50381, 'sweet': 158, 'blocked_blind_open': 10}`

## Pairwise deltas

### A_vs_B
- row_delta: 535
- enter_true_delta: 0
- symbol_count_delta: 0
- reason_delta_top20_scope: `{'now_time_5': 4218, 'sweet': -3683}`

### B_vs_C
- row_delta: 0
- enter_true_delta: 0
- symbol_count_delta: 0
- reason_delta_top20_scope: `{}`

### A_vs_C
- row_delta: 535
- enter_true_delta: 0
- symbol_count_delta: 0
- reason_delta_top20_scope: `{'now_time_5': 4218, 'sweet': -3683}`

## Interpretation
- A-vs-B isolates historical/runtime lineage and replay-substrate gaps.
- B-vs-C isolates card-engine semantic replication. If C is generated from B state, this should be exact unless card semantics diverge.
- A-vs-C remains useful as an operational parity signal but should not be used alone as truth.
