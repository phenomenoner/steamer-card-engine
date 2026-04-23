import { CandlestickSeries, createChart, createSeriesMarkers, type IChartApi, type ISeriesApi, type CandlestickData, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

type FreshnessState = "fresh" | "lagging" | "stale" | "degraded";

type ObserverSession = {
  session_id: string;
  engine_id: string;
  symbol: string;
  market_mode: string;
  freshness_state: FreshnessState;
};

type Candle = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type ChartMarker = {
  time: string;
  position: "aboveBar" | "belowBar" | "inBar";
  shape: "arrowUp" | "arrowDown" | "circle" | "square";
  color: string;
  text: string;
  event_id: string;
};

type PositionSummary = {
  side: string;
  quantity: number;
  avg_price: number | null;
  market_price: number | null;
  unrealized_pnl: number | null;
  realized_pnl: number | null;
};

type OrderSummary = {
  order_id: string;
  status: string;
  side: string;
  quantity: number;
  limit_price: number | null;
  filled_quantity: number;
  submitted_at: string;
};

type FillSummary = {
  fill_id: string;
  side: string;
  quantity: number;
  price: number;
  filled_at: string;
};

type HealthSummary = {
  engine_state: string;
  feed_freshness_seconds: number;
  freshness_state: FreshnessState;
  incidents: string[];
};

type TimelineEntry = {
  seq: number;
  event_time: string;
  event_type: string;
  title: string;
  summary: string;
  freshness_state: FreshnessState;
  status: string;
};

type ObserverBootstrap = {
  schema_version: string;
  session_id: string;
  engine_id: string;
  session_label: string;
  market_mode: string;
  symbol: string;
  timeframe: string;
  generated_at: string;
  latest_seq: number;
  freshness_state: FreshnessState;
  chart: {
    candles: Candle[];
    markers: ChartMarker[];
    position_band: { side: string; avg_price: number; last_price: number };
  };
  position: PositionSummary;
  open_orders: OrderSummary[];
  last_fill: FillSummary | null;
  health: HealthSummary;
  timeline: TimelineEntry[];
};

type ObserverEvent = {
  schema_version: string;
  session_id: string;
  engine_id: string;
  seq: number;
  event_id: string;
  event_type: string;
  event_time: string;
  ingest_time: string;
  partial_data: Record<string, unknown>;
  freshness_state: FreshnessState;
};

type ObserverState = {
  session: ObserverSession | null;
  bootstrap: ObserverBootstrap | null;
  timeline: TimelineEntry[];
  events: ObserverEvent[];
  latestSeq: number;
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} -> ${response.status}`);
  return response.json() as Promise<T>;
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Taipei",
  });
}

function toUtcTimestamp(value: string): UTCTimestamp {
  return Math.floor(new Date(value).getTime() / 1000) as UTCTimestamp;
}

function toBarTime(value: string): string {
  return `${value.slice(0, 16)}:00Z`;
}

function tone(value: FreshnessState) {
  if (value === "fresh") return "accent";
  if (value === "lagging") return "muted";
  return "alert";
}

function applyObserverEvent(state: ObserverState, event: ObserverEvent): ObserverState {
  if (event.seq <= state.latestSeq || !state.bootstrap) return state;

  const timelineEntry: TimelineEntry = {
    seq: event.seq,
    event_time: event.event_time,
    event_type: event.event_type,
    title: String(event.partial_data.title ?? event.event_type),
    summary: String(event.partial_data.summary ?? ""),
    freshness_state: event.freshness_state,
    status: event.freshness_state === "fresh" ? "ok" : "warn",
  };

  const nextBootstrap: ObserverBootstrap = {
    ...state.bootstrap,
    latest_seq: event.seq,
    freshness_state: event.freshness_state,
    timeline: [timelineEntry, ...state.bootstrap.timeline].slice(0, 12),
    health: {
      ...state.bootstrap.health,
      freshness_state: event.freshness_state,
      feed_freshness_seconds:
        typeof event.partial_data.feed_freshness_seconds === "number"
          ? event.partial_data.feed_freshness_seconds
          : state.bootstrap.health.feed_freshness_seconds,
      incidents:
        typeof event.partial_data.incident === "string"
          ? [...state.bootstrap.health.incidents, event.partial_data.incident].slice(-12)
          : state.bootstrap.health.incidents,
    },
  };

  if (event.event_type === "candle_bar" && event.partial_data.candle) {
    nextBootstrap.chart = {
      ...nextBootstrap.chart,
      candles: [...nextBootstrap.chart.candles, event.partial_data.candle as Candle]
        .sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime())
        .slice(-200),
    };
  }

  if (event.event_type === "order_submitted") {
    const order = event.partial_data.order as OrderSummary | undefined;
    if (order) {
      nextBootstrap.open_orders = [order, ...nextBootstrap.open_orders.filter((item) => item.order_id !== order.order_id)];
      nextBootstrap.chart = {
        ...nextBootstrap.chart,
        markers: [
          ...nextBootstrap.chart.markers,
          {
            time: toBarTime(event.event_time),
            position: order.side === "sell" ? "aboveBar" : "belowBar",
            shape: order.side === "sell" ? "arrowDown" : "arrowUp",
            color: order.side === "sell" ? "#ff6b6b" : "#5ef3b1",
            text: `${String(order.side).toUpperCase()} SUBMIT`,
            event_id: event.event_id,
          },
        ],
      };
    }
  }

  if (event.event_type === "fill_received") {
    const fill = event.partial_data.fill as FillSummary | undefined;
    if (fill) {
      nextBootstrap.last_fill = fill;
      nextBootstrap.chart = {
        ...nextBootstrap.chart,
        markers: [
          ...nextBootstrap.chart.markers,
          {
            time: toBarTime(event.event_time),
            position: fill.side === "sell" ? "aboveBar" : "belowBar",
            shape: "circle",
            color: fill.side === "sell" ? "#ffcd81" : "#80c2ff",
            text: `FILL ${fill.quantity}`,
            event_id: event.event_id,
          },
        ],
      };
    }
  }

  if (event.event_type === "position_updated") {
    const position = event.partial_data.position as PositionSummary | undefined;
    if (position) nextBootstrap.position = position;
  }

  return {
    ...state,
    bootstrap: nextBootstrap,
    timeline: [timelineEntry, ...state.timeline].slice(0, 20),
    events: [...state.events, event],
    latestSeq: event.seq,
  };
}

function ObserverChart({ candles, markers }: { candles: Candle[]; markers: ChartMarker[] }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [chartError, setChartError] = useState<string | null>(null);

  useEffect(() => {
    if (!hostRef.current) return;
    try {
      const chart = createChart(hostRef.current, {
        autoSize: true,
        layout: { background: { color: "#0a1016" }, textColor: "#8ba8bb" },
        grid: { vertLines: { color: "rgba(141,170,186,0.08)" }, horzLines: { color: "rgba(141,170,186,0.08)" } },
        timeScale: { timeVisible: true, secondsVisible: true, borderColor: "rgba(141,170,186,0.2)" },
        rightPriceScale: { borderColor: "rgba(141,170,186,0.2)" },
        crosshair: { vertLine: { color: "rgba(94,243,177,0.3)" }, horzLine: { color: "rgba(94,243,177,0.3)" } },
      });
      const series = chart.addSeries(CandlestickSeries, {
        upColor: "#5ef3b1",
        downColor: "#ff6b6b",
        borderVisible: false,
        wickUpColor: "#5ef3b1",
        wickDownColor: "#ff6b6b",
      });
      chartRef.current = chart;
      seriesRef.current = series;
      setChartError(null);
      return () => chart.remove();
    } catch (error) {
      setChartError(error instanceof Error ? error.message : String(error));
      return;
    }
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !chartRef.current) return;
    try {
      const data: CandlestickData[] = candles
        .filter((candle) => [candle.open, candle.high, candle.low, candle.close].every((value) => Number.isFinite(value)))
        .map((candle) => ({
          time: toUtcTimestamp(candle.time),
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
        }));
      seriesRef.current.setData(data);
      createSeriesMarkers(
        seriesRef.current,
        [...markers]
          .filter((marker) => marker.time && marker.position && marker.shape)
          .sort((left, right) => new Date(left.time).getTime() - new Date(right.time).getTime())
          .map((marker) => ({
            time: toUtcTimestamp(marker.time),
            position: marker.position,
            shape: marker.shape,
            color: marker.color,
            text: marker.text,
          })),
      );
      chartRef.current.timeScale().fitContent();
      setChartError(null);
    } catch (error) {
      setChartError(error instanceof Error ? error.message : String(error));
    }
  }, [candles, markers]);

  if (chartError) {
    return <div className="state-block text-alert">CHART ERROR: {chartError}</div>;
  }

  return <div className="observer-chart" ref={hostRef} />;
}

function InfoCard({ label, value, subvalue }: { label: string; value: string; subvalue?: string }) {
  return (
    <article className="metric-card observer-metric-card">
      <span className="mini-label">{label}</span>
      <strong>{value}</strong>
      {subvalue ? <p>{subvalue}</p> : null}
    </article>
  );
}

export function ObserverSurface() {
  const [state, setState] = useState<ObserverState>({ session: null, bootstrap: null, timeline: [], events: [], latestSeq: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let cancelled = false;

    async function load() {
      try {
        const sessions = await getJson<{ items: ObserverSession[] }>("/api/observer/sessions");
        const session = sessions.items[0];
        const bootstrap = await getJson<ObserverBootstrap>(`/api/observer/sessions/${session.session_id}/bootstrap`);
        if (cancelled) return;
        setState({
          session,
          bootstrap,
          timeline: bootstrap.timeline,
          events: [],
          latestSeq: bootstrap.latest_seq,
        });
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        socket = new WebSocket(`${protocol}://${window.location.host}/api/observer/sessions/${session.session_id}/stream?after_seq=${bootstrap.latest_seq}`);
        socket.onmessage = (message) => {
          const payload = JSON.parse(message.data);
          if (payload.type === "stream_end") return;
          setState((current) => applyObserverEvent(current, payload as ObserverEvent));
        };
      } catch (reason) {
        setError(String(reason));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
      socket?.close();
    };
  }, []);

  const freshnessClass = useMemo(() => tone(state.bootstrap?.freshness_state ?? "fresh"), [state.bootstrap?.freshness_state]);

  if (loading) return <div className="state-block">Loading observer sidecar…</div>;
  if (error) return <div className="state-block text-alert">ERROR: {error}</div>;
  if (!state.bootstrap || !state.session) return <div className="state-block">Observer bootstrap unavailable.</div>;

  const bootstrap = state.bootstrap;

  return (
    <main className="observer-surface">
      <section className="panel observer-hero-panel">
        <div className="panel-header">
          <h3>Live Observer Sidecar</h3>
          <span className={`status-chip status-chip-${freshnessClass}`}>{bootstrap.freshness_state.toUpperCase()}</span>
        </div>
        <div className="panel-body observer-hero-body">
          <div>
            <div className="observer-title-row">
              <h2>{bootstrap.session_label}</h2>
              <span className="pill">{bootstrap.market_mode}</span>
            </div>
            <p className="strategy-note">One browser-openable sanitized observer for a single engine instance. Read-only by structure.</p>
          </div>
          <div className="observer-top-meta">
            <div><span className="mini-label">symbol</span><strong>{bootstrap.symbol}</strong></div>
            <div><span className="mini-label">timeframe</span><strong>{bootstrap.timeframe}</strong></div>
            <div><span className="mini-label">engine</span><strong>{bootstrap.engine_id}</strong></div>
            <div><span className="mini-label">generated</span><strong>{formatTimestamp(bootstrap.generated_at)}</strong></div>
          </div>
        </div>
      </section>

      <div className="metrics-row observer-metrics-row">
        <InfoCard label="engine state" value={bootstrap.health.engine_state.toUpperCase()} subvalue={`freshness ${bootstrap.health.feed_freshness_seconds}s`} />
        <InfoCard label="position" value={`${bootstrap.position.side.toUpperCase()} ${bootstrap.position.quantity}`} subvalue={`avg ${bootstrap.position.avg_price ?? "—"}`} />
        <InfoCard label="last fill" value={bootstrap.last_fill ? `${bootstrap.last_fill.side.toUpperCase()} ${bootstrap.last_fill.quantity}` : "NONE"} subvalue={bootstrap.last_fill ? `${bootstrap.last_fill.price} @ ${formatTimestamp(bootstrap.last_fill.filled_at)}` : "No fills yet"} />
        <InfoCard label="open orders" value={String(bootstrap.open_orders.length)} subvalue={bootstrap.open_orders[0] ? `${bootstrap.open_orders[0].status} · ${bootstrap.open_orders[0].side}` : "No working orders"} />
      </div>

      <div className="observer-grid">
        <section className="panel observer-chart-panel">
          <div className="panel-header">
            <h3>Chart + Markers</h3>
            <span className="pill">snapshot + stream reconcile</span>
          </div>
          <div className="panel-body observer-chart-wrap">
            <ObserverChart candles={bootstrap.chart.candles} markers={bootstrap.chart.markers} />
          </div>
        </section>

        <aside className="observer-right-rail">
          <section className="panel">
            <div className="panel-header"><h3>Position</h3><span className="pill">live(sim)</span></div>
            <div className="panel-body">
              <div className="kv-grid observer-kv-grid">
                <div className="kv-item"><span className="mini-label">side</span><strong>{bootstrap.position.side}</strong></div>
                <div className="kv-item"><span className="mini-label">qty</span><strong>{bootstrap.position.quantity}</strong></div>
                <div className="kv-item"><span className="mini-label">avg</span><strong>{bootstrap.position.avg_price ?? "—"}</strong></div>
                <div className="kv-item"><span className="mini-label">mark</span><strong>{bootstrap.position.market_price ?? "—"}</strong></div>
                <div className="kv-item"><span className="mini-label">uPnL</span><strong>{bootstrap.position.unrealized_pnl ?? "—"}</strong></div>
                <div className="kv-item"><span className="mini-label">rPnL</span><strong>{bootstrap.position.realized_pnl ?? "—"}</strong></div>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-header"><h3>Orders / Fill</h3><span className="pill">sanitized</span></div>
            <div className="panel-body observer-list-panel">
              {bootstrap.open_orders.map((order) => (
                <div className="history-item" key={order.order_id}>
                  <div className="history-item-head"><div><div className="card-title history-title">{order.order_id}</div><div className="card-meta">{order.side} · qty {order.quantity}</div></div><span className="status-chip status-chip-muted">{order.status}</span></div>
                  <p className="card-meta">limit {order.limit_price ?? "mkt"} · filled {order.filled_quantity}</p>
                </div>
              ))}
              {bootstrap.last_fill ? (
                <div className="history-item history-item-highlight">
                  <div className="history-item-head"><div><div className="card-title history-title">{bootstrap.last_fill.fill_id}</div><div className="card-meta">{formatTimestamp(bootstrap.last_fill.filled_at)}</div></div><span className="status-chip status-chip-accent">fill</span></div>
                  <p className="card-meta">{bootstrap.last_fill.side} · {bootstrap.last_fill.quantity} @ {bootstrap.last_fill.price}</p>
                </div>
              ) : null}
            </div>
          </section>

          <section className="panel">
            <div className="panel-header"><h3>Health Strip</h3><span className={`status-chip status-chip-${freshnessClass}`}>{bootstrap.health.freshness_state}</span></div>
            <div className="panel-body observer-list-panel">
              <div className="kv-grid observer-kv-grid observer-health-grid">
                <div className="kv-item"><span className="mini-label">feed lag</span><strong>{bootstrap.health.feed_freshness_seconds}s</strong></div>
                <div className="kv-item"><span className="mini-label">incidents</span><strong>{bootstrap.health.incidents.length}</strong></div>
                <div className="kv-item"><span className="mini-label">latest seq</span><strong>{state.latestSeq}</strong></div>
              </div>
              {bootstrap.health.incidents.map((incident) => <div className="observer-incident" key={incident}>{incident}</div>)}
            </div>
          </section>
        </aside>
      </div>

      <section className="panel">
        <div className="panel-header">
          <h3>Decision / Event Timeline</h3>
          <span className="pill">append only</span>
        </div>
        <div className="panel-body observer-timeline-grid">
          {state.timeline.map((item) => (
            <article className="history-item" key={item.seq}>
              <div className="history-item-head">
                <div>
                  <div className="card-title history-title">#{item.seq} · {item.title}</div>
                  <div className="card-meta">{formatTimestamp(item.event_time)} · {item.event_type}</div>
                </div>
                <span className={`status-chip status-chip-${tone(item.freshness_state)}`}>{item.status}</span>
              </div>
              <p className="card-meta">{item.summary}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
