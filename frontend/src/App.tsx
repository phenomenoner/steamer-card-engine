import { startTransition, useEffect, useMemo, useState } from "react";

type DashboardTab = "live-sim" | "strategy-powerhouse" | "strategy-pipeline";

type DateItem = {
  date: string;
  hero: boolean;
  compare_status: string;
  scenario_id: string;
  comparison_dir: string;
  dominant_lane: string;
  dominant_card: string | null;
  anomaly_count: number;
  transaction_state: string;
  symbol_count?: number | null;
  calendar?: string | null;
  timezone?: string | null;
  candidate_deck_id?: string | null;
  baseline_deck_id?: string | null;
};

type CardSummary = {
  id: string;
  card_id: string;
  card_version: string;
  deck_id: string;
  lane: string;
  intent_count: number;
  signal_intent_count: number;
  entry_intent_count: number;
  allowed_risk_count: number;
  blocked_risk_count: number;
  execution_request_count: number;
  feature_record_count: number;
  top_symbols: Array<{ label: string; count: number }>;
  sides: Array<{ label: string; count: number }>;
  reason_distribution: Array<{ label: string; count: number }>;
  risk_reason_distribution: Array<{ label: string; count: number }>;
  anomaly_refs: string[];
};

type CompareData = {
  status: string;
  compare_version: string;
  comparison_relpath: string;
  hard_fail_reasons: string[];
  counts: Record<string, Record<string, number>>;
  anomalies: Record<string, Record<string, number>>;
  pnl_reported: Record<string, Record<string, number>>;
  scaffold_placeholders: Record<string, string>;
};

type TimelineEvent = {
  event_key: string;
  timestamp: string;
  lane: string;
  kind: string;
  title: string;
  subtitle: string;
  symbol: string | null;
  card_id?: string | null;
  intent_id?: string | null;
  status: string;
  details: Record<string, unknown>;
};

type TransactionsData = {
  counts: Record<string, Record<string, number>>;
  pnl_reported: Record<string, Record<string, number>>;
  lanes: Record<
    string,
    {
      counts: Record<string, number>;
      pnl_summary: Record<string, number | string | Record<string, number>>;
      empty_state: {
        is_empty: boolean;
        empty_reason: string;
        truth_note: string;
      };
    }
  >;
  empty_state_metadata: {
    state: string;
    empty_reason: string;
    truth_note: string;
  };
};

type DeckView = {
  date: string;
  fixture: {
    comparison_relpath: string;
    baseline_bundle_relpath: string;
    candidate_bundle_relpath: string;
  };
  cover: {
    date: string;
    scenario_id: string;
    compare_status: string;
    dominant_lane: string;
    dominant_card: string | null;
    dominant_card_label: string | null;
    anomaly_total: number;
    transaction_state: string;
    delta_counts: Record<string, { baseline: number; candidate: number; delta: number }>;
    scaffold_placeholders: string[];
    compare_notes: string[];
  };
  universe: {
    scenario_id: string | null;
    calendar: string | null;
    timezone: string | null;
    session: {
      session_date: string | null;
      slice_label: string | null;
      start_local: string | null;
      end_local: string | null;
    };
    event_source: {
      source_kind: string | null;
      source_id: string | null;
      time_range_utc: { start: string; end: string } | null;
    };
    determinism: Record<string, unknown>;
    symbol_set: {
      symbol_set_id: string | null;
      mode: string | null;
    };
    symbol_count: number;
    symbol_samples: string[];
  };
  strategy: {
    dominant_lane: string;
    dominant_card: string | null;
    lanes: Record<
      string,
      {
        deck_id: string | null;
        deck_version: string | null;
        config_hash: string | null;
        cards: Array<{ card_id: string; card_version: string }>;
        card_count: number;
      }
    >;
    cards: CardSummary[];
  };
  compare: CompareData;
  evidence: {
    anomalies: Array<{
      anomaly_id: string;
      category: string;
      detected_at_utc: string;
      message: string;
      severity: string;
      lane: string;
    }>;
    timeline: TimelineEvent[];
    phase_truth_summary: {
      baseline: {
        execution_phase_counts: Record<string, number>;
        contract_violation_count: number;
        phase_classifier: string;
        open_discovery_summary?: {
          saw_trial_match_event?: boolean;
          saw_official_open_signal?: boolean;
          first_trial_match_utc?: string | null;
          first_official_open_signal_utc?: string | null;
        } | null;
      };
      candidate: {
        execution_phase_counts: Record<string, number>;
        contract_violation_count: number;
        phase_classifier: string;
        open_discovery_summary?: {
          saw_trial_match_event?: boolean;
          saw_official_open_signal?: boolean;
          first_trial_match_utc?: string | null;
          first_official_open_signal_utc?: string | null;
        } | null;
      };
    };
    comparison_summary_markdown: string;
    comparison_summary_relpath: string;
  };
  transactions: TransactionsData;
  snapshots_available: string[];
};

type CardDetail = {
  date: string;
  lane: string;
  card_id: string;
  card_version: string;
  deck_id: string | null;
  deck_version: string | null;
  config_hash: string | null;
  scenario_id: string | null;
  run_id: string | null;
  bundle_relpath: string;
  anomaly_refs: Array<string | null>;
  counts: {
    intents: number;
    risk_decisions: number;
    risk_allow: number;
    risk_block: number;
    execution_requests: number;
    feature_records: number;
  };
  distributions: {
    top_symbols: Array<{ label: string; count: number }>;
    sides: Array<{ label: string; count: number }>;
    intent_reasons: Array<{ label: string; count: number }>;
    risk_reasons: Array<{ label: string; count: number }>;
  };
  samples: {
    intents: Array<Record<string, unknown>>;
    risk_decisions: Array<Record<string, unknown>>;
    execution_requests: Array<Record<string, unknown>>;
    feature_provenance: Array<Record<string, unknown>>;
  };
  truth_notes: string[];
};

type StrategyLink = {
  label: string;
  kind: string;
  path: string;
};

type StrategyHistoryEntry = {
  event_id: string;
  timestamp: string | null;
  kind: string;
  title: string;
  summary: string;
  status: string | null;
  path: string;
  source_kind: string;
};

type StrategyPlanTarget = {
  variant_id: string;
  deck_id: string | null;
  deck_path: string | null;
  deck_manifest_present: boolean;
};
type RuntimeSelectionCandidate = {
  campaignId: string;
  priority?: number | null;
  phase?: string | null;
  status?: string | null;
  dispatchable?: boolean;
};


type StrategyPipelineStage = {
  stage_id: string;
  label: string;
  role: string;
  current_surface: string;
  status: string;
  summary: string;
  latest_receipt: string | null;
  blocking_note: string | null;
};

