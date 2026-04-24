# Evidence Provenance Envelope Spec

Status: contract draft, docs-first, remote-safe.
Scope: Steamer evidence archives, replay/live-sim reports, and aggregate MarketDataHub introspection.

This spec defines the first Fincept absorption item as a Steamer-native contract. It does **not** implement broker behavior, live runtime authority, or raw-data export.

## Purpose

The evidence provenance envelope answers four questions without exposing strategy-private material:

1. Which local evidence source or report was summarized?
2. Which parser/schema produced this summary?
3. How much aggregate material was observed?
4. Why did coverage pass, fail, or stay low?

The envelope is for receipts, reports, and operator review. It is intentionally aggregate-only.

## Privacy boundary

The envelope must never contain:

- raw symbols or instrument identifiers
- account numbers, user identifiers, broker identifiers, or credential material
- raw card parameters, strategy thresholds, feature values, or private config payloads
- raw orders, trades, fills, positions, broker events, or market events
- raw event excerpts, log excerpts, stack traces with private values, or unredacted error payloads
- absolute local paths, host-private directory names, or archive member paths
- subscriber identities, card instance names, or per-symbol routing tables

Allowed references are sanitized pointers only, such as opaque source ids, archive hashes, parser versions, and aggregate counts.

## Envelope shape

Recommended filename when emitted beside a report:

```text
evidence-provenance-envelope.json
```

Minimum JSON shape:

```json
{
  "schema_version": "evidence-provenance-envelope/v1",
  "generated_at_utc": "<ISO-8601 UTC>",
  "source": {
    "source_kind": "<local-archive|report|run-artifact>",
    "source_host_alias": "<opaque-host-alias>",
    "source_date": "<YYYY-MM-DD>",
    "source_id": "<opaque-source-id>",
    "archive_sha256": "<sha256-or-null>",
    "report_sha256": "<sha256-or-null>"
  },
  "parser": {
    "parser_name": "<parser-name>",
    "parser_version": "<semver-or-git-sha>",
    "schema_version": "<input-schema-version>",
    "ruleset_id": "<opaque-ruleset-id-or-null>"
  },
  "scope": {
    "run_type": "<replay-sim|live-sim|local-evidence>",
    "session_date": "<YYYY-MM-DD-or-null>",
    "scenario_id_hash": "<hash-or-null>",
    "time_range_utc": {
      "start": "<ISO-8601 UTC-or-null>",
      "end": "<ISO-8601 UTC-or-null>"
    }
  },
  "aggregate_counts": {
    "rows_total": 0,
    "events_total": 0,
    "feature_records_total": 0,
    "intents_total": 0,
    "risk_decisions_total": 0,
    "execution_requests_total": 0,
    "order_lifecycle_events_total": 0,
    "fills_total": 0,
    "positions_total": 0,
    "anomalies_total": 0
  },
  "reason_counts": {
    "no_trades": 0,
    "warmup_not_ready": 0,
    "insufficient_bars": 0,
    "other_reject": 0,
    "pass": 0,
    "unknown": 0,
    "error": 0
  },
  "market_data_hub_stats": {
    "schema_version": "market-data-hub-stats/v1",
    "snapshot_at_utc": "<ISO-8601 UTC>",
    "connection_state": "<unknown|disconnected|connecting|connected|degraded|replaying>",
    "subscription_count": 0,
    "subscriber_count": 0,
    "event_count": 0,
    "last_event_at_utc": "<ISO-8601 UTC-or-null>",
    "last_event_lag_ms": null,
    "stale": false,
    "stale_reason": null,
    "error_count": 0,
    "last_error_class": null,
    "replay_live_parity": {
      "contract_version": "<contract-version-or-null>",
      "event_shape_match": null,
      "feature_shape_match": null,
      "notes": []
    }
  },
  "verifier": {
    "aggregate_only": true,
    "banned_fields_absent": true,
    "path_sanitized": true,
    "raw_excerpt_absent": true
  }
}
```

Fields may be omitted only when a narrower artifact type explicitly cannot know them. Unknown values should prefer `null`, `0`, or `"unknown"` over private detail.

## Sanitized field rules

- `source_host_alias`: opaque label only. Do not use hostnames that reveal accounts, projects, or local directory structure.
- `source_id`: deterministic opaque id or hash. Do not embed paths, symbols, or account names.
- `archive_sha256` / `report_sha256`: hash the whole source/report artifact, not individual private records.
- `scenario_id_hash`: hash or opaque id only when the scenario id may reveal private strategy context.
- `rows_total` and related counts: counts only, no grouped-by-symbol/account/card breakdowns.
- `last_error_class`: bounded class name only, such as `parse_error`, `stale_source`, or `schema_mismatch`. Do not include raw exception messages when they may contain private values.
- `notes`: verifier-safe text only. Prefer placeholders and receipt ids over quoted source lines.

## Bounded reason taxonomy

`reason_counts` is the canonical aggregate reason bucket for zero/low coverage explanations.

