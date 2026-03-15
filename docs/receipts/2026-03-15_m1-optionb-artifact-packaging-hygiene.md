# M1 Option B Receipt — artifact size / evidence packaging hygiene

Date (UTC): 2026-03-15

## Outcome

Done (bounded hygiene pass).

## Phase 1 — reality-first inventory

Footprint diagnostics (before):

- `docs/receipts/artifacts/2026-03-15_optionb_artifact_footprint_before.json`

Key facts:

- tracked worktree bytes (tracked files): `187,970,325`
- `runs/` worktree bytes: `187,617,987`
- large tracked artifacts are dominated by `event-log.jsonl`
- `event-log.jsonl` duplication pattern:
  - sha `277259...` (2026-03-10): 2 copies, total `160,557,776` bytes
  - sha `66d486...` (2026-03-12): 2 copies, total `19,612,606` bytes
  - sha `cd1e1d...` (2026-03-06): 6 copies, total `6,051,714` bytes

Classification:

1. required durable evidence:
   - canonical 3-scenario bundles + compare outputs + acceptance receipts
2. too-large / low-value tracked artifact:
   - byte-identical duplicate `event-log.jsonl` copies across lanes/reruns
3. better represented as pointer/index:
   - duplicate logs represented as symlink pointers to canonical copies with unchanged content hashes

## Phase 2 — bounded hygiene implementation

Implemented symlink dedupe for duplicate `event-log.jsonl` payloads (7 paths switched to symlink).

Canonical non-symlink event logs retained:

- `runs/baseline-bot/2026-03-06/..._20260315T082717Z/event-log.jsonl`
- `runs/baseline-bot/2026-03-10/..._20260315T082721Z/event-log.jsonl`
- `runs/baseline-bot/2026-03-12/..._20260315T082719Z/event-log.jsonl`

After diagnostics:

- `docs/receipts/artifacts/2026-03-15_optionb_artifact_footprint_after.json`

Observed effect (worktree/lstat footprint):

- tracked files: `187,970,325` → `92,842,868` bytes
- `runs/`: `187,617,987` → `92,490,530` bytes

No checksum-truth shortcuts were used; `event-log.jsonl` resolved content hashes remain unchanged.

## Phase 3 — docs / topology / operator sync

Updated docs to reflect packaging posture:

- `docs/EVIDENCE_PACKAGING_HYGIENE.md` (new policy)
- `docs/SIM_ARTIFACT_SPEC.md` (symlink packaging note)
- `docs/M1_EVIDENCE_PACK_INDEX.md` (packaging note + policy pointer)
- `docs/SETUP.md` (operator packaging hygiene checks)
- `README.md` (new hygiene doc link + status note)
- `docs/TOPOLOGY.md` (repo map + receipt + run artifact note)

Topology status:

- capability boundary/dependency truth is unchanged
- this pass changes packaging representation only (no runtime authority change)

## Validation receipts

- validation artifact: `docs/receipts/artifacts/2026-03-15_optionb_validation.json`
- bundle validation across committed runs:
  - `uv run python - <<'PY' ... validate_bundle(...)` → 10 bundles, 0 failures
- tests:
  - `uv run pytest tests/test_sim_compare.py -q` → `9 passed`

## Final Copilot batch review

- receipt: `docs/receipts/artifacts/2026-03-15_optionb_final_copilot_review.txt`
- result: no critical issue; one medium guardrail on cross-lane canonical deletion risk
- accepted fix: `docs/EVIDENCE_PACKAGING_HYGIENE.md` now explicitly forbids deleting/moving canonical copies before re-pointing incoming symlinks

## Risk note

Symlinked artifact paths are safe inside repo checks/validation, but standalone bundle exports should dereference symlinks:

- `tar --dereference -czf <bundle>.tar.gz <run_bundle_dir>`
