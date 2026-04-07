import { startTransition, useEffect, useMemo, useState } from "react";

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

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatTimestamp(value: string) {
  return new Date(value).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "UTC",
  });
}

function stringifyValue(value: unknown): string {
  if (value === null) {
    return "null";
  }
  if (value === undefined) {
    return "—";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => stringifyValue(item)).join(", ") : "[]";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function getRowString(row: EvidenceRow, key: string): string | null {
  const value = row[key];
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    return String(value);
  }
  return null;
}

function getRowNumber(row: EvidenceRow, key: string): number | null {
  const value = row[key];
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function KeyValueGrid({ items }: { items: KeyValueItem[] }) {
  if (!items.length) {
    return null;
  }

  return (
    <div className="kv-grid">
      {items.map((item) => (
        <div className="kv-row" key={item.label}>
          <span className="kv-label">{item.label}</span>
          <span className="kv-value">{stringifyValue(item.value)}</span>
        </div>
      ))}
    </div>
  );
}

function EvidenceList({
  title,
  hint,
  rows,
  getKey,
  renderPrimary,
  renderSecondary,
  renderMeta,
}: {
  title: string;
  hint?: string;
  rows: EvidenceRow[];
  getKey: (row: EvidenceRow, index: number) => string;
  renderPrimary: (row: EvidenceRow) => string;
  renderSecondary?: (row: EvidenceRow) => string;
  renderMeta?: (row: EvidenceRow) => string;
}) {
  return (
    <div className="evidence-stack">
      <div className="evidence-stack-header">
        <h4>{title}</h4>
        {hint ? <p className="muted">{hint}</p> : null}
      </div>
      {rows.length ? (
        <div className="evidence-list">
          {rows.slice(0, 8).map((row, index) => (
            <div className="evidence-row" key={getKey(row, index)}>
              <div className="evidence-row-main">
                <strong>{renderPrimary(row)}</strong>
                {renderSecondary ? <p>{renderSecondary(row)}</p> : null}
              </div>
              {renderMeta ? <div className="evidence-row-meta">{renderMeta(row)}</div> : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="state-block">No sampled rows in this fixture slice.</div>
      )}
    </div>
  );
}

function App() {
  const [dates, setDates] = useState<DateItem[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [deck, setDeck] = useState<DeckView | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [activeEventKey, setActiveEventKey] = useState<string | null>(null);
  const [cardDetail, setCardDetail] = useState<CardDetail | null>(null);
  const [deckLoading, setDeckLoading] = useState(true);
  const [cardLoading, setCardLoading] = useState(false);
  const [timelineLaneFilter, setTimelineLaneFilter] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);

    getJson<DateItem[]>("/api/dates")
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setDates(payload);
        if (!selectedDate && payload.length > 0) {
          setSelectedDate(payload[0].date);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(String(reason));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDate]);

  useEffect(() => {
    if (!selectedDate) {
      return;
    }

    let cancelled = false;
    setDeckLoading(true);
    setError(null);

    getJson<DeckView>(`/api/days/${selectedDate}/deck`)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setDeck(payload);
        setTimelineLaneFilter(null);
        setActiveCardId(payload.strategy.cards[0]?.id ?? null);
        setActiveEventKey(payload.evidence.timeline[0]?.event_key ?? null);
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(String(reason));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDeckLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDate]);

  const activeCard = useMemo(() => {
    return deck?.strategy.cards.find((card) => card.id === activeCardId) ?? null;
  }, [deck, activeCardId]);

  useEffect(() => {
    if (!selectedDate || !activeCard) {
      setCardDetail(null);
      return;
    }

    let cancelled = false;
    setCardLoading(true);

    getJson<CardDetail>(`/api/days/${selectedDate}/lanes/${activeCard.lane}/cards/${activeCard.card_id}`)
      .then((payload) => {
        if (!cancelled) {
          setCardDetail(payload);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(String(reason));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCardLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDate, activeCard?.lane, activeCard?.card_id]);

  const activeEvent = useMemo(() => {
    return deck?.evidence.timeline.find((event) => event.event_key === activeEventKey) ?? null;
  }, [deck, activeEventKey]);

  const visibleTimeline = useMemo(() => {
    const events = deck?.evidence.timeline ?? [];
    if (!timelineLaneFilter) {
      return events;
    }
    return events.filter((event) => event.lane === timelineLaneFilter);
  }, [deck, timelineLaneFilter]);

  const laneAnomalies = useMemo(() => {
    if (!deck || !cardDetail) {
      return [];
    }
    return deck.evidence.anomalies.filter((anom) => anom.lane === cardDetail.lane);
  }, [deck, cardDetail]);

  const evidenceSummaryItems = useMemo<KeyValueItem[]>(() => {
    if (!activeEvent) {
      return [];
    }

    const details = activeEvent.details ?? {};
    if (activeEvent.kind === "anomaly") {
      return [
        { label: "anomaly_id", value: details.anomaly_id },
        { label: "category", value: details.category },
        { label: "severity", value: details.severity },
        { label: "message", value: details.message },
      ];
    }

    if (activeEvent.kind.startsWith("risk-")) {
      return [
        { label: "decision", value: details.decision },
        { label: "reason_code", value: details.reason_code },
        { label: "policy_name", value: details.policy_name },
        { label: "adjusted_qty", value: details.adjusted_qty },
        { label: "intent_id", value: (activeEvent.intent_id ?? details.intent_id) as unknown },
        { label: "risk_decision_id", value: details.risk_decision_id },
      ];
    }

    if (activeEvent.kind === "execution-request") {
      return [
        { label: "symbol", value: details.symbol },
        { label: "side", value: details.side },
        { label: "order_type", value: details.order_type },
        { label: "qty", value: details.qty },
        { label: "limit_price", value: details.limit_price },
        { label: "risk_decision_id", value: details.risk_decision_id },
        { label: "exec_request_id", value: details.exec_request_id },
      ];
    }

    if (activeEvent.kind === "market-sample") {
      const payload = details.payload as Record<string, unknown> | undefined;
      return [
        { label: "event_id", value: details.event_id },
        { label: "symbol", value: details.symbol },
        { label: "price", value: payload?.price },
        { label: "size", value: payload?.size },
      ];
    }

    if (activeEvent.kind === "run-start" || activeEvent.kind === "run-end") {
      return [{ label: "run_id", value: details.run_id }];
    }

    return [];
  }, [activeEvent]);

  return (
    <div className="page-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <header className="hero">
        <div>
          <p className="eyebrow">Steamer Card Engine</p>
          <h1>Mission Control</h1>
          <p className="hero-copy">
            Mission Control → Daily Deck → Strategy Card → Evidence. Read-only battle surfaces over the committed March
            replay fixtures.
          </p>
        </div>
        <div className="hero-chip-cluster">
          <span className="chip">Fixture Set 20260306 / 20260310 / 20260312</span>
          <span className="chip chip-accent">Topology Unchanged</span>
          {deck ? <span className="chip">{deck.universe.calendar ?? "?"}</span> : null}
        </div>
      </header>

      <main className="mission-layout">
        <section className="panel deck-wall">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Deck Wall</p>
              <h2>DAILY DECKS</h2>
            </div>
          </div>
          <div className="deck-wall-list">
            {dates.map((date) => (
              <button
                key={date.date}
                className={`deck-cover-tile ${selectedDate === date.date ? "deck-cover-tile-active" : ""}`}
                onClick={() =>
                  startTransition(() => {
                    setSelectedDate(date.date);
                  })
                }
                type="button"
              >
                <div className="deck-cover-top">
                  <strong>{formatDate(date.date)}</strong>
                  {date.hero ? <span className="badge badge-hero">HERO</span> : null}
                </div>
                <p className="deck-cover-subtitle">{date.scenario_id}</p>
                <div className="deck-cover-meta">
                  <span className={`badge ${date.compare_status === "pass" ? "badge-hero" : "badge-muted"}`}>
                    {date.compare_status.toUpperCase()}
                  </span>
                  <span className="badge badge-muted">{date.anomaly_count} ANOM</span>
                </div>
                <p className="deck-cover-bottom muted">
                  {date.dominant_lane} {date.candidate_deck_id ? ` · deck=${date.candidate_deck_id}` : ""}
                </p>
              </button>
            ))}
          </div>
        </section>

        <section className="panel daily-deck">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Operational View</p>
              <h2>{deck ? formatDate(deck.date).toUpperCase() : selectedDate ? formatDate(selectedDate).toUpperCase() : "Select a day"}</h2>
              {deck ? <p className="muted">{deck.cover.scenario_id}</p> : null}
            </div>
            {deck ? (
              <span className={`badge ${deck.cover.compare_status === "pass" ? "badge-hero" : "badge-alert"}`}>
                {deck.cover.compare_status.toUpperCase()}
              </span>
            ) : null}
          </div>

          {deckLoading ? <div className="state-block">Engaging deck link…</div> : null}
          {error ? <div className="state-block state-error">ERROR: {error}</div> : null}

          {!deckLoading && deck ? (
            <>
              <div className="deck-cover-grid">
                <article className="metric-card">
                  <span className="metric-label">Dominant Lane</span>
                  <strong>{deck.cover.dominant_lane === "steamer-card-engine" ? "CANDIDATE" : "BASELINE"}</strong>
                  <p>{deck.cover.dominant_card_label ?? "No card resolved"}</p>
                </article>
                <article className="metric-card">
                  <span className="metric-label">Anomalies</span>
                  <strong className={deck.cover.anomaly_total > 0 ? "text-alert" : ""}>{deck.cover.anomaly_total}</strong>
                  <p>Detected in session logs.</p>
                </article>
                <article className="metric-card">
                  <span className="metric-label">Decisions</span>
                  <strong>{deck.cover.delta_counts.intents?.candidate ?? 0}</strong>
                  <p>Strategy intents processed.</p>
                </article>
                <article className="metric-card">
                  <span className="metric-label">Truth State</span>
                  <strong>{deck.cover.transaction_state.toUpperCase()}</strong>
                  <p>{deck.transactions.empty_state_metadata.empty_reason}</p>
                </article>
              </div>

              <div className="deck-sections">
                <article className="subpanel">
                  <div className="subpanel-header">
                    <h3>STRATEGY CARDS</h3>
                    <span className="pill">{deck.strategy.cards.length} ACTIVE</span>
                  </div>
                  <div className="card-grid">
                    {deck.strategy.cards.map((card) => (
                      <button
                        className={`card-tile ${activeCardId === card.id ? "card-tile-active" : ""}`}
                        key={card.id}
                        onClick={() => setActiveCardId(card.id)}
                        type="button"
                      >
                        <div className="card-tile-top">
                          <strong>{card.card_id}</strong>
                          <span className="badge badge-muted">{card.lane.split("-")[0]}</span>
                        </div>
                        <div className="card-tile-metrics">
                          <span>{card.execution_request_count} EXEC</span>
                          <span>{card.allowed_risk_count} ALLOW</span>
                          <span>{card.blocked_risk_count} BLOCK</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </article>

                <article className="subpanel">
                  <div className="subpanel-header">
                    <h3>EVIDENCE FEED</h3>
                    <div className="chip-row">
                      <button
                        type="button"
                        className={`chip chip-button ${!timelineLaneFilter ? "chip-accent" : ""}`}
                        onClick={() => setTimelineLaneFilter(null)}
                      >
                        ALL
                      </button>
                      <button
                        type="button"
                        className={`chip chip-button ${timelineLaneFilter === "steamer-card-engine" ? "chip-accent" : ""}`}
                        onClick={() => setTimelineLaneFilter("steamer-card-engine")}
                      >
                        CANDIDATE
                      </button>
                    </div>
                  </div>
                  <div className="timeline">
                    {visibleTimeline.slice(0, 70).map((event) => {
                      const isActive = activeEventKey === event.event_key;
                      const isRelatedToCard =
                        !!activeCard && event.lane === activeCard.lane && event.card_id === activeCard.card_id;
                      return (
                        <button
                          key={event.event_key}
                          className={`timeline-row timeline-${event.status} ${isActive ? "timeline-row-active" : ""} ${
                            isRelatedToCard ? "timeline-row-related" : ""
                          }`}
                          onClick={() => setActiveEventKey(event.event_key)}
                          type="button"
                        >
                          <div className="timeline-time">{new Date(event.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'})}</div>
                          <div>
                            <strong>{event.title.toUpperCase()}</strong>
                            <p>{event.symbol ? `SYMBOL=${event.symbol}` : ""}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </article>
              </div>

              <div className="deck-sections" style={{ marginTop: '20px' }}>
                <article className="subpanel">
                  <div className="subpanel-header">
                    <h3>UNIVERSE</h3>
                    <span className="pill">{deck.universe.calendar}</span>
                  </div>
                  <div className="universe-grid">
                    <div>
                      <span className="mini-label">TZ</span>
                      <strong>{deck.universe.timezone}</strong>
                    </div>
                    <div>
                      <span className="mini-label">SESSION</span>
                      <strong>{deck.universe.session.slice_label}</strong>
                    </div>
                  </div>
                  <div className="symbol-cloud">
                    {deck.universe.symbol_samples.map((symbol) => (
                      <span className="pill" key={symbol}>{symbol}</span>
                    ))}
                  </div>
                </article>

                <article className="subpanel">
                  <div className="subpanel-header">
                    <h3>PNL PERFORMANCE</h3>
                    <span className="pill">REALTIME</span>
                  </div>
                  <div className="drawer-grid" style={{ marginBottom: 0 }}>
                    <div>
                      <span className="mini-label">GROSS</span>
                      <strong style={{ color: deck.transactions.pnl_reported.candidate.realized_pnl_gross >= 0 ? 'var(--accent)' : 'var(--alert)' }}>
                        {deck.transactions.pnl_reported.candidate.realized_pnl_gross.toFixed(2)}
                      </strong>
                    </div>
                    <div>
                      <span className="mini-label">NET</span>
                      <strong style={{ color: deck.transactions.pnl_reported.candidate.realized_pnl_net >= 0 ? 'var(--accent)' : 'var(--alert)' }}>
                        {deck.transactions.pnl_reported.candidate.realized_pnl_net.toFixed(2)}
                      </strong>
                    </div>
                  </div>
                </article>
              </div>
            </>
          ) : null}
        </section>
      </main>

      {activeCard ? (
        <aside className="drawer">
          <div className="drawer-header">
            <div>
              <p className="panel-kicker">STRATEGY CARD</p>
              <h2>{activeCard.card_id}</h2>
              <p className="muted" style={{ fontFamily: 'IBM Plex Mono' }}>
                {activeCard.lane.toUpperCase()} · v{activeCard.card_version}
              </p>
            </div>
            <button className="ghost-button" onClick={() => setActiveCardId(null)} type="button">
              [CLOSE]
            </button>
          </div>

          {cardLoading && !cardDetail ? <div className="state-block">SCANNING ARCHIVES…</div> : null}

          {cardDetail ? (
            <>
              <div className="drawer-grid">
                <div>
                  <span className="mini-label">INTENTS</span>
                  <strong>{cardDetail.counts.intents}</strong>
                </div>
                <div>
                  <span className="mini-label">RISK DECISIONS</span>
                  <strong>
                    {cardDetail.counts.risk_allow}A / {cardDetail.counts.risk_block}B
                  </strong>
                </div>
              </div>

              {cardDetail.truth_notes.length > 0 ? (
                <div className="drawer-section">
                  <h3 className="mini-label">TRUTH NOTES</h3>
                  <ul className="truth-list">
                    {cardDetail.truth_notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="drawer-section">
                <h3 className="mini-label">EVIDENCE STACK</h3>
                <p className="muted" style={{ fontSize: '0.8rem', marginBottom: '16px' }}>SAMPLED OPERATIONAL DATA</p>

                <EvidenceList
                  title="INTENT"
                  rows={cardDetail.samples.intents}
                  getKey={(row, index) => getRowString(row, "intent_id") ?? `intent:${index}`}
                  renderPrimary={(row) => {
                    const side = getRowString(row, "side") ?? "?";
                    const symbol = getRowString(row, "symbol") ?? "?";
                    return `${side.toUpperCase()} ${symbol}`;
                  }}
                  renderSecondary={(row) => {
                    const reason = getRowString(row, "reason_code") ?? "unknown";
                    return `REASON=${reason}`;
                  }}
                  renderMeta={(row) => {
                    const when = getRowString(row, "intent_time_utc");
                    return when ? new Date(when).toLocaleTimeString([], { hour12: false }) : "";
                  }}
                />

                <EvidenceList
                  title="RISK"
                  rows={cardDetail.samples.risk_decisions}
                  getKey={(row, index) => getRowString(row, "risk_decision_id") ?? `risk:${index}`}
                  renderPrimary={(row) => {
                    const decision = getRowString(row, "decision") ?? "?";
                    const reason = getRowString(row, "reason_code") ?? "unknown";
                    return `${decision.toUpperCase()} ${reason}`;
                  }}
                  renderSecondary={(row) => {
                    const policy = getRowString(row, "policy_name") ?? "?";
                    return `POLICY=${policy}`;
                  }}
                  renderMeta={(row) => {
                    const when = getRowString(row, "decision_time_utc");
                    return when ? new Date(when).toLocaleTimeString([], { hour12: false }) : "";
                  }}
                />
              </div>

              <details className="drawer-section">
                <summary className="mini-label" style={{ cursor: 'pointer' }}>[RAW PAYLOADS]</summary>
                <pre className="json-block">{JSON.stringify(cardDetail.samples, null, 2)}</pre>
              </details>
            </>
          ) : null}
        </aside>
      ) : null}

      {activeEvent ? (
        <aside className="drawer drawer-right">
          <div className="drawer-header">
            <div>
              <p className="panel-kicker">EVIDENCE ARCHIVE</p>
              <h2>{activeEvent.title.toUpperCase()}</h2>
              <p className="muted" style={{ fontFamily: 'IBM Plex Mono' }}>{activeEvent.subtitle}</p>
            </div>
            <button className="ghost-button" onClick={() => setActiveEventKey(null)} type="button">
              [CLOSE]
            </button>
          </div>
          <p className="drawer-meta" style={{ fontFamily: 'IBM Plex Mono', fontSize: '0.8rem' }}>
            {formatTimestamp(activeEvent.timestamp)} · {activeEvent.lane.toUpperCase()} · {activeEvent.kind.toUpperCase()}
            {activeEvent.symbol ? ` · ${activeEvent.symbol}` : ""}
          </p>

          {activeEvent.card_id && deck?.strategy.cards.some((card) => card.id === `${activeEvent.lane}:${activeEvent.card_id}`) ? (
            <div className="drawer-section">
              <h3 className="mini-label">RELATED CARD</h3>
              <button
                type="button"
                className="link-row"
                style={{ fontFamily: 'IBM Plex Mono' }}
                onClick={() => setActiveCardId(`${activeEvent.lane}:${activeEvent.card_id}`)}
              >
                {"> OPEN "}{activeEvent.lane.toUpperCase()}:{activeEvent.card_id}
              </button>
            </div>
          ) : null}

          {!activeEvent.card_id && deck ? (
            <div className="drawer-section">
              <h3 className="mini-label">LANE IMPLICATIONS</h3>
              <p className="muted" style={{ fontSize: '0.8rem', marginBottom: '12px' }}>Operational cards in this lane segment:</p>
              <div className="lane-card-links">
                {deck.strategy.cards
                  .filter((card) => card.lane === activeEvent.lane)
                  .slice(0, 6)
                  .map((card) => (
                    <button key={card.id} type="button" className="link-row" style={{ fontFamily: 'IBM Plex Mono' }} onClick={() => setActiveCardId(card.id)}>
                      {card.card_id} [E:{card.execution_request_count} A:{card.allowed_risk_count}]
                    </button>
                  ))}
              </div>
            </div>
          ) : null}

          <div className="drawer-section">
            <h3 className="mini-label">PAYLOAD SUMMARY</h3>
            <KeyValueGrid items={evidenceSummaryItems} />
          </div>

          <details className="drawer-section">
            <summary className="mini-label" style={{ cursor: 'pointer' }}>[RAW EVENT DATA]</summary>
            <pre className="json-block">{JSON.stringify(activeEvent.details, null, 2)}</pre>
          </details>
        </aside>
      ) : null}
    </div>
  );
}

export default App;