| Reason | Meaning | Privacy posture |
|---|---|---|
| `no_trades` | No fill/trade-level evidence was present or eligible for the measured scope. | Count only; do not list instruments or orders. |
| `warmup_not_ready` | Feature/session warmup prevented evaluation or action. | Count only; do not expose warmup thresholds. |
| `insufficient_bars` | Source history/window length was insufficient. | Count only; do not expose bar windows or private feature params. |
| `other_reject` | A known policy or parser rejection outside the named buckets. | Count only; optional bounded class may live in anomalies, not raw detail. |
| `pass` | Evidence met the measured gate or an item passed filtering. | Count only. |
| `unknown` | The parser could not classify the reason safely. | Use instead of leaking source detail. |
| `error` | The parser/verifier failed before safe classification. | Use with bounded error class, not raw stack traces. |

New reason values require a docs update and verifier update. Do not create ad hoc per-strategy reasons in emitted envelopes.

## MarketDataHub stats/introspection contract

MarketDataHub introspection is read-only and aggregate-only. It is meant for receipts and operator health checks, not for reconstructing raw market data or subscriber routing.

Minimum `market-data-hub-stats/v1` fields:

- `snapshot_at_utc`
- `connection_state`: `unknown`, `disconnected`, `connecting`, `connected`, `degraded`, or `replaying`
- `subscription_count`: number of active requested market subscriptions
- `subscriber_count`: number of downstream consumers, without identities
- `event_count`: total normalized events observed in this process/run/scope
- `last_event_at_utc`: timestamp only, nullable
- `last_event_lag_ms`: aggregate lag only, nullable
- `stale`: boolean
- `stale_reason`: bounded reason, nullable
- `error_count`: count only
- `last_error_class`: bounded class only, nullable
- `replay_live_parity`: nullable or aggregate booleans for contract-shape parity checks

Forbidden in MarketDataHub stats:

- symbols, account ids, card ids, subscriber ids, or callback names
- raw event payloads
- per-symbol event counts
- connection URLs, broker credentials, or raw vendor error payloads

Runtime maturity note: this is a contract target. Existing seed runtime components may expose only a tiny inert subset until native MarketDataHub implementation matures.

## Placeholder-only examples

### Low-coverage local evidence summary

```json
{
  "schema_version": "evidence-provenance-envelope/v1",
  "generated_at_utc": "<ISO-8601 UTC>",
  "source": {
    "source_kind": "local-archive",
    "source_host_alias": "<host-alias>",
    "source_date": "<YYYY-MM-DD>",
    "source_id": "<opaque-source-id>",
    "archive_sha256": "<sha256>",
    "report_sha256": null
  },
  "parser": {
    "parser_name": "<parser-name>",
    "parser_version": "<parser-version>",
    "schema_version": "<input-schema-version>",
    "ruleset_id": "<ruleset-id>"
  },
  "aggregate_counts": {
    "rows_total": 0,
    "events_total": 0,
    "feature_records_total": 0,
    "intents_total": 0,
    "risk_decisions_total": 0,
    "execution_requests_total": 0,
    "order_lifecycle_events_total": 0,
    "fills_total": 0,
    "positions_total": 0,
    "anomalies_total": 0
  },
  "reason_counts": {
    "no_trades": 1,
    "warmup_not_ready": 0,
    "insufficient_bars": 0,
    "other_reject": 0,
    "pass": 0,
    "unknown": 0,
    "error": 0
  },
  "verifier": {
    "aggregate_only": true,
    "banned_fields_absent": true,
    "path_sanitized": true,
    "raw_excerpt_absent": true
  }
}
```

### MarketDataHub stats snapshot

```json
{
  "schema_version": "market-data-hub-stats/v1",
  "snapshot_at_utc": "<ISO-8601 UTC>",
  "connection_state": "replaying",
  "subscription_count": 0,
  "subscriber_count": 0,
  "event_count": 0,
  "last_event_at_utc": null,
  "last_event_lag_ms": null,
  "stale": false,
  "stale_reason": null,
  "error_count": 0,
  "last_error_class": null,
  "replay_live_parity": {
    "contract_version": "<contract-version>",
    "event_shape_match": true,
    "feature_shape_match": true,
    "notes": []
  }
}
```

## Verifier checklist

A provenance envelope is acceptable only if:

1. `schema_version` is present and recognized.
2. Source pointers are opaque or hashed; no absolute paths or archive member paths are present.
3. Banned privacy fields are absent: raw symbols, accounts, params, orders/trades, fills, positions, raw events, raw excerpts, credentials, and subscriber identities.
4. `reason_counts` contains only the bounded taxonomy above.
5. Zero/low coverage can be explained by aggregate counts and reason counts.
6. MarketDataHub stats expose counts, timestamps, stale/error summaries, and parity booleans only.
7. Any error disclosure is bounded to a class/category, not a raw exception or source line.
8. Placeholder examples in docs remain placeholders and never use real local evidence.

## Related contracts

- Fincept absorption ROI map: `docs/FINCEPT_ABSORPTION_ROI.md`
- Architecture: `docs/ARCHITECTURE.md`
- SIM artifact contract: `docs/SIM_ARTIFACT_SPEC.md`
- Topology: `docs/TOPOLOGY.md`