type StrategyGlossaryItem = {
  term: string;
  zh: string;
  plain: string;
  role: string;
};

type StrategyFocusLine = {
  line_id: string;
  title: string;
  status: string;
  family: string | null;
  variant: string | null;
  summary: string;
  next_gate: string;
  topology_changed: boolean;
  receipts: Array<{
    label: string;
    kind: string;
    path: string;
    timestamp: string | null;
  }>;
};

type StrategyPowerhouseCard = {
  candidate_id: string;
  family_id: string;
  display_name: string;
  card_id: string;
  deck_id: string;
  status: string;
  validation_status: string;
  current_gate: string | null;
  next_gate: string | null;
  handoff_state: string;
  handoff_readiness: string;
  proposal_state: string;
  proposal_priority: string;
  notes: string;
  proof_note: string;
  selected_parameter_summary: Array<{ label: string; value: unknown }>;
  symbol_pool: string[];
  feature_requirements: string[];
  latest_packet: StrategyHistoryEntry | null;
  verifier_history: StrategyHistoryEntry[];
  family_timeline: StrategyHistoryEntry[];
  related_links: StrategyLink[];
};

type StrategyPowerhouseView = {
  updated_at: string | null;
  topology_changed: boolean;
  boundary: {
    note: string;
    execution_authority: string;
    governance_mutation: boolean;
    primary_execution_surface: string;
    strategy_powerhouse_role: string;
  };
  baton_line: {
    today: string | null;
    read_only_note: string;
    breadcrumb: {
      state: string;
      note: string;
      last_active_change_at: string | null;
      last_active_change_source: string | null;
      last_baton_source: {
        state: string;
        label: string;
        path: string | null;
        changed_at: string | null;
        from_family: string | null;
        to_family: string | null;
        forcing_evidence: string | null;
        summary: string | null;
      };
      change_summary: string;
      divergence_freshness: {
        state: string;
        reference_at: string | null;
        age_hours: number | null;
        note: string;
      };
    };
    activation: {
      plan_state: string;
      plan_note: string;
      latest_pointer_present: boolean;
      latest: {
        activation_state: string | null;
        activated_at: string | null;
        changed: boolean | null;
        receipt: string | null;
        effective_scope: string | null;
        effective_run_day: string | null;
        note: string | null;
      } | null;
    };
    active: {
      truth_state: string;
      family: string | null;
      prepared_at: string | null;
      source_packet: string | null;
      targets: StrategyPlanTarget[];
      target_labels: string[];
      attachment_summary: string;
    };
    proposal: {
      family: string | null;
      prepared_at: string | null;
      source_packet: string;
      targets: StrategyPlanTarget[];
      target_labels: string[];
    };
    handoff_readiness: {
      state: string;
      summary: string;
    };
    divergence: {
      state: string;
      family_differs: boolean;
      target_differs: boolean;
      note: string;
    };
  };
  proposal: {
    proposal_family: string | null;
    proposal_prepared_at: string | null;
    proposal_state: string;
    source_packet: string;
    truthful_boundary: string;
    active_family: string | null;
    active_plan_source: string | null;
  };
  architecture_map: {
    note: string;
    stages: StrategyPipelineStage[];
  };
  glossary: StrategyGlossaryItem[];
  focus_lines: StrategyFocusLine[];
  metrics: {
    card_count: number;
    ready_count: number;
    hold_count: number;
    synthetic_proven_count: number;
    history_event_count: number;
    verifier_receipt_count: number;
  };
  sources: StrategyLink[];
  cards: StrategyPowerhouseCard[];
};

type StrategyPipelineView = {
  updated_at: string | null;
  topology_changed: boolean;
  summary: {
    headline: string;
    current_state: string;
    verdict: string;
    note: string;
  };
  line_state: {
    line_id: string;
    title: string;
    family_id: string;
    variant_id: string;
    verifier_id: string;
    run_state: string;
    verdict: string | null;
    blocking_reason: string | null;
    handoff_ready: boolean;
    live_sim_attach_state: string;
    state_path: string | null;
  };
  canon_flow: Array<{
    stage_id: string;
    label: string;
    state: string;
    summary: string;
    receipt: string | null;
  }>;
  components: Array<{
    component_id: string;
    label: string;
    role: string;
    current_surface: string;
    status: string;
    source_paths: Array<string | null>;
    note: string;
  }>;
  autonomous_drivers: Array<{
    driver_id: string;
    label: string;
    role: string;
    state: string;
    schedule_or_trigger: string;
    source_path: string | null;
    break_risk: string;
  }>;
  handoff_gate: {
    state?: string;
    summary?: string;
    requirements?: Array<{
      id: string;
      label: string;
      state: string;
      note: string;
    }>;
  };
  control_plane: {
    proposal_family: string | null;
    active_family: string | null;
    proposal_plan_path: string | null;
    active_plan_path: string | null;
    activation_latest_path: string | null;
    nightly_state_path: string | null;
    line_state_root: string | null;
    campaign_index_path: string | null;
    runtime_shadow_path: string | null;
    runtime_activation?: {
      path: string | null;
      enabled: boolean;
      campaign_id: string | null;
      updated_at: string | null;
      raw_state_path: string | null;
    };
    runtime_dispatch?: {
      state: string | null;
      campaign_id: string | null;
      requested_campaign_id: string | null;
      suggested_campaign_id: string | null;
      attempted: boolean;
      fallback_used: boolean;
      activation_mismatch: boolean;
      returncode: number | null;
      reason: string | null;
      reason_compact: string;
    };
    runtime_campaign_selection?: {
      policy: string;
      policy_id: string | null;
      selected_campaign_id: string | null;
      requested_campaign_id: string | null;
      selected_entry_present: boolean;
      selection_reason: string;
      selection_notes: string;
      candidate_set?: RuntimeSelectionCandidate[];
      candidate_count?: number;
    };
    selected_campaign_id: string | null;
    selection_hint: string;
  };
  campaign_state: {
    campaign_id: string | null;
    status: string | null;
    phase: string | null;
    active_candidate_id: string | null;
    dispatchable: boolean;
    cluster_mode: string | null;
    cluster_window: string | null;
    max_bounded_slices_per_cluster: number | null;
    next_action_id: string | null;
    next_worker_type: string | null;
    next_candidate_id: string | null;
    retry_remaining_for_active: number | null;
    stale_after_active: string | null;
    stale_after_parked: string | null;
    research_autonomous: boolean;
    attach_autonomous: boolean;
    campaign_path: string | null;
    state_path: string | null;
    next_action_path: string | null;
    status_path: string | null;
    gates_path: string | null;
    runtime_dispatch?: {
      state: string | null;
      campaign_id: string | null;
      requested_campaign_id: string | null;
      suggested_campaign_id: string | null;
      attempted: boolean;
      fallback_used: boolean;
      activation_mismatch: boolean;
      returncode: number | null;
      reason: string | null;
      reason_compact: string;
    };
    selection?: {
      policy: string;
      policy_id: string | null;
      selected_campaign_id: string | null;
      requested_campaign_id: string | null;
      selected_entry_present: boolean;
      selection_reason: string;
      selection_notes: string;
      candidate_set?: RuntimeSelectionCandidate[];
      candidate_count?: number;
    };
  };
  sources: string[];
};

