# 2026-04-09 — 五氣朝元 closure for dashboard active-family baton line

## Verdict

Closure level: **Level 1**.

- repo truth changed
- topology did **not** change
- no new authority plane was added
- the baton line remains a read-only support surface inside the existing `Steamer Dashboard`

## Canonical authority after the sweep

For this line, the current authoritative surfaces are:

1. `AGENTS.md`
2. `docs/SETUP.md`
3. `docs/TOPOLOGY.md`
4. `docs/tech-notes/2026-04-09_steamer_dashboard_tabbed_strategy_powerhouse_surface.md`
5. `docs/tech-notes/2026-04-09_steamer_strategy_powerhouse_history_browser.md`
6. `ops/sprints/steamer-card-engine-mission-control-dashboard-v0-sprint.md`

They now agree on the same bounded truth:

- the browser surface is the broader read-only **Steamer Dashboard**
- `Live Sim` remains the execution-truth tab
- `Strategy Powerhouse / Strategy Cards` remains a local-artifact research/control support tab
- the new active-family baton line is read-only only
- `steamer-card-engine` remains the execution surface
- `strategy-powerhouse` does not gain runtime or governance authority

## Five-surface stale-rule retirement sweep

### 1) `AGENTS.md`

Scanned both authority layers:

- workspace `/root/.openclaw/workspace/AGENTS.md` -> already aligned; no baton-line conflict found
- repo `AGENTS.md` -> stale underclaim found and retired

Retired stale wording in repo `AGENTS.md`:

- old rule-surface implication: repo reliable surface was only manifests + CLI
- new truthful wording: repo reliable surface now also includes the read-only dashboard/API, while execution authority remains partial/placeholder and non-mutating

Result: **workspace AGENTS unchanged; repo AGENTS updated in place**.

### 2) `MEMORY.md`

Scanned for conflicting durable rule.

Result: **no conflicting older rule found**.

- workspace `MEMORY.md` already aligned on WAL closure, topology checks, rule-surface hygiene, and `五氣朝元`
- no Steamer-specific authority line there contradicted the new baton-line truth

### 3) Most relevant spec / canon / operator doc

Retired stale operator wording in `docs/SETUP.md`:

- old wording centered only on a `Mission Control dashboard demo`
- new wording now names the broader `Steamer Dashboard`, its two tabs, and the read-only baton-line boundary

Result: **updated in place**.

### 4) Tracked ledger decision / authority docs

Scanned relevant tracked authority surfaces:

- `/root/.openclaw/workspace/lyria-working-ledger/DECISIONS/2026-04-09.md`
- `/root/.openclaw/workspace/lyria-working-ledger/HANDOFFS/2026-04-07_steamer-mission-control-dashboard_checkpoint.md`
- `/root/.openclaw/workspace/lyria-working-ledger/NOTES/steamer/2026-04-08_steamer-card-engine_session-phase-implementation-executive-summary.md`

Result:

- `DECISIONS/2026-04-09.md` is **still aligned** and remains authoritative for the boundary split: `steamer-card-engine` execution surface, `strategy-powerhouse` support only
- the 2026-04-07 handoff and 2026-04-08 executive summary are **historical receipts only**, not current authority surfaces for the dashboard baton-line shape
- no ledger decision rewrite was needed for truthful closure

### 5) Graph / doc-memory surfaces

Completed:

- docs cold-lane ingest run against the updated repo authority surfaces
  - result: `files=7`, `batches=1`, `changed=46`
- memory receipt written to:
  - `/root/.openclaw/workspace/memory/2026-04-09.md`

Advisory note:

- direct `memory_store` write for this closure was held by Wei Ji preflight policy, so the durable receipt for this pass is the markdown memory note plus docs-ingest receipt

Historical doc-memory note:

- earlier checkpoint / execution-packet surfaces may still mention prior recommended next moves; they should be read as **history**, not as current authority, once this closure receipt exists

## Historical receipts explicitly treated as non-authoritative

These remain useful receipts, but are **not** the current authority surface for the baton-line contract:

- `docs/tech-notes/2026-04-06_steamer_card_engine_mission-control_dashboard_v0_build-packet.md`
- `ops/execution-packets/2026-04-09_queued-next-blade_dashboard_recent-days_gap.packet.md`
- `/root/.openclaw/workspace/lyria-working-ledger/HANDOFFS/2026-04-07_steamer-mission-control-dashboard_checkpoint.md`
- `/root/.openclaw/workspace/lyria-working-ledger/NOTES/steamer/2026-04-08_steamer-card-engine_session-phase-implementation-executive-summary.md`

They remain valid as chronology / receipts, but current dashboard authority should now be read from the canonical surfaces listed above.

## What was retired vs what remains

### Retired in place

- repo `AGENTS.md` underclaim that the reliable surface was only manifests + CLI
- `docs/SETUP.md` operator wording that still presented the dashboard only as the earlier Mission Control demo shape

### Confirmed aligned, no edit needed

- workspace `MEMORY.md`
- `lyria-working-ledger/DECISIONS/2026-04-09.md`
- `docs/TOPOLOGY.md`
- 2026-04-09 strategy dashboard / history-browser tech notes
- mission-control dashboard sprint journal

### Remains historical only

- 2026-04-06 build packet
- 2026-04-07 checkpoint handoff
- 2026-04-08 private executive summary
- 2026-04-09 queued-next-blade diagnostic packet

## WAL closure receipts

- baton-line implementation commit already pushed: `aa937a5653b3101e2e438700312016c5a32973ef`
- docs cold-lane ingest receipt: `files=7`, `batches=1`, `changed=46`
- memory receipt: `/root/.openclaw/workspace/memory/2026-04-09.md`
- topology statement: **unchanged**

## Remaining limit

This closes stale-rule retirement for the current baton-line slice.

It does **not** promote strategy-powerhouse into an execution/control plane.
Any future same-day change breadcrumb or richer handoff surface must preserve the same explicit no-authority boundary.
