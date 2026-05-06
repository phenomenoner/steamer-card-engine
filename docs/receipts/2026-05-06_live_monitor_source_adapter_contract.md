# 2026-05-06 Live Monitor source-adapter contract closure

## Change

Formalized the live monitor sidecar runtime discovery contract:

- added `RuntimeSourceAdapter` registry in `runtime_sources.py`
- added `local-runs` and `aws-live-sim` source layouts
- routed runtime chart fallback and runtime-store import through the adapter registry
- added runtime freshness snapshot support and endpoint
- made runtime-store import receipts expose `adapters`, `source_kinds`, and `warnings`
- documented the public sidecar contract in `docs/LIVE_MONITOR_SIDECAR.md`

## Why now

The live AWS sidecar was receiving raw ticks, but the runtime-store importer had assumed only the local fixture layout:

```text
runs/<lane>/<YYYY-MM-DD>/<run-id>/...
```

The live host used:

```text
<runtime-root>/<YYYYMMDD>/<run-id>/data/<YYYYMMDD>/ticks.jsonl
```

This produced a reachable dashboard and healthy service while the importer silently missed fresh runs. The product fix is a source layout adapter contract plus a freshness verifier, not another one-off path patch.

## Public product invariants

- Sidecar remains read-only; no broker authority or trading control is added.
- Runtime chart truth remains exact date/symbol only.
- New source layouts must enter through adapters, not scattered path checks.
- Import receipts must distinguish zero-data success from zero-run discovery warnings.
- Freshness is separate from HTTP health.

## Verification

Local verifier artifact:

- `.state/steamer-live-monitor-v14-source-adapter-contract/local_verify_v3.log`

Local verifier results:

- `46 passed` for dashboard tests
- ruff passed for changed dashboard modules/tests
- frontend Vite build passed
- TypeScript `tsc --noEmit` passed

AWS-layout dry-run artifact:

- `.state/steamer-live-monitor-v14-source-adapter-contract/aws_layout_dryrun_v14.json`

AWS-layout dry-run result:

- package: `steamer-live-monitor-v14-20260506T0325Z-99b6226-source-adapter-contract.tar.gz`
- adapter readback: `adapters=["aws-live-sim"]`
- source layout readback: `source_kinds=["runtime-aws-live-sim-layout"]`
- dry-run import: `run_count=1`, `tick_count=253708`, `warnings=[]`
- freshness snapshot for `00632R`: `state=fresh`, `api_latest_bar_utc=2026-05-06T03:25:00Z`, `lag_seconds≈50.8`

Counterfactual coverage added:

- AWS live-sim layout fixture imports ticks and reports adapter metadata.
- AWS live-sim adapter ignores non-run directories under a date root.
- Empty/mispointed root returns explicit warning for missing runtime run roots.
- Freshness detects lag when raw ticks are newer than API/store bars.
- Freshness reports fresh/import-missing/no-raw-ticks states.

## Review gates

- Claude second-brain review: `/workspace/.reviews/steamer-sidecar-v14-claude-review.md`; verdict `PASS with conditions`. Conditions were resolved by citing AWS dry-run evidence and validating AWS adapter run-root filtering.
- QA review: `/workspace/.reviews/steamer-sidecar-v14-qa-review.md`; verdict `PASS for deploy gate after condition fixes`.
- Product documentation review: `docs/LIVE_MONITOR_SIDECAR.md` updated to document source adapters, receipt fields, and freshness endpoint/SLA semantics.

## Live deploy smoke

Live deploy artifact:

- `.state/steamer-live-monitor-v14-source-adapter-contract/deploy_v14_result.json`

Live deploy result:

- release: `/opt/trading/releases/steamer-live-monitor-v14-20260506T0325Z-99b6226-source-adapter-contract`
- import receipt: `adapters=["aws-live-sim"]`, `source_kinds=["runtime-aws-live-sim-layout"]`, `run_count=1`, `tick_count=256063`, `warnings=[]`
- services: dashboard active; runtime-store import timer active

External readback artifact:

- `.state/steamer-live-monitor-v14-source-adapter-contract/external_readback_v14.json`

External readback result:

- asset: `index-BxJ8jou9.js`
- `00632R`: `runtime-ticks-jsonl`, `4885 ticks`, `175 bars`
- latest external bar: `2026-05-06T03:31:00Z`
- freshness endpoint: `state=fresh`, `api_latest_bar_utc=2026-05-06T03:30:00Z`, `lag_seconds≈69.1`

## Rollback

Revert the source adapter/freshness/docs patch and redeploy the previous live monitor release if adapter discovery or freshness endpoint regresses production behavior.
