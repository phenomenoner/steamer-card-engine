# 2026-04-26 — Steamer backlog after observer Priority 1

## Context

Priority 1 is observer-first monitor local closure. The items below are intentionally parked until that closure is verified and committed.

## Backlog item 1 — strategy-family verifier selection

- Decision needed: choose the next verifier-backed strategy family after observer closure.
- Candidate A: `timesfm_regime_rank_assist_v1`, prove whether TimesFM-derived rank / uncertainty beats dumb baselines after walk-forward stability and frictions.
- Candidate B: VCP / gate-meta family, exploit existing local Steamer evidence first.
- Required posture: research/control-plane only; no strategy-private params, symbol lists, or broker/runtime evidence in this repo.
- Success gate: one family gets a named verifier, acceptance criteria, kill criteria, and handoff target.

## Backlog item 2 — real-money smoke gate packet

- Decision needed: open a fresh explicit real-money smoke gate only after local observer closure and current broker/runtime truth are re-checked.
- Required posture: new authority boundary, not an extension of prior non-real-money validation closure.
- Must include: operator confirmation, broker/runtime preflight, kill switch, payload leakage review, observer visibility, and rollback/abort path.
- Success gate: a bounded execution packet exists before any real-money action.

## Topology

No topology change. This is backlog documentation only.
