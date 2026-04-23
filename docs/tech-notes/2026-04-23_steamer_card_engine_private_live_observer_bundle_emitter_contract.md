# 2026-04-23 — steamer-card-engine private live observer bundle emitter contract

## Verdict

Now that the public-safe repo owns an attachment seam, the next honest move is a **private bundle emitter** that writes sanitized observer session bundles onto a private runtime path and lets the repo-side observer API mount them via `STEAMER_OBSERVER_BUNDLE_JSON`.

Do not put the private field mapping into this repo.
Do not make the browser or projection service discover runtime truth directly.

## Producer / consumer split

### Private emitter owns
- reading real runtime/session/probe surfaces
- field mapping from engine-grade/runtime-grade truth into sanitized observer events
- writing bundle JSON to a private filesystem path
- rotating/replacing the bundle atomically

### Public-safe repo owns
- bundle ingestion
- deterministic bootstrap rebuild
- read-only API serving
- browser presentation

## First recommended upstream source

For the first truthful activation slice, prefer a **single-source session health lane plus one event lane** instead of trying to solve all runtime plumbing at once.

Recommended order:
1. canonical session/probe truth from `operator probe-session` or session-manager equivalent
2. sanitized market/candle lane for one active symbol
3. sanitized order/fill/position lane
4. operator-visible notes / incidents

That lets the first private emitter stand up in layers:
- v0a: session + health + candles
- v0b: add order/fill/position
- v0c: add operator-visible notes and degraded/gap incidents

## Bundle path contract

The emitter should write one JSON file per observer session, for example:

```text
/root/.openclaw/workspace/.state/steamer/observer/private/aws-live-sim-2330.json
```

The observer API mount then becomes:

```text
STEAMER_OBSERVER_BUNDLE_JSON=/root/.openclaw/workspace/.state/steamer/observer/private/aws-live-sim-2330.json
STEAMER_OBSERVER_INCLUDE_MOCK=0
```

## Bundle JSON contract

Minimum required shape:

```json
{
  "metadata": {
    "session_id": "aws-live-sim-2330",
    "engine_id": "steamer-card-engine.live-sim",
    "session_label": "AWS live(sim) 2330 observer",
    "market_mode": "live(sim)",
    "symbol": "2330.TW",
    "timeframe": "1m"
  },
  "events": []
}
```

Optional fields:
- `candles`
- `bootstrap`

Guidance:
- prefer emitting `metadata + events` only at first
- let the public-safe bridge rebuild `bootstrap`
- include `candles` only if it reduces emitter complexity without creating a second truth source
- include `bootstrap` only if the private runtime already materializes it from the same event stream

## Event requirements

Every event must satisfy the public observer contract:
- monotonic `seq`
- stable `event_id`
- explicit `event_time` and `ingest_time`
- presentation-safe `partial_data`
- explicit `freshness_state`

The private emitter must never leak:
- account identifiers
- broker routing identifiers
- raw broker/order objects
- internal URLs/hosts/VPC shape
- alpha-bearing strategy internals
- hidden future-control fields

## First truthful event family target

Required for the first real browser proof:
- `session_started`
- `engine_state_changed`
- `health_alert`
- `candle_bar`

Next layer:
- `order_submitted`
- `order_acknowledged`
- `fill_received`
- `position_updated`

Optional but useful:
- `operator_visible_note`
- `data_gap_detected`
- `session_ended`

## Atomic write rule

The emitter should write bundles atomically:
1. write to `*.tmp`
2. fsync if needed
3. rename into place

The observer API should only ever see a full prior bundle or a full next bundle, never a partial write.

## Freshness rule

The emitter owns truthful freshness classification.
The browser must never infer health only from absence of traffic.

Minimum mapping:
- `fresh`
- `lagging`
- `degraded`
- `stale`

If the upstream source only exposes heartbeat age, classify freshness in the emitter and record the coarse reason in a presentation-safe incident string.

## Stop-loss

Stop and report if any of these appears:
- the emitter needs raw engine/broker objects in browser payloads to keep moving
- the bundle wants to double as a write/control path
- multiple conflicting truth sources try to own candles or position simultaneously
- the first slice expands to multi-session orchestration before one session is proven cleanly

## Activation proof target

The first private emitter slice is done only if:
1. one private bundle file mounts cleanly through `STEAMER_OBSERVER_BUNDLE_JSON`
2. `/api/observer/sessions` shows only the attached session when mock is disabled
3. bootstrap, candles, timeline, and stream all reconcile to the same event sequence
4. payload review shows no sensitive field leakage
5. reconnect rebuilds without duplicate drift

## Topology statement

Topology unchanged.
This contract adds a private producer lane feeding the existing read-only observer sidecar boundary.
