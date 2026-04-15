# 2026-04-16 — steamer-card-engine probe JSON inlet

## Why this slice landed

The broker-preflight contract skeleton was in place, but the CLI still only knew how to emit seed `not-connected` health.
That meant later real probing would still need to touch the CLI internals too early.

## What is now executable

- `auth inspect-session --probe-json <snapshot.json>`
- `operator preflight-smoke --probe-json <snapshot.json>`

The snapshot is an external JSON object that can override the seed `session_status + connections` health surface.
This keeps the probe lane decoupled from the CLI lane:
- probe gathers vendor/runtime truth
- CLI consumes the normalized snapshot

## Why this matters

This is the first true bridge from seed contract to real probe integration.
A later broker/session-manager probe can write the canonical snapshot shape, and the existing session/preflight surfaces can immediately use it without command-shape changes.

## Current boundary

- fixture/example probes are allowed
- vendor SDK login/attach is still not implemented inside this repo slice
- prepared-only remains explicit

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: no
- CLI contract changed: yes
