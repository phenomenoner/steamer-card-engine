# M1 Evidence Packaging Hygiene (Option B)

Date (UTC): 2026-03-15

This document defines how `steamer-card-engine` keeps M1 evidence truthful **without** letting repository artifact footprint drift into avoidable bloat.

## Why this exists

M1 pre-sprint evidence includes large `event-log.jsonl` streams. Those streams are required for auditability, but multiple run bundles can carry byte-identical copies.

Hygiene goal: keep proof quality constant while reducing low-value duplication in repo working tree footprint.

## Evidence classification

### 1) Required durable evidence (must stay tracked)

- canonical M1 scenario bundles listed in `docs/M1_EVIDENCE_PACK_INDEX.md`
- per-bundle `run-manifest.json` + `file-index.json`
- comparator outputs under `comparisons/`
- acceptance/repeatability/operator receipts under `docs/receipts/`

These are acceptance-facing artifacts and cannot be dropped for cosmetic cleanup.

### 2) Too-large / low-value duplication (dedupe target)

- byte-identical `event-log.jsonl` copies across baseline/candidate bundles for the same scenario
- byte-identical `event-log.jsonl` copies across superseded exploratory reruns of the same scenario

These are not new evidence facts; they are repeated payload bytes.

### 3) Better represented as summary/index/pointer

- footprint diagnostics belong in small receipts (`docs/receipts/artifacts/*_artifact_footprint_*.json`)
- duplicate `event-log.jsonl` payloads are represented by symlink pointers to a canonical copy with unchanged content hash

## Current packaging policy

1. Keep at least one real (non-symlink) `event-log.jsonl` per unique content hash used by evidence bundles.
2. Replace duplicate `event-log.jsonl` copies with symlinks to the canonical copy when hashes match.
   - Cross-lane symlinks are allowed (`steamer-card-engine` bundle path pointing to `baseline-bot` canonical copy) only for byte-identical payloads.
   - Do not delete/move canonical copies without first re-pointing all incoming symlinks.
3. Never edit `file-index.json` hashes to “fit” cleanup; content must remain checksum-stable.
4. When exporting a standalone bundle outside this repo, dereference symlinks so the bundle is self-contained:

```bash
tar --dereference -czf <bundle>.tar.gz <run_bundle_dir>
```

5. New scenario additions must still satisfy `docs/M1_EVIDENCE_PACK_ACCEPTANCE_CONTRACT.md` and `docs/SIM_ARTIFACT_SPEC.md`.

## Guardrails

- No cleanup may hide provenance, relax hard-fail gates, or remove required artifacts.
- If a large artifact is uniquely informative (not duplicate), keep it and record why.

## Topology / boundary status

This hygiene policy changes repository packaging only.

- No runtime capability change
- No trust-boundary change
- No new external dependency
