# Execution packet — observer-first AWS activation gate

## Mission

Redeploy the observer-first monitor bundle to the existing AWS demo host only after local closure, and prove one browser-openable read-only observer session without widening execution authority.

## Preconditions

- Local observer-first monitor closure checkpoint exists:
  - `ops/checkpoints/2026-04-24_observer-first-monitor-local-closure-checkpoint.md`
- Local verifiers pass:
  - targeted pytest
  - ruff
  - default frontend build
  - `VITE_STEAMER_SURFACE=observer` frontend build
- AWS access uses explicit profile:
  - `AWS_PROFILE=lyria-trading-ops`
- No auth/security boundary change is made silently.

## Activation steps

1. Build observer-only frontend bundle:

```bash
VITE_STEAMER_SURFACE=observer npm --prefix frontend run build
```

2. Package only the required runtime/frontend artifacts for the read-only observer deployment path.

3. Upload to the existing staging bucket / demo instance path used by the prior observer demo bring-up.

4. Start or reload only the observer/dashboard read-only service on the demo host.

5. Mount a sanitized observer bundle via:

```text
STEAMER_OBSERVER_BUNDLE_JSON=<private-or-demo-sanitized-bundle-json>
STEAMER_OBSERVER_INCLUDE_MOCK=0
```

6. Browser proof:

- remote page opens
- page title/shell is observer-first, not legacy Mission Control tab shell
- no unrelated strategy/live-sim panels are visible
- session bootstrap loads
- chart / position / orders / fills / health / timeline render
- websocket state is visible
- refresh/reconnect works
- stale/degraded/closed states are visible if induced or present

7. Payload review:

- inspect browser-visible `/api/observer/...` payloads
- confirm no account IDs, broker routing IDs, raw broker objects, internal hosts/URLs/VPC/subnet names, credentials/tokens, or strategy internals

8. Kill switch proof:

- document the command/service/env change that disables observer exposure without touching the trading engine path

## Stop gates

Stop before activation if:

- deployment requires opening new public ports or broadening security groups
- deployment requires auth/permission changes not explicitly approved
- observer bundle requires raw private/broker payloads to render
- hosted surface still serves the full legacy Mission Control shell instead of observer-only mode
- mock session cannot be disabled for the proof

## Acceptance receipt

Write checkpoint after activation attempt:

- `ops/checkpoints/2026-04-24_observer-first-aws-activation-checkpoint.md`

Include:

- instance / URL / staged bundle receipts, redacted if needed
- env vars used, without secrets
- browser proof status
- payload review status
- reconnect status
- kill switch path
- topology statement
- blocker list, if any

## Topology statement

This packet permits a demo deployment/reload of the read-only observer surface only. It does not authorize live execution authority, broker control wiring, public access widening, or durable runtime topology changes.
