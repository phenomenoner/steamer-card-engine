import { startTransition, useEffect, useState } from "react";

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
};

type Summary = {
  date: string;
  hero_day: boolean;
  scenario_id: string;
  scenario_fingerprint: string;
  compare_status: string;
  compare_version: string;
  dominant_lane: string;
  dominant_card: string | null;
  dominant_card_label: string | null;
  anomaly_total: number;
  event_total: number;
  execution_request_total: number;
  intent_total: number;
  transaction_state: string;
  lanes: Array<{
    lane: string;
    run_id: string;
    status: string;
    started_at_utc: string;
    ended_at_utc: string;
    counts: Record<string, number>;
    entry_count: number;
    realized_pnl_net: number;
    anomaly_count: number;
    bundle_relpath: string;
  }>;
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
  status: string;
  details: Record<string, unknown>;
};

type EventsData = {
  date: string;
  fixture: {
    comparison_relpath: string;
  };
  event_timeline: TimelineEvent[];
  anomalies: Array<{
    anomaly_id: string;
    category: string;
    detected_at_utc: string;
    message: string;
    severity: string;
    lane: string;
  }>;
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

type SnapshotResponse = {
  date: string;
  snapshot_id: string;
  payload: Record<string, unknown>;
};

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

function App() {
  const [dates, setDates] = useState<DateItem[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [cards, setCards] = useState<CardSummary[]>([]);
  const [compare, setCompare] = useState<CompareData | null>(null);
  const [events, setEvents] = useState<EventsData | null>(null);
  const [transactions, setTransactions] = useState<TransactionsData | null>(null);
  const [scenarioSnapshot, setScenarioSnapshot] = useState<SnapshotResponse | null>(null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [activeEventKey, setActiveEventKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
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
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
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
    setLoading(true);
    setError(null);

    Promise.all([
      getJson<Summary>(`/api/days/${selectedDate}/summary`),
      getJson<CardSummary[]>(`/api/days/${selectedDate}/cards`),
      getJson<CompareData>(`/api/days/${selectedDate}/compare`),
      getJson<EventsData>(`/api/days/${selectedDate}/events`),
      getJson<TransactionsData>(`/api/days/${selectedDate}/transactions`),
      getJson<SnapshotResponse>(`/api/days/${selectedDate}/snapshots/scenario`),
    ])
      .then(([summaryPayload, cardsPayload, comparePayload, eventsPayload, transactionsPayload, scenarioPayload]) => {
        if (cancelled) {
          return;
        }
        setSummary(summaryPayload);
        setCards(cardsPayload);
        setCompare(comparePayload);
        setEvents(eventsPayload);
        setTransactions(transactionsPayload);
        setScenarioSnapshot(scenarioPayload);
        setActiveCardId(cardsPayload[0]?.id ?? null);
        setActiveEventKey(eventsPayload.event_timeline[0]?.event_key ?? null);
      })
      .catch((reason) => {
        if (!cancelled) {
          setError(String(reason));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedDate]);

  const activeCard = cards.find((card) => card.id === activeCardId) ?? null;
  const activeEvent = events?.event_timeline.find((event) => event.event_key === activeEventKey) ?? null;

  return (
    <div className="page-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      <header className="hero">
        <div>
          <p className="eyebrow">Steamer Card Engine</p>
          <h1>Mission Control Dashboard</h1>
          <p className="hero-copy">
            Read-only battle report over the committed March replay fixtures. No broker control plane, no fabricated trade data.
          </p>
        </div>
        <div className="hero-chip-cluster">
          <span className="chip">Fixture Set 20260306 / 20260310 / 20260312</span>
          <span className="chip chip-accent">Topology Unchanged</span>
        </div>
      </header>

      <main className="dashboard-grid">
        <section className="panel panel-history">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">History</p>
              <h2>March demo fixtures</h2>
            </div>
          </div>
          <div className="date-list">
            {dates.map((date) => (
              <button
                key={date.date}
                className={`date-tile ${selectedDate === date.date ? "date-tile-active" : ""}`}
                onClick={() =>
                  startTransition(() => {
                    setSelectedDate(date.date);
                  })
                }
                type="button"
              >
                <div className="date-tile-head">
                  <strong>{formatDate(date.date)}</strong>
                  {date.hero ? <span className="badge badge-hero">Hero</span> : null}
                </div>
                <div className="date-meta">
                  <span>{date.compare_status}</span>
                  <span>{date.dominant_lane}</span>
                  <span>{date.anomaly_count} anomaly</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="panel panel-command">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Daily Command View</p>
              <h2>{summary ? formatDate(summary.date) : "Loading day"}</h2>
            </div>
            {summary ? <span className="badge">{summary.compare_status}</span> : null}
          </div>

          {loading && !summary ? <div className="state-block">Loading March mission-control bundle…</div> : null}
          {error ? <div className="state-block state-error">{error}</div> : null}

          {summary && compare && transactions ? (
            <>
              <div className="command-strip">
                <article className="metric-card">
                  <span className="metric-label">Dominant lane</span>
                  <strong>{summary.dominant_lane}</strong>
                  <p>{summary.dominant_card_label ?? "No dominant card resolved"}</p>
                </article>
                <article className="metric-card">
                  <span className="metric-label">Anomalies</span>
                  <strong>{summary.anomaly_total}</strong>
                  <p>Minor-only across both lanes in the committed March set.</p>
                </article>
                <article className="metric-card">
                  <span className="metric-label">Event pressure</span>
                  <strong>{formatNumber(summary.event_total)}</strong>
                  <p>{formatNumber(summary.execution_request_total)} execution shells</p>
                </article>
                <article className="metric-card">
                  <span className="metric-label">Transaction truth</span>
                  <strong>{transactions.empty_state_metadata.state}</strong>
                  <p>{transactions.empty_state_metadata.empty_reason}</p>
                </article>
              </div>

              <div className="two-up">
                <article className="subpanel">
                  <div className="subpanel-header">
                    <h3>Compare posture</h3>
                    <span className="muted">{compare.compare_version}</span>
                  </div>
                  <div className="compare-grid">
                    <div>
                      <span className="mini-label">Intents</span>
                      <strong>
                        {compare.counts.intents.baseline} / {compare.counts.intents.candidate}
                      </strong>
                    </div>
                    <div>
                      <span className="mini-label">Risk decisions</span>
                      <strong>
                        {compare.counts.risk_decisions.baseline} / {compare.counts.risk_decisions.candidate}
                      </strong>
                    </div>
                    <div>
                      <span className="mini-label">Orders</span>
                      <strong>
                        {compare.counts.orders.baseline} / {compare.counts.orders.candidate}
                      </strong>
                    </div>
                    <div>
                      <span className="mini-label">Fills</span>
                      <strong>
                        {compare.counts.fills.baseline} / {compare.counts.fills.candidate}
                      </strong>
                    </div>
                  </div>
                  <p className="subpanel-note">
                    Compare artifacts pass, but scaffold placeholders remain for exit reasons, exposure, and per-symbol totals.
                  </p>
                </article>

                <article className="subpanel">
                  <div className="subpanel-header">
                    <h3>Scenario receipt</h3>
                    <span className="muted">Read-only</span>
                  </div>
                  <p className="scenario-id">{summary.scenario_id}</p>
                  <p className="fingerprint">{summary.scenario_fingerprint}</p>
                  <p className="subpanel-note">
                    {scenarioSnapshot ? JSON.stringify(scenarioSnapshot.payload.session_slice) : "Loading scenario slice…"}
                  </p>
                </article>
              </div>
            </>
          ) : null}
        </section>

        <section className="panel panel-cards">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Blade 4</p>
              <h2>Strategy-card leaderboard</h2>
            </div>
          </div>
          <div className="leaderboard">
            {cards.map((card) => (
              <button
                key={card.id}
                className={`leaderboard-row ${activeCardId === card.id ? "leaderboard-row-active" : ""}`}
                onClick={() => setActiveCardId(card.id)}
                type="button"
              >
                <div>
                  <strong>{card.lane}</strong>
                  <p>{card.card_id}</p>
                </div>
                <div className="leaderboard-metrics">
                  <span>{card.execution_request_count} exec</span>
                  <span>{card.allowed_risk_count} allow</span>
                  <span>{card.blocked_risk_count} block</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="panel panel-events">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Blade 5</p>
              <h2>Replay and anomaly drilldown</h2>
            </div>
            {events ? <span className="muted">{events.event_timeline.length} timeline items</span> : null}
          </div>
          <div className="timeline">
            {events?.event_timeline.slice(0, 80).map((event) => (
              <button
                key={event.event_key}
                className={`timeline-row timeline-${event.status} ${
                  activeEventKey === event.event_key ? "timeline-row-active" : ""
                }`}
                onClick={() => setActiveEventKey(event.event_key)}
                type="button"
              >
                <div className="timeline-time">{formatTimestamp(event.timestamp)}</div>
                <div>
                  <strong>{event.title}</strong>
                  <p>
                    {event.lane} · {event.kind}
                    {event.symbol ? ` · ${event.symbol}` : ""}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="panel panel-transactions">
          <div className="panel-header">
            <div>
              <p className="panel-kicker">Blade 6</p>
              <h2>Transaction and PnL truth surface</h2>
            </div>
          </div>
          {transactions ? (
            <>
              <div className="transaction-grid">
                <article className="subpanel">
                  <h3>Compare counts</h3>
                  <div className="compare-grid">
                    <div>
                      <span className="mini-label">Orders</span>
                      <strong>{transactions.counts.orders.baseline + transactions.counts.orders.candidate}</strong>
                    </div>
                    <div>
                      <span className="mini-label">Fills</span>
                      <strong>{transactions.counts.fills.baseline + transactions.counts.fills.candidate}</strong>
                    </div>
                    <div>
                      <span className="mini-label">Gross PnL</span>
                      <strong>{transactions.pnl_reported.baseline.realized_pnl_gross.toFixed(2)}</strong>
                    </div>
                    <div>
                      <span className="mini-label">Net PnL</span>
                      <strong>{transactions.pnl_reported.candidate.realized_pnl_net.toFixed(2)}</strong>
                    </div>
                  </div>
                </article>
                <article className="subpanel subpanel-warning">
                  <h3>Truthful empty state</h3>
                  <p>{transactions.empty_state_metadata.empty_reason}</p>
                  <p className="subpanel-note">{transactions.empty_state_metadata.truth_note}</p>
                </article>
              </div>

              <div className="lane-table">
                {Object.entries(transactions.lanes).map(([lane, payload]) => (
                  <article className="lane-card" key={lane}>
                    <div className="subpanel-header">
                      <h3>{lane}</h3>
                      <span className="badge badge-muted">{payload.empty_state.is_empty ? "empty" : "partial"}</span>
                    </div>
                    <p>{payload.empty_state.truth_note}</p>
                    <div className="lane-stats">
                      <span>{payload.counts.execution_requests} execution shells</span>
                      <span>{String(payload.pnl_summary.entry_count)} entry shells</span>
                      <span>{String(payload.pnl_summary.realized_pnl_net)} net PnL</span>
                    </div>
                  </article>
                ))}
              </div>
            </>
          ) : null}
        </section>
      </main>

      {activeCard ? (
        <aside className="drawer">
          <div className="drawer-header">
            <div>
              <p className="panel-kicker">Card detail</p>
              <h2>{activeCard.card_id}</h2>
            </div>
            <button className="ghost-button" onClick={() => setActiveCardId(null)} type="button">
              Close
            </button>
          </div>
          <div className="drawer-grid">
            <div>
              <span className="mini-label">Lane</span>
              <strong>{activeCard.lane}</strong>
            </div>
            <div>
              <span className="mini-label">Deck</span>
              <strong>{activeCard.deck_id}</strong>
            </div>
            <div>
              <span className="mini-label">Intent count</span>
              <strong>{activeCard.intent_count}</strong>
            </div>
            <div>
              <span className="mini-label">Exec shells</span>
              <strong>{activeCard.execution_request_count}</strong>
            </div>
          </div>
          <div className="drawer-section">
            <h3>Reason distribution</h3>
            {activeCard.reason_distribution.map((item) => (
              <div className="pill-row" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
          <div className="drawer-section">
            <h3>Top symbols</h3>
            {activeCard.top_symbols.map((item) => (
              <div className="pill-row" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.count}</strong>
              </div>
            ))}
          </div>
        </aside>
      ) : null}

      {activeEvent ? (
        <aside className="drawer drawer-right">
          <div className="drawer-header">
            <div>
              <p className="panel-kicker">Event detail</p>
              <h2>{activeEvent.title}</h2>
            </div>
            <button className="ghost-button" onClick={() => setActiveEventKey(null)} type="button">
              Close
            </button>
          </div>
          <p className="drawer-meta">
            {formatTimestamp(activeEvent.timestamp)} · {activeEvent.lane} · {activeEvent.kind}
          </p>
          <pre className="json-block">{JSON.stringify(activeEvent.details, null, 2)}</pre>
        </aside>
      ) : null}
    </div>
  );
}

export default App;