type EvidenceRow = Record<string, unknown>;
type KeyValueItem = { label: string; value: unknown };

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${path} -> ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function formatDate(date: string) {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Taipei",
  });
}

function summarizeCampaignSelectionCandidates(candidates?: RuntimeSelectionCandidate[]): string {
  if (!candidates || candidates.length === 0) return "—";
  return candidates
    .slice(0, 6)
    .map((item) => `${item.campaignId || "-"}(p=${item.priority ?? "-"},r=${item.phase || "-"})`)
    .join(", ");
}

function formatHours(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(2)}h`;
}

function stringifyValue(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.length ? value.map((item) => stringifyValue(item)).join(", ") : "[]";
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function getRowString(row: EvidenceRow, key: string): string | null {
  const value = row[key];
  return typeof value === "string" ? value : typeof value === "number" ? String(value) : null;
}

function statusTone(value: string | null | undefined): "accent" | "alert" | "muted" {
  const normalized = (value ?? "").toLowerCase();
  if (normalized.includes("hold") || normalized.includes("needs") || normalized.includes("diverg") || normalized.includes("unknown") || normalized.includes("missing")) return "alert";
  if (normalized.includes("ready") || normalized.includes("synthetic") || normalized.includes("active") || normalized.includes("proposed")) return "accent";
  return "muted";
}

function KeyValueGrid({ items }: { items: KeyValueItem[] }) {
  if (!items.length) return null;
  return (
    <div className="kv-grid">
      {items.map((item) => (
        <div className="kv-item" key={item.label}>
          <span className="mini-label">{item.label}</span>
          <strong>{stringifyValue(item.value)}</strong>
        </div>
      ))}
    </div>
  );
}

function EvidenceStack({
  title,
  rows,
  getKey,
  renderPrimary,
  renderMeta,
}: {
  title: string;
  rows: EvidenceRow[];
  getKey: (row: EvidenceRow, index: number) => string;
  renderPrimary: (row: EvidenceRow) => string;
  renderMeta?: (row: EvidenceRow) => string;
}) {
  return (
    <div className="evidence-stack">
      <p className="mini-label" style={{ marginBottom: "8px" }}>{title}</p>
      {rows.length ? (
        rows.slice(0, 5).map((row, index) => (
          <div className="evidence-row" key={getKey(row, index)}>
            <span>{renderPrimary(row)}</span>
            {renderMeta ? <span className="muted">{renderMeta(row)}</span> : null}
          </div>
        ))
      ) : (
        <div className="muted" style={{ fontSize: "0.8rem", padding: "8px" }}>No samples.</div>
      )}
    </div>
  );
}

function StatusChip({ value }: { value: string | null | undefined }) {
  if (!value) return null;
  return <span className={`status-chip status-chip-${statusTone(value)}`}>{value.replace(/-/g, " ").toUpperCase()}</span>;
}

function TargetList({ targets, emptyState }: { targets: StrategyPlanTarget[]; emptyState: string }) {
  if (!targets.length) {
    return <div className="muted baton-empty">{emptyState}</div>;
  }

  return (
    <ul className="baton-target-list">
      {targets.map((target) => (
        <li key={`${target.variant_id}-${target.deck_path ?? "missing-deck"}`}>
          <strong>{target.deck_id ?? target.variant_id}</strong>
          <span className="card-meta">{target.variant_id}</span>
          <code>{target.deck_path ?? "No deck path recorded"}</code>
        </li>
      ))}
    </ul>
  );
}

function HistoryList({
  title,
  events,
  emptyState,
}: {
  title: string;
  events: StrategyHistoryEntry[];
  emptyState: string;
}) {
  return (
    <div className="strategy-section">
      <p className="mini-label">{title}</p>
      {events.length ? (
        <div className="history-list">
          {events.map((event) => (
            <article className="history-item" key={event.event_id}>
              <div className="history-item-head">
                <div>
                  <div className="card-title history-title">{event.title}</div>
                  <div className="card-meta">{formatTimestamp(event.timestamp)} · {event.kind}</div>
                </div>
                <StatusChip value={event.status} />
              </div>
              <p className="card-meta">{event.summary}</p>
              <code>{event.path}</code>
            </article>
          ))}
        </div>
      ) : (
        <div className="muted history-empty">{emptyState}</div>
      )}
    </div>
  );
}

function StrategySurface({ view }: { view: StrategyPowerhouseView }) {
  const proposalItems: KeyValueItem[] = [
    { label: "proposal family", value: view.proposal.proposal_family },
    { label: "prepared", value: formatTimestamp(view.proposal.proposal_prepared_at) },
    { label: "proposal state", value: view.proposal.proposal_state },
    { label: "active family", value: view.proposal.active_family },
    { label: "execution authority", value: view.boundary.execution_authority },
    { label: "governance mutation", value: String(view.boundary.governance_mutation) },
  ];
  const activeFamilyLabel = view.baton_line.active.family ?? "No active family truth present";
  const proposalFamilyLabel = view.baton_line.proposal.family ?? "No proposal family recorded";
  const breadcrumb = view.baton_line.breadcrumb;
  const lastBatonSource = breadcrumb.last_baton_source;
  const previousFamilyLabel = lastBatonSource.from_family ?? "unknown / not indexed";
  const freshnessMeta = breadcrumb.divergence_freshness.age_hours !== null
    ? `${formatHours(breadcrumb.divergence_freshness.age_hours)} indexed gap`
    : formatTimestamp(breadcrumb.divergence_freshness.reference_at);

  return (
    <main className="strategy-surface">
      <section className="panel">
        <div className="panel-header">
          <h3>Active-Family Baton Line</h3>
          <span className="pill">READ ONLY / NO AUTHORITY</span>
        </div>
        <div className="panel-body">
          <p className="strategy-note strategy-boundary-note">{view.baton_line.read_only_note}</p>
          <article className="baton-breadcrumb">
            <div className="baton-breadcrumb-head">
              <div>
                <p className="mini-label">Last active-plan / baton change</p>
                <strong>{formatTimestamp(breadcrumb.last_active_change_at)}</strong>
              </div>
              <div className="strategy-chip-row baton-breadcrumb-chips">
                <StatusChip value={breadcrumb.state} />
                <StatusChip value={breadcrumb.divergence_freshness.state} />
              </div>
            </div>
            <div className="baton-breadcrumb-grid">
              <div>
                <p className="mini-label">Previous baton source</p>
                <div className="card-meta">{previousFamilyLabel} → {lastBatonSource.to_family ?? activeFamilyLabel}</div>
                <code>{lastBatonSource.path ?? lastBatonSource.label}</code>
                <p className="card-meta">{formatTimestamp(lastBatonSource.changed_at)}</p>
              </div>
              <div>
                <p className="mini-label">Current active source</p>
                <code>{breadcrumb.last_active_change_source ?? "No active plan source packet recorded"}</code>
                <p className="card-meta">{breadcrumb.change_summary}</p>
              </div>
              <div>
                <p className="mini-label">Divergence freshness</p>
                <div className="card-meta">{freshnessMeta}</div>
                <p className="card-meta">{breadcrumb.divergence_freshness.note}</p>
              </div>
            </div>
            {lastBatonSource.forcing_evidence ? <code>{lastBatonSource.forcing_evidence}</code> : null}
            {lastBatonSource.summary ? <p className="strategy-note">{lastBatonSource.summary}</p> : null}
            <p className="strategy-note">{breadcrumb.note}</p>
          </article>
          <div className="baton-grid">
            <article className="baton-card">
              <div className="baton-head">
                <span className="mini-label">Today&apos;s Active Family</span>
                <StatusChip value={view.baton_line.active.truth_state} />
              </div>
              <strong className="baton-value">{activeFamilyLabel}</strong>
              <p className="card-meta">{formatTimestamp(view.baton_line.active.prepared_at)}</p>
              <p className="card-meta">{view.baton_line.active.attachment_summary}</p>
            </article>

            <article className="baton-card">
              <div className="baton-head">
                <span className="mini-label">Attached Plan / Decks</span>
                <StatusChip value={view.baton_line.active.targets.length ? "attached" : view.baton_line.active.truth_state} />
              </div>
              <code>{view.baton_line.active.source_packet ?? "No active plan source packet recorded"}</code>
              <TargetList
                targets={view.baton_line.active.targets}
                emptyState="No active deck attachment truth is available."
              />
            </article>

            <article className="baton-card">
              <div className="baton-head">
                <span className="mini-label">Handoff Readiness</span>
                <StatusChip value={view.baton_line.handoff_readiness.state} />
              </div>
              <strong className="baton-value">{view.baton_line.today ?? "Current day"}</strong>
              <p className="strategy-note">{view.baton_line.handoff_readiness.summary}</p>
            </article>

            <article className="baton-card">
              <div className="baton-head">
                <span className="mini-label">Activation / Promotion</span>
                <StatusChip value={view.baton_line.activation.plan_state} />
              </div>
              {view.baton_line.activation.latest?.activated_at ? (
                <p className="card-meta">Activated at {formatTimestamp(view.baton_line.activation.latest.activated_at)}</p>
              ) : (
                <p className="card-meta">No activation timestamp recorded.</p>
              )}
              <p className="card-meta">
                Effective scope: {view.baton_line.activation.latest?.effective_scope ?? "unknown"}
              </p>
              {view.baton_line.activation.latest?.effective_run_day ? (
                <p className="card-meta">Effective run day: {view.baton_line.activation.latest.effective_run_day}</p>
              ) : null}
              <p className="strategy-note">{view.baton_line.activation.plan_note}</p>
              {view.baton_line.activation.latest?.note ? (
                <p className="strategy-note">{view.baton_line.activation.latest.note}</p>
              ) : null}
              {view.baton_line.activation.latest?.receipt ? (
                <code>{view.baton_line.activation.latest.receipt}</code>
              ) : (
                <div className="baton-empty">
                  {view.baton_line.activation.latest_pointer_present
                    ? "Activation pointer exists but receipt path is missing."
                    : "No activation receipt pointer found."}
                </div>
              )}
            </article>

            <article className="baton-card">
              <div className="baton-head">
                <span className="mini-label">Proposed vs Active</span>
                <StatusChip value={view.baton_line.divergence.state} />
              </div>
              <strong className="baton-value">{proposalFamilyLabel}</strong>
              <p className="card-meta">{formatTimestamp(view.baton_line.proposal.prepared_at)}</p>
              <p className="strategy-note">{view.baton_line.divergence.note}</p>
              <code>{view.baton_line.proposal.source_packet}</code>
              <div className="baton-inline-list">
                {view.baton_line.proposal.target_labels.length
                  ? view.baton_line.proposal.target_labels.join(" · ")
                  : "No proposed deck attachments recorded."}
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Authority Boundary</h3>
          <span className="pill">READ ONLY</span>
        </div>
        <div className="panel-body">
          <p className="strategy-note strategy-boundary-note">{view.boundary.note}</p>
          <KeyValueGrid
            items={[
              { label: "primary execution surface", value: view.boundary.primary_execution_surface },
              { label: "strategy-powerhouse role", value: view.boundary.strategy_powerhouse_role },
              { label: "topology changed", value: String(view.topology_changed) },
              { label: "updated", value: formatTimestamp(view.updated_at) },
            ]}
          />
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>架構對照表 / Canon Flow</h3>
          <span className="pill">DYNAMIC STATUS</span>
        </div>
        <div className="panel-body">
          <p className="strategy-note strategy-boundary-note">{view.architecture_map.note}</p>
          <div className="history-list">
            {view.architecture_map.stages.map((stage) => (
              <article className="history-item" key={stage.stage_id}>
                <div className="history-item-head">
                  <div>
                    <div className="card-title history-title">{stage.label}</div>
                    <div className="card-meta">{stage.role} · {stage.current_surface}</div>
                  </div>
                  <StatusChip value={stage.status} />
                </div>
                <p className="card-meta">{stage.summary}</p>
                {stage.blocking_note ? <p className="strategy-note">{stage.blocking_note}</p> : null}
                {stage.latest_receipt ? <code>{stage.latest_receipt}</code> : null}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Current Focus Lines</h3>
          <span className="pill">LATEST RECEIPTS</span>
        </div>
        <div className="panel-body">
          <div className="history-list">
            {view.focus_lines.map((line) => (
              <article className="history-item" key={line.line_id}>
                <div className="history-item-head">
                  <div>
                    <div className="card-title history-title">{line.title}</div>
                    <div className="card-meta">
                      {line.family ?? "no parent family"}
                      {line.variant ? ` · ${line.variant}` : ""}
                    </div>
                  </div>
                  <StatusChip value={line.status} />
                </div>
                <p className="card-meta">{line.summary}</p>
                <p className="strategy-note">Next gate: {line.next_gate}</p>
                <div className="baton-inline-list">topology changed: {String(line.topology_changed)}</div>
                {line.receipts.length ? (
                  <div className="sources-grid">
                    {line.receipts.map((receipt) => (
                      <div className="source-card" key={`${line.line_id}-${receipt.path}`}>
                        <span className="mini-label">{receipt.kind}</span>
                        <strong>{receipt.label}</strong>
                        <div className="card-meta">{formatTimestamp(receipt.timestamp)}</div>
                        <code>{receipt.path}</code>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="muted history-empty">No indexed receipts yet.</div>
                )}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>中文對照 / Glossary</h3>
          <span className="pill">PLAIN LANGUAGE</span>
        </div>
        <div className="panel-body">
          <div className="sources-grid">
            {view.glossary.map((item) => (
              <div className="source-card" key={item.term}>
                <span className="mini-label">{item.role}</span>
                <strong>{item.zh}</strong>
                <div className="card-meta">{item.term}</div>
                <p className="strategy-note">{item.plain}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="metrics-row">
        <article className="metric-card">
          <span className="mini-label">Cards</span>
          <strong>{view.metrics.card_count}</strong>
          <p>Current local proposal surface.</p>
        </article>
        <article className="metric-card">
          <span className="mini-label">Ready</span>
          <strong>{view.metrics.ready_count}</strong>
          <p>Observation-ready families.</p>
        </article>
        <article className="metric-card">
          <span className="mini-label">Hold</span>
          <strong className={view.metrics.hold_count > 0 ? "text-alert" : ""}>{view.metrics.hold_count}</strong>
          <p>Families blocked by current truth.</p>
        </article>
        <article className="metric-card">
          <span className="mini-label">Synthetic Proven</span>
          <strong>{view.metrics.synthetic_proven_count}</strong>
          <p>Positive-case verifier receipts present.</p>
        </article>
        <article className="metric-card">
          <span className="mini-label">History Events</span>
          <strong>{view.metrics.history_event_count}</strong>
          <p>Family timeline entries sourced locally.</p>
        </article>
        <article className="metric-card">
          <span className="mini-label">Verifier Receipts</span>
          <strong>{view.metrics.verifier_receipt_count}</strong>
          <p>Synthetic verifier history carried into the browser.</p>
        </article>
      </div>

      <section className="panel">
        <div className="panel-header">
          <h3>Strategy Powerhouse / Family History Browser</h3>
          <span className="pill">LOCAL ARTIFACTS ONLY</span>
        </div>
        <div className="strategy-card-grid">
          {view.cards.map((card) => (
            <article className="strategy-summary-card" key={card.candidate_id}>
              <div className="strategy-summary-head">
                <div>
                  <div className="card-title">{card.display_name}</div>
                  <div className="card-meta">{card.candidate_id} · {card.family_id}</div>
                </div>
                <div className="strategy-chip-row">
                  <StatusChip value={card.status} />
                  <StatusChip value={card.validation_status} />
                  <StatusChip value={card.proposal_state} />
                </div>
              </div>

              <p className="strategy-note">{card.handoff_state}</p>
              <KeyValueGrid
                items={[
                  { label: "current gate", value: card.current_gate ?? "—" },
                  { label: "handoff state", value: card.handoff_state },
                  { label: "latest packet", value: card.latest_packet?.title ?? "No family packet found" },
                  { label: "latest packet kind", value: card.latest_packet?.kind ?? "—" },
                ]}
              />

              {card.latest_packet ? (
                <div className="strategy-section">
                  <p className="mini-label">Latest Packet</p>
                  <article className="history-item history-item-highlight">
                    <div className="history-item-head">
                      <div>
                        <div className="card-title history-title">{card.latest_packet.title}</div>
                        <div className="card-meta">{formatTimestamp(card.latest_packet.timestamp)} · {card.latest_packet.kind}</div>
                      </div>
                      <StatusChip value={card.latest_packet.status} />
                    </div>
                    <p className="card-meta">{card.latest_packet.summary}</p>
                    <code>{card.latest_packet.path}</code>
                  </article>
                </div>
              ) : null}

              <HistoryList
                title="Verifier History"
                events={card.verifier_history}
                emptyState="No verifier history exists for this family yet."
              />

              <HistoryList
                title="Family Timeline"
                events={card.family_timeline}
                emptyState="No family timeline exists yet; this surface is intentionally sparse when local artifacts are missing."
              />

              <div className="strategy-section">
                <p className="mini-label">Selected Parameter Pack</p>
                <div className="parameter-grid">
                  {card.selected_parameter_summary.map((item) => (
                    <div className="parameter-item" key={`${card.candidate_id}-${item.label}`}>
                      <span className="mini-label">{item.label}</span>
                      <strong>{stringifyValue(item.value)}</strong>
                    </div>
                  ))}
                </div>
              </div>

              <div className="strategy-section strategy-columns">
                <div>
                  <p className="mini-label">Universe / Features</p>
                  <p className="card-meta">symbols: {card.symbol_pool.join(", ") || "—"}</p>
                  <p className="card-meta">features: {card.feature_requirements.join(", ") || "—"}</p>
                </div>
                <div>
                  <p className="mini-label">Research Notes</p>
                  <p className="card-meta">{card.notes}</p>
                  <p className="card-meta">{card.proof_note}</p>
                </div>
              </div>

              <div className="strategy-section">
                <p className="mini-label">Related Packets / Receipts</p>
                <ul className="path-list">
                  {card.related_links.map((link) => (
                    <li key={`${card.candidate_id}-${link.label}-${link.path}`}>
                      <span className="path-label">{link.label}</span>
                      <code>{link.path}</code>
                    </li>
                  ))}
                </ul>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Proposal / Control Truth</h3>
          <span className="pill">NO MUTATION</span>
        </div>
        <div className="panel-body">
          <KeyValueGrid items={proposalItems} />
          <p className="strategy-note">{view.proposal.truthful_boundary}</p>
          <ul className="path-list">
            <li>
              <span className="path-label">proposal source packet</span>
              <code>{view.proposal.source_packet}</code>
            </li>
            {view.proposal.active_plan_source ? (
              <li>
                <span className="path-label">active plan source</span>
                <code>{view.proposal.active_plan_source}</code>
              </li>
            ) : null}
          </ul>
          <div className="sources-grid">
            {view.sources.map((source) => (
              <div className="source-card" key={`${source.kind}-${source.path}`}>
                <span className="mini-label">{source.kind}</span>
                <strong>{source.label}</strong>
                <code>{source.path}</code>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function StrategyPipelineSurface({ view }: { view: StrategyPipelineView }) {
  return (
    <main className="strategy-surface">
      <section className="panel">
        <div className="panel-header">
          <h3>Pipeline Verdict</h3>
          <span className="pill">READ ONLY / DYNAMIC</span>
        </div>
        <div className="panel-body">
          <p className="strategy-note strategy-boundary-note">{view.summary.headline}</p>
          <KeyValueGrid
            items={[
              { label: "current state", value: view.summary.current_state },
              { label: "verdict", value: view.summary.verdict },
              { label: "line", value: view.line_state.title },
              { label: "run state", value: view.line_state.run_state },
              { label: "handoff ready", value: String(view.line_state.handoff_ready) },
              { label: "live sim attach", value: view.line_state.live_sim_attach_state },
            ]}
          />
          <p className="strategy-note">{view.summary.note}</p>
          {view.line_state.state_path ? <code>{view.line_state.state_path}</code> : null}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Canon Flow</h3>
          <span className="pill">STAGE STATE</span>
        </div>
        <div className="panel-body">
          <div className="history-list">
            {view.canon_flow.map((stage) => (
              <article className="history-item" key={stage.stage_id}>
                <div className="history-item-head">
                  <div>
                    <div className="card-title history-title">{stage.label}</div>
                    <div className="card-meta">{stage.stage_id}</div>
                  </div>
                  <StatusChip value={stage.state} />
                </div>
                <p className="card-meta">{stage.summary}</p>
                {stage.receipt ? <code>{stage.receipt}</code> : null}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Pipeline Components</h3>
          <span className="pill">WHO DOES WHAT</span>
        </div>
        <div className="panel-body">
          <div className="history-list">
            {view.components.map((component) => (
              <article className="history-item" key={component.component_id}>
                <div className="history-item-head">
                  <div>
                    <div className="card-title history-title">{component.label}</div>
                    <div className="card-meta">{component.role} · {component.current_surface}</div>
                  </div>
                  <StatusChip value={component.status} />
                </div>
                <p className="strategy-note">{component.note}</p>
                <div className="sources-grid">
                  {component.source_paths.filter(Boolean).map((path) => (
                    <div className="source-card" key={`${component.component_id}-${path}`}>
                      <span className="mini-label">source</span>
                      <code>{path}</code>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Autonomous Drivers</h3>
          <span className="pill">LOOPS / CONTROLLERS</span>
        </div>
        <div className="panel-body">
          <div className="history-list">
            {view.autonomous_drivers.map((driver) => (
              <article className="history-item" key={driver.driver_id}>
                <div className="history-item-head">
                  <div>
                    <div className="card-title history-title">{driver.label}</div>
                    <div className="card-meta">{driver.role} · {driver.schedule_or_trigger}</div>
                  </div>
                  <StatusChip value={driver.state} />
                </div>
                <p className="strategy-note">{driver.break_risk}</p>
                {driver.source_path ? <code>{driver.source_path}</code> : null}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Campaign Controller</h3>
          <span className="pill">AUTONOMOUS READINESS</span>
        </div>
        <div className="panel-body">
          <KeyValueGrid
            items={[
              { label: "campaign", value: view.campaign_state.campaign_id },
              { label: "status", value: view.campaign_state.status },
              { label: "phase", value: view.campaign_state.phase },
              { label: "dispatchable", value: String(view.campaign_state.dispatchable) },
              { label: "active candidate", value: view.campaign_state.active_candidate_id },
              { label: "next action", value: view.campaign_state.next_action_id },
              { label: "next worker", value: view.campaign_state.next_worker_type },
              { label: "cluster mode", value: view.campaign_state.cluster_mode },
              { label: "cluster window", value: view.campaign_state.cluster_window },
              { label: "max slices / cluster", value: view.campaign_state.max_bounded_slices_per_cluster },
              { label: "retry remaining", value: view.campaign_state.retry_remaining_for_active },
              { label: "stale_after(active)", value: view.campaign_state.stale_after_active },
              { label: "stale_after(parked)", value: view.campaign_state.stale_after_parked },
            ]}
          />
          <KeyValueGrid
            items={[
              { label: "research-autonomous", value: String(view.campaign_state.research_autonomous) },
              { label: "attach-autonomous", value: String(view.campaign_state.attach_autonomous) },
              { label: "runtime dispatch state", value: view.campaign_state.runtime_dispatch?.state },
              { label: "runtime requested campaign", value: view.campaign_state.selection?.requested_campaign_id },
              { label: "runtime selected campaign", value: view.campaign_state.selection?.selected_campaign_id },
              { label: "runtime suggested campaign", value: view.campaign_state.runtime_dispatch?.suggested_campaign_id },
              { label: "runtime fallback used", value: String(Boolean(view.campaign_state.runtime_dispatch?.fallback_used)) },
              { label: "activation mismatch", value: String(Boolean(view.campaign_state.runtime_dispatch?.activation_mismatch)) },
              { label: "runtime selector", value: view.campaign_state.selection?.policy },
              { label: "runtime selector reason", value: view.campaign_state.selection?.selection_reason },
              { label: "runtime policy id", value: view.campaign_state.selection?.policy_id ?? "—" },
              {
                label: "runtime candidate set",
                value: summarizeCampaignSelectionCandidates(view.campaign_state.selection?.candidate_set),
              },
            ]}
          />
          {view.campaign_state.runtime_dispatch?.reason ? <p className="strategy-note">{view.campaign_state.runtime_dispatch?.reason}</p> : null}
          <div className="sources-grid">
            {[view.campaign_state.campaign_path, view.campaign_state.state_path, view.campaign_state.next_action_path, view.campaign_state.status_path, view.campaign_state.gates_path]
              .filter(Boolean)
              .map((path) => (
                <div className="source-card" key={`campaign-${path}`}>
                  <span className="mini-label">campaign</span>
                  <code>{path}</code>
                </div>
              ))}
            {[view.control_plane.runtime_shadow_path, view.control_plane.runtime_activation?.path]
              .filter(Boolean)
              .map((path) => (
                <div className="source-card" key={`runtime-${path}`}>
                  <span className="mini-label">runtime</span>
                  <code>{path}</code>
                </div>
              ))}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>Handoff Gate</h3>
          <span className="pill">LIVE SIM BLOCKER</span>
        </div>
        <div className="panel-body">
          <KeyValueGrid
            items={[
              { label: "state", value: view.handoff_gate.state ?? "unknown" },
              { label: "proposal family", value: view.control_plane.proposal_family },
              { label: "active family", value: view.control_plane.active_family },
              { label: "activation latest", value: view.control_plane.activation_latest_path },
              { label: "runtime dispatch", value: view.control_plane.runtime_dispatch?.state },
              { label: "runtime selected campaign", value: view.control_plane.selected_campaign_id },
              { label: "runtime selector policy", value: view.control_plane.runtime_campaign_selection?.policy },
              { label: "runtime selector policy id", value: view.control_plane.runtime_campaign_selection?.policy_id ?? "—" },
            ]}
          />
          {view.handoff_gate.summary ? <p className="strategy-note">{view.handoff_gate.summary}</p> : null}
          <div className="history-list">
            {(view.handoff_gate.requirements ?? []).map((requirement) => (
              <article className="history-item" key={requirement.id}>
                <div className="history-item-head">
                  <div>
                    <div className="card-title history-title">{requirement.label}</div>
                    <div className="card-meta">{requirement.id}</div>
                  </div>
                  <StatusChip value={requirement.state} />
                </div>
                <p className="card-meta">{requirement.note}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function App() {
  const [dashboardTab, setDashboardTab] = useState<DashboardTab>("live-sim");
  const [dates, setDates] = useState<DateItem[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [deck, setDeck] = useState<DeckView | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [activeEventKey, setActiveEventKey] = useState<string | null>(null);
  const [cardDetail, setCardDetail] = useState<CardDetail | null>(null);
  const [strategyPowerhouse, setStrategyPowerhouse] = useState<StrategyPowerhouseView | null>(null);
  const [strategyPipeline, setStrategyPipeline] = useState<StrategyPipelineView | null>(null);
  const [deckLoading, setDeckLoading] = useState(true);
  const [cardLoading, setCardLoading] = useState(false);
  const [strategyLoading, setStrategyLoading] = useState(true);
  const [pipelineLoading, setPipelineLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getJson<DateItem[]>("/api/dates")
      .then((payload) => {
        setDates(payload);
        if (payload.length > 0) setSelectedDate(payload[0].date);
      })
      .catch((reason) => setError(String(reason)));

    getJson<StrategyPowerhouseView>("/api/strategy-powerhouse")
      .then((payload) => setStrategyPowerhouse(payload))
      .catch((reason) => setError(String(reason)))
      .finally(() => setStrategyLoading(false));

    getJson<StrategyPipelineView>("/api/strategy-pipeline")
      .then((payload) => setStrategyPipeline(payload))
      .catch((reason) => setError(String(reason)))
      .finally(() => setPipelineLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedDate) return;
    setDeckLoading(true);
    getJson<DeckView>(`/api/days/${selectedDate}/deck`)
      .then((payload) => {
        setDeck(payload);
        setActiveCardId(null);
        setActiveEventKey(null);
      })
      .catch((reason) => setError(String(reason)))
      .finally(() => setDeckLoading(false));
  }, [selectedDate]);

  useEffect(() => {
    if (!selectedDate || !activeCardId || !deck) {
      setCardDetail(null);
      return;
    }
    const card = deck.strategy.cards.find((item) => item.id === activeCardId);
    if (!card) return;

    setCardLoading(true);
    getJson<CardDetail>(`/api/days/${selectedDate}/lanes/${card.lane}/cards/${card.card_id}`)
      .then((payload) => setCardDetail(payload))
      .catch((reason) => setError(String(reason)))
      .finally(() => setCardLoading(false));
  }, [selectedDate, activeCardId, deck]);

  const activeEvent = useMemo(() => {
    return deck?.evidence.timeline.find((event) => event.event_key === activeEventKey) ?? null;
  }, [deck, activeEventKey]);

  const eventSummaryItems = useMemo<KeyValueItem[]>(() => {
    if (!activeEvent) return [];
    const details = activeEvent.details ?? {};
    if (activeEvent.kind === "anomaly") {
      return [
        { label: "category", value: details.category },
        { label: "severity", value: details.severity },
        { label: "message", value: details.message },
      ];
    }
    if (activeEvent.kind.startsWith("risk-")) {
      return [
        { label: "decision", value: details.decision },
        { label: "reason", value: details.reason_code },
        { label: "policy", value: details.policy_name },
        { label: "qty", value: details.adjusted_qty },
      ];
    }
    if (activeEvent.kind === "execution-request" || activeEvent.kind === "execution-phase-violation") {
      return [
        { label: "symbol", value: details.symbol },
        { label: "side", value: details.side },
        { label: "qty", value: details.qty },
        { label: "price", value: details.limit_price },
        { label: "phase", value: details.market_phase },
        { label: "semantic", value: details.phase_semantic_label },
        { label: "contract", value: details.session_contract_status },
        { label: "tif", value: details.time_in_force },
        { label: "profile", value: details.order_profile_name },
        { label: "user_def_suffix", value: details.requested_user_def_suffix },
      ];
    }
    return [{ label: "kind", value: activeEvent.kind }];
  }, [activeEvent]);

  const liveSimSubtitle = deck
    ? `Execution truth from committed ${deck.fixture.comparison_relpath}.`
    : "Execution truth from committed replay/live-sim fixture bundles.";

  return (
    <div className="page-shell">
      <header className="hero">
        <div className="hero-copy">
          <div className="hero-info">
            <h1>Steamer Dashboard</h1>
            <p>
              {dashboardTab === "live-sim"
                ? liveSimSubtitle
                : dashboardTab === "strategy-powerhouse"
                  ? "Research/control truth from local strategy-powerhouse artifacts. Read-only; no execution authority."
                  : "Whole-pipeline design, components, autonomous drivers, and handoff gates from local state/receipts. Read-only."}
            </p>
          </div>
          <nav className="dashboard-tabs">
            <button
              className={`dashboard-tab ${dashboardTab === "live-sim" ? "dashboard-tab-active" : ""}`}
              onClick={() => setDashboardTab("live-sim")}
              type="button"
            >
              Live Sim
            </button>
            <button
              className={`dashboard-tab ${dashboardTab === "strategy-powerhouse" ? "dashboard-tab-active" : ""}`}
              onClick={() => setDashboardTab("strategy-powerhouse")}
              type="button"
            >
              Strategy Powerhouse / Strategy Cards
            </button>
            <button
              className={`dashboard-tab ${dashboardTab === "strategy-pipeline" ? "dashboard-tab-active" : ""}`}
              onClick={() => setDashboardTab("strategy-pipeline")}
              type="button"
            >
              Strategy Pipeline / Autonomous Drivers
            </button>
          </nav>
        </div>

        {dashboardTab === "live-sim" ? (
          <nav className="deck-selector">
            {dates.map((date) => (
              <button
                key={date.date}
                className={`deck-tab ${selectedDate === date.date ? "deck-tab-active" : ""}`}
                onClick={() => startTransition(() => setSelectedDate(date.date))}
                type="button"
              >
                <div className="deck-tab-date">{formatDate(date.date)}</div>
                <div className="deck-tab-status">{date.compare_status.toUpperCase()}</div>
              </button>
            ))}
          </nav>
        ) : null}
      </header>

      {dashboardTab === "live-sim" ? (
        deckLoading ? (
          <div className="state-block">Engaging deck link…</div>
        ) : deck ? (
          <main className="dashboard-surface">
            <div className="metrics-row">
              <article className="metric-card">
                <span className="mini-label">Dominant Lane</span>
                <strong>{deck.cover.dominant_lane === "steamer-card-engine" ? "CANDIDATE" : "BASELINE"}</strong>
                <p>{deck.cover.dominant_card_label ?? "No card resolved"}</p>
              </article>
              <article className="metric-card">
                <span className="mini-label">Anomalies</span>
                <strong className={deck.cover.anomaly_total > 0 ? "text-alert" : ""}>{deck.cover.anomaly_total}</strong>
                <p>Detected in session logs.</p>
              </article>
              <article className="metric-card">
                <span className="mini-label">Intents</span>
                <strong>{deck.cover.delta_counts.intents?.candidate ?? 0}</strong>
                <p>Strategy intents processed.</p>
              </article>
              <article className="metric-card">
                <span className="mini-label">Status</span>
                <strong className={deck.cover.compare_status === "pass" ? "" : "text-alert"}>{deck.cover.compare_status.toUpperCase()}</strong>
                <p>{deck.cover.scenario_id}</p>
              </article>
              <article className="metric-card">
                <span className="mini-label">Phase Violations</span>
                <strong className={deck.evidence.phase_truth_summary.candidate.contract_violation_count > 0 ? "text-alert" : ""}>
                  {deck.evidence.phase_truth_summary.candidate.contract_violation_count}
                </strong>
                <p>{deck.evidence.phase_truth_summary.candidate.phase_classifier}</p>
              </article>
              <article className="metric-card">
                <span className="mini-label">Open Discovery</span>
                <strong>
                  {deck.evidence.phase_truth_summary.candidate.open_discovery_summary?.saw_official_open_signal ? "SEEN" : "N/A"}
                </strong>
                <p>
                  trial={String(Boolean(deck.evidence.phase_truth_summary.candidate.open_discovery_summary?.saw_trial_match_event))}
                </p>
              </article>
            </div>

            <section className="panel">
              <div className="panel-header">
                <h3>Strategy Cards</h3>
                <span className="pill">{deck.strategy.cards.length} ACTIVE</span>
              </div>
              <div className="cards-list">
                {deck.strategy.cards.map((card) => {
                  const isActive = activeCardId === card.id;
                  return (
                    <div key={card.id} className={`card-item ${isActive ? "card-item-active" : ""}`}>
                      <button
                        className="card-trigger"
                        onClick={() => setActiveCardId(isActive ? null : card.id)}
                        type="button"
                      >
                        <div>
                          <div className="card-title">{card.card_id}</div>
                          <div className="card-meta">{card.lane.toUpperCase()} · v{card.card_version}</div>
                        </div>
                        <div className="card-meta">
                          {card.execution_request_count} E / {card.allowed_risk_count} A / {card.blocked_risk_count} B
                        </div>
                      </button>
                      {isActive && (
                        <div className="expansion-panel">
                          {cardLoading ? (
                            <div className="muted">Scanning archives…</div>
                          ) : cardDetail ? (
                            <>
                              <div className="kv-grid">
                                <div className="kv-item">
                                  <span className="mini-label">Intents</span>
                                  <strong>{cardDetail.counts.intents}</strong>
                                </div>
                                <div className="kv-item">
                                  <span className="mini-label">Execution</span>
                                  <strong>{cardDetail.counts.execution_requests}</strong>
                                </div>
                              </div>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                                <EvidenceStack
                                  title="Recent Intents"
                                  rows={cardDetail.samples.intents}
                                  getKey={(row, index) => getRowString(row, "intent_id") ?? `i${index}`}
                                  renderPrimary={(row) => `${getRowString(row, "side")?.toUpperCase()} ${getRowString(row, "symbol")}`}
                                />
                                <EvidenceStack
                                  title="Risk Decisions"
                                  rows={cardDetail.samples.risk_decisions}
                                  getKey={(row, index) => getRowString(row, "risk_decision_id") ?? `r${index}`}
                                  renderPrimary={(row) => `${getRowString(row, "decision")?.toUpperCase()} ${getRowString(row, "reason_code")}`}
                                />
                              </div>
                            </>
                          ) : null}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="panel">
              <div className="panel-header">
                <h3>Evidence Feed</h3>
                <span className="pill">TIMELINE</span>
              </div>
              <div className="timeline-container">
                {deck.evidence.timeline.slice(0, 50).map((event) => {
                  const isActive = activeEventKey === event.event_key;
                  return (
                    <div key={event.event_key} className={`timeline-item ${isActive ? "timeline-item-active" : ""}`}>
                      <button
                        className="timeline-trigger"
                        onClick={() => setActiveEventKey(isActive ? null : event.event_key)}
                        type="button"
                      >
                        <span className="timeline-time">
                          {new Date(event.timestamp).toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                        </span>
                        <span>
                          <div>{event.title.toUpperCase()}</div>
                          <div className="mini-label">{event.subtitle}</div>
                        </span>
                      </button>
                      {isActive && (
                        <div className="expansion-panel">
                          <KeyValueGrid items={eventSummaryItems} />
                          <details>
                            <summary className="mini-label" style={{ cursor: "pointer", marginTop: "12px" }}>[RAW PAYLOAD]</summary>
                            <pre className="json-block">{JSON.stringify(event.details, null, 2)}</pre>
                          </details>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          </main>
        ) : (
          <div className="state-block">Select a deck to begin.</div>
        )
      ) : dashboardTab === "strategy-powerhouse" ? (
        strategyLoading ? (
          <div className="state-block">Loading strategy-powerhouse surface…</div>
        ) : strategyPowerhouse ? (
          <StrategySurface view={strategyPowerhouse} />
        ) : (
          <div className="state-block">Strategy-powerhouse artifacts are unavailable.</div>
        )
      ) : pipelineLoading ? (
        <div className="state-block">Loading strategy-pipeline surface…</div>
      ) : strategyPipeline ? (
        <StrategyPipelineSurface view={strategyPipeline} />
      ) : (
        <div className="state-block">Strategy-pipeline artifacts are unavailable.</div>
      )}

      {error ? <div className="state-block text-alert">ERROR: {error}</div> : null}
    </div>
  );
}

export default App;
