# 2026-04-23 — steamer-card-engine observer launch enablement and remote security hardening

## Verdict

The next honest goal is **not** wider UI polish.
The next honest goal is **remote-safe enablement** of one real live(sim) observer session behind a hardened read-only boundary.

If we want this line to reach actual browser-openable activation, the next sequence should be:
1. private live adapter
2. read-only projection service hardening
3. auth and network boundary hardening
4. one real session activation proof

## Next step recommendation (goal: enablement)

### Phase 1 — private adapter bridge
Build the first **private-only** adapter that converts one real live(sim) engine session into the sanitized observer schema already used by the mock slice.

Deliverables:
- one private adapter module, not committed to the public repo if it contains sensitive field mapping
- append-only observer event emitter
- latest-state projection materializer for bootstrap rebuild
- explicit seq allocator / monotonic ordering contract

Done means:
- one real session can emit sanitized bootstrap + stream payloads matching the v0 observer contract
- no engine-grade/raw broker payload reaches browser-facing surfaces

### Phase 2 — read-only projection service hardening
Take the current mock observer API shape and harden it for real remote use.

Deliverables:
- explicit session lookup/allowlist
- reconnect-safe bootstrap + stream rebuild path
- bounded timeline / incident retention
- heartbeat / freshness monitor for stale and degraded state
- server-side request limits (`limit` clamping, session fanout limits, websocket connection caps)

Done means:
- refresh/reconnect rebuilds the same state truthfully
- stale/degraded states surface deterministically
- one observer client cannot request unbounded history or open unbounded sockets

### Phase 3 — remote access security hardening
Before public or semi-public browser access, freeze the remote boundary.

Deliverables:
- auth in front of the observer route (OIDC/SSO or equivalent)
- TLS everywhere
- strict origin allowlist, no wildcard CORS
- reverse-proxy or gateway policy that exposes **observer-only** routes
- rate limiting and connection limiting
- separate deploy/service identity from the trading engine path
- kill switch that disables observer exposure without touching the engine
- secrets only in private runtime/env, never in public repo or browser bundle

Done means:
- remote browser access is possible only through authenticated, encrypted, bounded, read-only entry points
- there is no network path from browser to engine control/broker surfaces

### Phase 4 — one activation proof
Run one real AWS live(sim) observer session end-to-end and collect receipts.

Required proof:
- browser opens remotely
- one authenticated user can see chart + timeline + orders/fills + health
- reconnect works without duplicate drift
- payload review confirms no internal strategy/broker/infra leakage
- observer can be disabled independently

## Remote connection security hardening checklist

### Network and service boundary
- observer service must be **separate** from execution/broker services
- private adapter should sit on a private subnet/non-public path
- browser-visible service should expose only sanitized read-only projection routes
- no shared write-capable route namespace with execution control
- no direct browser access to engine DB/cache/broker/session stores

### Authentication and session security
- require real auth (OIDC/SSO or equivalent), not obscurity URLs
- use short-lived sessions/tokens
- bind authorization to a narrow operator allowlist/group
- log observer access separately from engine execution logs
- revoke observer access without disturbing the engine

### Transport security
- TLS mandatory end-to-end where traffic leaves the host boundary
- strict CORS allowlist
- websocket origin checks
- rate limiting for HTTP and websocket connections
- idle timeout / maximum connection lifetime for websocket sessions

### Data sanitization
- no raw broker/order objects
- no account IDs, routing IDs, credentials, hostnames, subnet names, or internal URLs
- no strategy thresholds, feature weights, private score bands, or explainability dumps
- only presentation-grade state in browser payloads
- screenshots/fixtures used outside private runtime must remain synthetic or explicitly scrubbed

### Operational safety
- observer kill switch separate from trading engine
- explicit stale/degraded banners, never silent lag
- payload audit before widening beyond one session
- activation receipt must name whether the lane is prepared-only or truly activated

## Topology statement

Topology unchanged.
This is an enablement/hardening sequence for the observer sidecar boundary, not a change to Steamer execution authority.
