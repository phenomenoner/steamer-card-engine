# Steamer Observer v0 UI Implementation — Blade Map

> Date: 2026-04-28  
> Line: `櫻花刀舞 non-stop`  
> Repo: `/root/.openclaw/workspace/steamer-card-engine`  
> Design inputs:
> - `/workspace/.steamer-dashboard-design/steamer-live-monitor-dashboard-v0-spec.md`
> - `/workspace/.steamer-dashboard-design/Steamer-dashboar-v1.zip`
> - `/workspace/.steamer-dashboard-design/steamer-live-monitor-dashboard-v0-design-feedback.md`

## Verdict

Run this as a serial, verifier-backed implementation line: preserve the current observer API/bundle truth model, port the useful v1 UI ideas into the existing Vite/React surface, then QA/UIUX-review before AWS deployment.

Do **not** paste the mock zip into production. Treat it as a north-star design artifact.

## Whole-picture promise

Steamer Observer v0 lets an operator open a browser and answer within 10 seconds:

1. Which session am I looking at?
2. Is this live(sim), replay, or fixture?
3. Is the data fresh / stale / degraded / empty / replay-valid?
4. What happened recently on chart + timeline?
5. Do orders/fills/position reconcile?
6. Where is the receipt / provenance?
7. Is the browser still read-only and sanitized?

Fake progress: visual polish that weakens read-only/provenance boundaries, frontend-inferred trading truth, or deploy without local verifier + leakage scan.

## Non-negotiable boundaries

- Public/browser surface remains read-only.
- No browser order submit/cancel/modify/write-back.
- No private runtime discovery from frontend.
- Frontend consumes `/api/observer/...` and `ObserverBundle`-derived payloads only.
- No credentials/account/routing IDs/real endpoints/alpha-bearing thresholds in browser-visible payload.
- Replay state must not silently invent business truth. If frontend derives temporary presentation state, mark it as derived; preferred v0.1 hardening is API-provided state-at-cursor.
- Compare stays disabled/future unless existing API can be wired without scope growth.

## Execution queue

### Slice 0 — Claude second-brain review

Objective: independent architecture/design review before code surgery.

Ask Claude to review:
- spec vs v1 design
- current `frontend/src/observer.tsx` / `App.tsx` / `styles.css`
- test/API shape
- risks in porting design into production

Expected output:
- acceptance / rejection of slice plan
- top 5 implementation risks
- minimal first patch recommendation
- deployment blockers

Verifier: Claude output saved under `.state/steamer-observer-ui-v0/claude-review.md`.

### Slice 1 — Local implementation: observer shell visual hierarchy

Objective: port v1's operator-console hierarchy into existing React/Vite code without changing backend semantics.

Scope:
- fix observer-only shell/nav labels: Monitor / Replay History / disabled Compare
- strengthen session header hierarchy
- separate live freshness vs replay bundle validity display
- add clear read-only/sanitized/no broker control flags
- keep existing API fetch flow

Verifier:
- `VITE_STEAMER_SURFACE=observer npm --prefix frontend run build`
- grep built bundle for forbidden non-observer API refs
- no backend tests required unless payload typing changes

### Slice 2 — Local implementation: state reconciliation + empty/degraded states

Objective: make orders/fills/position panels truth-first and explicit.

Scope:
- group panels as `State Reconciliation`
- add first-class empty/degraded/stale state blocks with receipt affordance
- never render fake PnL; show unavailable when lane truth is not fresh/truthful
- keep lane status visible in panel headers

Verifier:
- frontend build
- fixture inspection / screenshot if browser lane available
- UI text grep for `State Reconciliation`, `receipt`, `degraded`, `unavailable`

### Slice 3 — Local implementation: chart/timeline/replay UX

Objective: improve operator scan path without frontend truth invention.

Scope:
- timeline cursor readout
- chart marker legend using stable lane colors
- replay frame + scrubber treatment
- selected replay session visibly distinct from live monitor
- keep frontend replay derivation explicitly labeled if retained

Verifier:
- frontend build
- typecheck/build no runtime import errors
- UIUX reviewer pass/conditional pass

### Slice 4 — Receipt drawer trust anchor

Objective: turn receipt drawer into the trust/provenance panel.

Scope:
- bundle identity
- freshness / bundle validity
- lane receipts
- sanitization / authority boundary
- source provenance
- degraded/missing explanations

Verifier:
- frontend build
- leak scan of built assets for account/token/endpoint-like strings
- QA reviewer pass/conditional pass

### Slice 5 — QA + UIUX researcher minions

Run at least two independent reviews after local build passes:

1. QA / safety reviewer:
   - read-only boundary
   - payload leakage / forbidden wording
   - API route assumptions
   - build/test gates

2. UIUX researcher:
   - 10-second operator questions
   - live vs replay confusion
   - degraded/empty visibility
   - cognitive load / hierarchy

Expected output:
- pass / conditional pass / blocker
- exact blockers if any
- top recommended polish items, separated from blockers

### Slice 6 — AWS deployment packet

Deployment is an external mutation gate.

Before deploy:
- local git clean or intentional diff only
- frontend build passes
- backend observer tests pass if touched
- QA/UIUX no blockers
- leakage scan clear
- package patch artifact with commit hash

Deploy only after explicit deploy confirmation if the command mutates AWS state.

Post-deploy smoke:
- HTTP reachable observer page
- `/api/observer/sessions` responds
- observer-only frontend has no forbidden API refs
- no credential/endpoint leakage in served bundle
- screenshot or curl receipt saved

### Slice 7 — WAL / push / ingest closure

Closure bundle:
- commit + push repo changes
- write receipt under `docs/receipts/` or `ops/checkpoints/`
- update design/implementation packet if actual topology differs
- topology statement: changed/unchanged
- docs-memory ingest if docs changed and relevant
- ledger/WAL summary if deployment/runtime truth changed

## Stop-loss

Stop and report if:
- current observer frontend shape blocks safe incremental port after 2 meaningful attempts
- v1 design requires schema/backend changes larger than this UI slice
- QA finds possible browser-visible secret/account/routing/endpoint leakage
- deployment requires unknown AWS/auth/topology decision
- same build/runtime error repeats after 2 attempts

## Recommended first implementation move

Start with Slice 0 + Slice 1. Do not touch AWS until local observer shell is build-clean and reviewed.
