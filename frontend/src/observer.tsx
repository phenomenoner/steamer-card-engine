import { CandlestickSeries, createChart, createSeriesMarkers, type IChartApi, type ISeriesApi, type CandlestickData, type UTCTimestamp } from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";

type FreshnessState = "fresh" | "lagging" | "stale" | "degraded";
type StreamState = "idle" | "connecting" | "live" | "ended" | "closed" | "error";

const MARKER_LIMIT = 80;
const CHART_TIMEFRAMES = ["auto", "1m", "5m", "15m"] as const;
type ChartTimeframe = typeof CHART_TIMEFRAMES[number];

type ObserverSession = {
  session_id: string;
  engine_id: string;
  symbol: string;
  market_mode: string;
  freshness_state: FreshnessState;
  strategy_id?: string;
  strategy_label?: string;
  strategy_source_kind?: string;
  run_type?: string | null;
  scenario_id?: string | null;
  deck_id?: string | null;
  run_id?: string | null;
};

type ObserverSymbolPool = {
  source_kind: string;
  symbol_count: number;
  symbols: string[];
  top_symbols: string[];
  sample_symbols: string[];
};

type StrategyRun = {
  strategy_id: string;
  strategy_label: string;
  strategy_source_kind: string;
  symbols: string[];
  symbols_source_kind: string;
  session_ids: string[];
  session_ids_by_symbol: Record<string, string[]>;
  default_session_id?: string | null;
  run_type?: string | null;
  scenario_id?: string | null;
  deck_id?: string | null;
};

type ObserverSessionsPayload = {
  items: ObserverSession[];
  default_session_id?: string | null;
  symbol_pool?: Partial<ObserverSymbolPool>;
  session_ids_by_symbol?: Record<string, string[]>;
  strategy_runs?: StrategyRun[];
};

function symbolPoolLabel(sourceKind: string) {
  if (sourceKind === "observer-sessions-fallback") return "Mounted sessions fallback";
  if (sourceKind === "observer-bundle-metadata") return "Mounted bundle metadata (actual)";
  if (sourceKind.startsWith("observer-bundle-metadata:")) {
    return `Mounted bundle metadata (${sourceKind.slice("observer-bundle-metadata:".length)})`;
  }
  if (sourceKind.endsWith("-sample")) return "Fixture sample fallback";
  return `Pool source: ${sourceKind}`;
}

function symbolPoolSubcopy(sourceKind: string) {
  if (sourceKind === "observer-sessions-fallback") {
    return "Pool metadata missing. Universe is inferred from mounted sessions.";
  }
  if (sourceKind === "observer-bundle-metadata" || sourceKind.startsWith("observer-bundle-metadata:")) {
    return "Using mounted bundle metadata for actual run universe context.";
  }
  if (sourceKind.endsWith("-sample")) {
    return "Using fixture sample pool. Replace with mounted bundle metadata for live universe truth.";
  }
  return `Pool source: ${sourceKind}`;
}

function normalizeSymbolList(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  values.forEach((value) => {
    if (typeof value !== "string") return;
    const symbol = value.trim();
    if (!symbol || seen.has(symbol)) return;
    seen.add(symbol);
    out.push(symbol);
  });
  return out;
}

function normalizeSymbolSessionMap(value: unknown): Record<string, string[]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const entries = Object.entries(value as Record<string, unknown>);
  const normalized: Record<string, string[]> = {};
  entries.forEach(([symbol, sessionIds]) => {
    const key = typeof symbol === "string" ? symbol.trim() : "";
    if (!key) return;
    const ids = normalizeSymbolList(sessionIds);
    if (ids.length) normalized[key] = ids;
  });
  return normalized;
}

const OVERVIEW_VIEW_ID = "__overview__";

type HistorySession = ObserverSession & {
  source_kind: string;
  source_path_ref: string;
  date: string;
  generated_at: string;
  session_label: string;
  timeframe: string;
  scenario_id: string | null;
  deck_id: string | null;
  run_type: string;
  latest_seq: number;
  event_count: number;
  candle_count: number;
  has_compare: boolean;
  tags: string[];
  strategy_id?: string;
  strategy_label?: string;
  strategy_source_kind?: string;
  symbols?: string[];
  symbols_source_kind?: string;
};

type HistorySessionsPayload = {
  items: HistorySession[];
  strategy_runs?: StrategyRun[];
  session_ids_by_symbol?: Record<string, string[]>;
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
  provenance?: {
    source_kind: string;
    source_path_ref: string;
    compare_ref?: string | null;
    labels: string[];
  };
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
  streamState: StreamState;
  streamNote: string | null;
  sequenceGaps: Array<{ expected: number; received: number }>;
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

function formatChartTime(timestamp: UTCTimestamp | number): string {
  return new Date(Number(timestamp) * 1000).toLocaleString("en-US", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Taipei",
  });
}

function toBarTime(value: string): string {
  return `${value.slice(0, 16)}:00Z`;
}

function timeframeMinutes(timeframe: ChartTimeframe): number {
  if (timeframe === "5m") return 5;
  if (timeframe === "15m") return 15;
  return 1;
}

function bucketTime(value: string, timeframe: ChartTimeframe): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return toBarTime(value);
  const minutes = timeframeMinutes(timeframe);
  date.setUTCSeconds(0, 0);
  date.setUTCMinutes(Math.floor(date.getUTCMinutes() / minutes) * minutes);
  return date.toISOString().replace(".000Z", "Z");
}

function aggregateCandles(candles: Candle[], timeframe: ChartTimeframe): Candle[] {
  const buckets = new Map<string, Candle[]>();
  [...candles]
    .sort((left, right) => new Date(left.time).getTime() - new Date(right.time).getTime())
    .forEach((candle) => {
      const key = bucketTime(candle.time, timeframe);
      buckets.set(key, [...(buckets.get(key) ?? []), candle]);
    });

  return [...buckets.entries()].map(([time, values]) => ({
    time,
    open: values[0].open,
    high: Math.max(...values.map((item) => item.high)),
    low: Math.min(...values.map((item) => item.low)),
    close: values[values.length - 1].close,
    volume: values.reduce((total, item) => total + item.volume, 0),
  }));
}

function alignMarkers(markers: ChartMarker[], timeframe: ChartTimeframe): ChartMarker[] {
  return markers.map((marker) => ({ ...marker, time: bucketTime(marker.time, timeframe) }));
}

function TimeframeSelector({ value, onChange }: { value: ChartTimeframe; onChange: (value: ChartTimeframe) => void }) {
  return (
    <div className="timeframe-selector" aria-label="Chart timeframe">
      {CHART_TIMEFRAMES.map((timeframe) => (
        <button
          key={timeframe}
          type="button"
          className={value === timeframe ? "active" : ""}
          onClick={() => onChange(timeframe)}
        >
          {timeframe === "auto" ? "Auto" : timeframe}
        </button>
      ))}
    </div>
  );
}

function StrategySelector({
  strategies,
  value,
  onChange,
}: {
  strategies: StrategyRun[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="observer-session-selector" htmlFor="observer-strategy-select">
      <span className="mini-label">strategy</span>
      <select id="observer-strategy-select" value={value} onChange={(event) => onChange(event.target.value)}>
        {strategies.map((strategy) => (
          <option key={strategy.strategy_id} value={strategy.strategy_id}>
            {strategy.strategy_label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ViewSelector({
  symbols,
  value,
  onChange,
}: {
  symbols: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="observer-session-selector" htmlFor="observer-view-select">
      <span className="mini-label">view</span>
      <select id="observer-view-select" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value={OVERVIEW_VIEW_ID}>Overview (portfolio)</option>
        {symbols.map((symbol) => (
          <option key={symbol} value={symbol}>
            {symbol}
          </option>
        ))}
      </select>
    </label>
  );
}

function tone(value: FreshnessState) {
  if (value === "fresh") return "accent";
  if (value === "lagging") return "muted";
  return "alert";
}

function applyObserverEvent(state: ObserverState, event: ObserverEvent): ObserverState {
  if (event.seq <= state.latestSeq || !state.bootstrap) return state;
  const expectedSeq = state.latestSeq + 1;
  const sequenceGaps = event.seq > expectedSeq ? [...state.sequenceGaps, { expected: expectedSeq, received: event.seq }].slice(-8) : state.sequenceGaps;

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

  if (event.event_type === "data_gap_detected") {
    nextBootstrap.health = {
      ...nextBootstrap.health,
      feed_freshness_seconds:
        typeof event.partial_data.gap_seconds === "number"
          ? event.partial_data.gap_seconds
          : nextBootstrap.health.feed_freshness_seconds,
      incidents: [...nextBootstrap.health.incidents, "observer_gap_detected"].slice(-12),
    };
  }

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
        ].slice(-MARKER_LIMIT),
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
        ].slice(-MARKER_LIMIT),
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
    streamState: "live",
    streamNote: null,
    sequenceGaps,
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
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: "rgba(141,170,186,0.2)", tickMarkFormatter: (time) => formatChartTime(time as number) },
        localization: { timeFormatter: (time) => formatChartTime(time as number) },
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
  const [chartTimeframe, setChartTimeframe] = useState<ChartTimeframe>("auto");
  const [sessions, setSessions] = useState<ObserverSession[]>([]);
  const [strategies, setStrategies] = useState<StrategyRun[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [selectedView, setSelectedView] = useState<string>(OVERVIEW_VIEW_ID);
  const [symbolPool, setSymbolPool] = useState<ObserverSymbolPool | null>(null);
  const [sessionIdsBySymbol, setSessionIdsBySymbol] = useState<Record<string, string[]>>({});
  const [state, setState] = useState<ObserverState>({
    session: null,
    bootstrap: null,
    timeline: [],
    events: [],
    latestSeq: 0,
    streamState: "idle",
    streamNote: null,
    sequenceGaps: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasNoSession, setHasNoSession] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadSessions() {
      try {
        const payload = await getJson<ObserverSessionsPayload>("/api/observer/sessions");
        if (cancelled) return;
        const loadedSessions = payload.items ?? [];
        const fallbackSymbols = normalizeSymbolList(
          loadedSessions.map((item) => item.symbol).filter((item) => typeof item === "string" && item.length > 0),
        ).sort();
        const poolSymbols = normalizeSymbolList(payload.symbol_pool?.symbols ?? fallbackSymbols);
        const normalizedSessionMap = normalizeSymbolSessionMap(payload.session_ids_by_symbol);

        setSessions(loadedSessions);
        setSymbolPool({
          source_kind: payload.symbol_pool?.source_kind ?? "observer-sessions-fallback",
          symbol_count: payload.symbol_pool?.symbol_count ?? poolSymbols.length,
          symbols: poolSymbols,
          top_symbols: payload.symbol_pool?.top_symbols ?? fallbackSymbols.slice(0, 5),
          sample_symbols: payload.symbol_pool?.sample_symbols ?? fallbackSymbols.slice(0, 8),
        });
        setSessionIdsBySymbol(normalizedSessionMap);

        const strategyRunsFromApi = Array.isArray(payload.strategy_runs)
          ? payload.strategy_runs
              .map((run) => {
                const strategyId = typeof run.strategy_id === "string" ? run.strategy_id.trim() : "";
                if (!strategyId) return null;
                return {
                  strategy_id: strategyId,
                  strategy_label: typeof run.strategy_label === "string" && run.strategy_label.trim() ? run.strategy_label.trim() : strategyId,
                  strategy_source_kind:
                    typeof run.strategy_source_kind === "string" && run.strategy_source_kind.trim()
                      ? run.strategy_source_kind.trim()
                      : "observer-session-derived",
                  symbols: normalizeSymbolList(run.symbols),
                  symbols_source_kind:
                    typeof run.symbols_source_kind === "string" && run.symbols_source_kind.trim()
                      ? run.symbols_source_kind.trim()
                      : payload.symbol_pool?.source_kind ?? "observer-sessions-fallback",
                  session_ids: normalizeSymbolList(run.session_ids),
                  session_ids_by_symbol: normalizeSymbolSessionMap(run.session_ids_by_symbol),
                  default_session_id: typeof run.default_session_id === "string" ? run.default_session_id : null,
                } satisfies StrategyRun;
              })
              .filter((run): run is StrategyRun => Boolean(run))
          : [];

        const fallbackStrategies: StrategyRun[] = strategyRunsFromApi.length
          ? strategyRunsFromApi
          : (() => {
              const grouped = new Map<string, StrategyRun>();
              loadedSessions.forEach((session) => {
                const strategyId = (session.strategy_id && session.strategy_id.trim()) || `session:${session.session_id}`;
                if (!grouped.has(strategyId)) {
                  grouped.set(strategyId, {
                    strategy_id: strategyId,
                    strategy_label: (session.strategy_label && session.strategy_label.trim()) || `Session-derived (${session.session_id})`,
                    strategy_source_kind: (session.strategy_source_kind && session.strategy_source_kind.trim()) || "observer-session-derived",
                    symbols: [],
                    symbols_source_kind: payload.symbol_pool?.source_kind ?? "observer-sessions-fallback",
                    session_ids: [],
                    session_ids_by_symbol: {},
                    default_session_id: session.session_id,
                  });
                }
                const run = grouped.get(strategyId);
                if (!run) return;
                if (!run.session_ids.includes(session.session_id)) run.session_ids.push(session.session_id);
                const symbol = typeof session.symbol === "string" ? session.symbol.trim() : "";
                if (symbol) {
                  if (!run.symbols.includes(symbol)) run.symbols.push(symbol);
                  const ids = run.session_ids_by_symbol[symbol] ?? [];
                  if (!ids.includes(session.session_id)) run.session_ids_by_symbol[symbol] = [...ids, session.session_id];
                }
              });
              return [...grouped.values()];
            })();

        const normalizedStrategies = fallbackStrategies.map((run) => {
          const symbols = run.symbols.length ? run.symbols : (fallbackStrategies.length === 1 ? poolSymbols : []);
          return {
            ...run,
            symbols,
          };
        });
        setStrategies(normalizedStrategies);

        if (!loadedSessions.length) {
          if (!cancelled) setHasNoSession(true);
          setSelectedStrategyId(null);
          if (!cancelled) setLoading(false);
          return;
        }
        setHasNoSession(false);
        setSelectedStrategyId((current) => {
          if (current && normalizedStrategies.some((strategy) => strategy.strategy_id === current)) return current;
          const strategyForDefaultSession = normalizedStrategies.find((strategy) =>
            strategy.session_ids.includes(payload.default_session_id ?? ""),
          );
          return strategyForDefaultSession?.strategy_id ?? normalizedStrategies[0]?.strategy_id ?? null;
        });
        setSelectedView(OVERVIEW_VIEW_ID);
        setError(null);
      } catch (reason) {
        setError(String(reason));
        if (!cancelled) setLoading(false);
      }
    }

    void loadSessions();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedStrategy = useMemo(
    () => strategies.find((strategy) => strategy.strategy_id === selectedStrategyId) ?? null,
    [strategies, selectedStrategyId],
  );

  useEffect(() => {
    if (selectedView === OVERVIEW_VIEW_ID) return;
    if (selectedStrategy?.symbols.includes(selectedView)) return;
    setSelectedView(OVERVIEW_VIEW_ID);
  }, [selectedStrategy, selectedView]);

  const strategySummarySessionId = selectedStrategy?.default_session_id ?? selectedStrategy?.session_ids[0] ?? null;
  const selectedSymbol = selectedView === OVERVIEW_VIEW_ID ? null : selectedView;
  const mountedSymbolSessionId = selectedSymbol
    ? selectedStrategy?.session_ids_by_symbol[selectedSymbol]?.[0] ?? sessionIdsBySymbol[selectedSymbol]?.[0] ?? null
    : null;
  const hasMountedSymbolSession = Boolean(selectedSymbol && mountedSymbolSessionId);
  const isOverviewMode = selectedView === OVERVIEW_VIEW_ID;
  const activeSessionId = hasMountedSymbolSession ? mountedSymbolSessionId : strategySummarySessionId;

  useEffect(() => {
    if (!activeSessionId) {
      setState((current) => ({
        ...current,
        session: null,
        bootstrap: null,
        timeline: [],
        events: [],
        latestSeq: 0,
        streamState: "idle",
        streamNote: null,
        sequenceGaps: [],
      }));
      setLoading(false);
      return;
    }

    const session = sessions.find((item) => item.session_id === activeSessionId);
    if (!session) return;

    let socket: WebSocket | null = null;
    let cancelled = false;

    async function loadSelectedSession() {
      setLoading(true);
      try {
        const bootstrap = await getJson<ObserverBootstrap>(`/api/observer/sessions/${session.session_id}/bootstrap`);
        if (cancelled) return;
        setError(null);
        setState({
          session,
          bootstrap: { ...bootstrap, chart: { ...bootstrap.chart, markers: bootstrap.chart.markers.slice(-MARKER_LIMIT) } },
          timeline: bootstrap.timeline,
          events: [],
          latestSeq: bootstrap.latest_seq,
          streamState: "connecting",
          streamNote: null,
          sequenceGaps: [],
        });
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        socket = new WebSocket(`${protocol}://${window.location.host}/api/observer/sessions/${session.session_id}/stream?after_seq=${bootstrap.latest_seq}`);
        socket.onopen = () => {
          if (!cancelled) setState((current) => ({ ...current, streamState: "live", streamNote: null }));
        };
        socket.onmessage = (message) => {
          if (cancelled) return;
          try {
            const payload = JSON.parse(message.data) as { type?: string } | ObserverEvent;
            if ("type" in payload && payload.type === "stream_end") {
              if (cancelled) return;
              setState((current) => ({ ...current, streamState: "ended", streamNote: "stream_end received from observer API" }));
              return;
            }
            if (typeof (payload as ObserverEvent).seq !== "number") {
              throw new Error("stream payload missing numeric seq");
            }
            if (cancelled) return;
            setState((current) => applyObserverEvent(current, payload as ObserverEvent));
          } catch (reason) {
            if (cancelled) return;
            setState((current) => ({
              ...current,
              streamState: "error",
              streamNote: `Malformed stream payload ignored: ${reason instanceof Error ? reason.message : String(reason)}`,
            }));
          }
        };
        socket.onerror = () => {
          if (!cancelled) setState((current) => ({ ...current, streamState: "error", streamNote: "websocket error" }));
        };
        socket.onclose = () => {
          if (!cancelled) setState((current) => (current.streamState === "ended" ? current : { ...current, streamState: "closed", streamNote: "websocket closed" }));
        };
      } catch (reason) {
        if (!cancelled) setError(String(reason));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadSelectedSession();
    return () => {
      cancelled = true;
      socket?.close();
    };
  }, [activeSessionId, sessions]);

  const freshnessClass = useMemo(() => tone(state.bootstrap?.freshness_state ?? "fresh"), [state.bootstrap?.freshness_state]);
  const needsAttention = state.bootstrap?.freshness_state && state.bootstrap.freshness_state !== "fresh";
  const isStreamDegraded = state.streamState === "error" || state.streamState === "closed" || state.sequenceGaps.length > 0;
  const effectivePool = useMemo(() => {
    const fallbackSymbols = normalizeSymbolList(
      sessions.map((item) => item.symbol).filter((item) => typeof item === "string" && item.length > 0),
    ).sort();
    if (symbolPool) return symbolPool;
    return {
      source_kind: "observer-sessions-fallback",
      symbol_count: fallbackSymbols.length,
      symbols: fallbackSymbols,
      top_symbols: fallbackSymbols.slice(0, 5),
      sample_symbols: fallbackSymbols.slice(0, 8),
    };
  }, [sessions, symbolPool]);

  const viewSymbols = selectedStrategy?.symbols.length ? selectedStrategy.symbols : effectivePool.symbols;
  const activeSession = state.session;

  if (loading && !state.bootstrap) return <div className="state-block">Loading observer sidecar…</div>;
  if (error) return <div className="state-block text-alert">ERROR: {error}</div>;
  if (hasNoSession) return <div className="state-block observer-empty-state"><strong>No observer session mounted.</strong><span>Set STEAMER_OBSERVER_BUNDLE_JSON or enable a mock session, then refresh this read-only surface.</span></div>;
  if (!selectedStrategy) return <div className="state-block">Strategy selector unavailable.</div>;
  if (!state.bootstrap) return <div className="state-block">Observer bootstrap unavailable.</div>;

  const bootstrap = state.bootstrap;
  const chartCandles = aggregateCandles(bootstrap.chart.candles, chartTimeframe);
  const chartMarkers = alignMarkers(bootstrap.chart.markers.slice(-MARKER_LIMIT), chartTimeframe);
  const poolSourceLabel = symbolPoolLabel(effectivePool.source_kind);
  const poolSubcopy = symbolPoolSubcopy(effectivePool.source_kind);
  const universeSymbols = effectivePool.symbols.length ? effectivePool.symbols : (effectivePool.sample_symbols.length ? effectivePool.sample_symbols : effectivePool.top_symbols);
  const missingSymbolSelection = Boolean(selectedSymbol) && !hasMountedSymbolSession;

  return (
    <main className="observer-surface">
      <section className="panel observer-status-strip">
        <div className="panel-header">
          <h3>Observer Status</h3>
          <div className="observer-chip-row">
            <span className={`status-chip status-chip-${state.streamState === "live" ? "accent" : state.streamState === "connecting" || state.streamState === "ended" ? "muted" : "alert"}`}>WS {state.streamState.toUpperCase()}</span>
            <span className={`status-chip status-chip-${freshnessClass}`}>{bootstrap.freshness_state.toUpperCase()}</span>
            <span className={`status-chip status-chip-${state.sequenceGaps.length ? "alert" : "muted"}`}>SEQ GAPS {state.sequenceGaps.length}</span>
          </div>
        </div>
        <div className="panel-body observer-status-body observer-top-meta">
          <div><span className="mini-label">latest seq</span><strong>{state.latestSeq}</strong></div>
          <div><span className="mini-label">feed lag</span><strong>{bootstrap.health.feed_freshness_seconds}s</strong></div>
          <div><span className="mini-label">generated</span><strong>{formatTimestamp(bootstrap.generated_at)}</strong></div>
          <div><span className="mini-label">stream note</span><strong>{state.streamNote ?? "none"}</strong></div>
        </div>
        {needsAttention || isStreamDegraded ? (
          <div className="observer-alert-banner">
            <strong>Observer attention needed</strong>
            <span>
              freshness={bootstrap.freshness_state}; websocket={state.streamState}
              {state.sequenceGaps[0] ? `; sequence gap expected ${state.sequenceGaps[0].expected}, received ${state.sequenceGaps[0].received}` : ""}
              {state.streamNote ? `; ${state.streamNote}` : ""}
            </span>
          </div>
        ) : null}
      </section>

      <section className="panel observer-universe-card">
        <div className="panel-header">
          <h3>Symbol Universe</h3>
          <div className="observer-chip-row">
            <span className="pill">{effectivePool.symbol_count} symbols</span>
            <span className="status-chip status-chip-muted">{poolSourceLabel}</span>
          </div>
        </div>
        <div className="panel-body observer-universe-body">
          <p className="strategy-note observer-universe-copy">{poolSubcopy}</p>
          <p className="card-meta">source {poolSourceLabel} · focus chart currently on {bootstrap.symbol}</p>
          <div className="observer-symbol-chip-row">
            {universeSymbols.map((symbol) => (
              <span className="observer-symbol-chip" key={symbol}>{symbol}</span>
            ))}
          </div>
        </div>
      </section>

      <section className="panel observer-focus-card">
        <div className="panel-header">
          <h3>Strategy + View</h3>
          <span className="pill">selector shell</span>
        </div>
        <div className="panel-body observer-focus-body">
          <div className="observer-title-row observer-focus-title-row">
            <h2>{selectedStrategy.strategy_label}</h2>
            <span className="pill">{selectedStrategy.strategy_source_kind}</span>
          </div>
          <p className="strategy-note observer-focus-copy">Strategy picks the strategy run. View picks portfolio overview or one symbol chart.</p>
          <div className="observer-focus-layout">
            <div className="observer-focus-selector-block">
              <StrategySelector strategies={strategies} value={selectedStrategy.strategy_id} onChange={setSelectedStrategyId} />
              <ViewSelector symbols={viewSymbols} value={selectedView} onChange={setSelectedView} />
              <p className="card-meta observer-focus-helper">Overview means portfolio-level behavior. Symbol means chart-level execution detail.</p>
            </div>
            <div className="observer-top-meta observer-top-meta-live observer-focus-meta-grid">
              <div><span className="mini-label">strategy id</span><strong>{selectedStrategy.strategy_id}</strong></div>
              <div><span className="mini-label">view</span><strong>{selectedView === OVERVIEW_VIEW_ID ? "Overview (portfolio)" : selectedView}</strong></div>
              <div><span className="mini-label">mounted session</span><strong>{activeSession?.session_id ?? "none"}</strong></div>
              <div><span className="mini-label">symbol source</span><strong>{selectedStrategy.symbols_source_kind}</strong></div>
              <div><span className="mini-label">symbols in view selector</span><strong>{viewSymbols.length}</strong></div>
              <div><span className="mini-label">websocket</span><strong>{state.streamState}</strong></div>
            </div>
          </div>
        </div>
      </section>

      {!isOverviewMode && !missingSymbolSelection ? (
        <div className="metrics-row observer-metrics-row">
          <InfoCard label="engine state" value={bootstrap.health.engine_state.toUpperCase()} subvalue={`freshness ${bootstrap.health.feed_freshness_seconds}s`} />
          <InfoCard label="position" value={`${bootstrap.position.side.toUpperCase()} ${bootstrap.position.quantity}`} subvalue={`avg ${bootstrap.position.avg_price ?? "—"}`} />
          <InfoCard label="last fill" value={bootstrap.last_fill ? `${bootstrap.last_fill.side.toUpperCase()} ${bootstrap.last_fill.quantity}` : "NONE"} subvalue={bootstrap.last_fill ? `${bootstrap.last_fill.price} @ ${formatTimestamp(bootstrap.last_fill.filled_at)}` : "No fills yet"} />
          <InfoCard label="open orders" value={String(bootstrap.open_orders.length)} subvalue={bootstrap.open_orders[0] ? `${bootstrap.open_orders[0].status} · ${bootstrap.open_orders[0].side}` : "No working orders"} />
        </div>
      ) : null}

      <div className="observer-grid">
        <section className="panel observer-chart-panel">
          <div className="panel-header">
            <h3>{isOverviewMode ? "Portfolio Overview" : "Symbol Focus Chart"}</h3>
            {!isOverviewMode ? <div className="observer-chart-controls"><span className="pill">snapshot + stream reconcile</span><TimeframeSelector value={chartTimeframe} onChange={setChartTimeframe} /></div> : null}
          </div>
          <div className="panel-body observer-chart-wrap">
            {isOverviewMode ? (
              <div className="observer-pool-overview">
                <div className="observer-pool-head">
                  <strong>Portfolio projection pending</strong>
                  <span className="status-chip status-chip-muted">truthful placeholder</span>
                </div>
                <p className="card-meta">Portfolio-level PnL projection is not mounted yet. This overview only shows currently available universe and health context.</p>
                <div className="observer-top-meta">
                  <div><span className="mini-label">strategy sessions</span><strong>{selectedStrategy.session_ids.length}</strong></div>
                  <div><span className="mini-label">symbol universe</span><strong>{viewSymbols.length}</strong></div>
                  <div><span className="mini-label">latest seq</span><strong>{bootstrap.latest_seq}</strong></div>
                  <div><span className="mini-label">feed lag</span><strong>{bootstrap.health.feed_freshness_seconds}s</strong></div>
                </div>
              </div>
            ) : missingSymbolSelection ? (
              <div className="state-block observer-empty-state">
                <strong>No mounted symbol session for {selectedSymbol}.</strong>
                <span>View selector includes full universe symbols, but this symbol does not have a mounted observer session yet.</span>
              </div>
            ) : (
              <ObserverChart candles={chartCandles} markers={chartMarkers} />
            )}
          </div>
        </section>

        {!isOverviewMode && !missingSymbolSelection ? <aside className="observer-right-rail">
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

          <details className="panel">
            <summary className="panel-header" style={{ cursor: "pointer", listStyle: "none" }}>
              <h3>Technical diagnostics</h3>
              <span className={`status-chip status-chip-${freshnessClass}`}>{bootstrap.health.freshness_state}</span>
            </summary>
            <div className="panel-body observer-list-panel">
              <div className="kv-grid observer-kv-grid observer-health-grid">
                <div className="kv-item"><span className="mini-label">feed lag</span><strong>{bootstrap.health.feed_freshness_seconds}s</strong></div>
                <div className="kv-item"><span className="mini-label">incidents</span><strong>{bootstrap.health.incidents.length}</strong></div>
                <div className="kv-item"><span className="mini-label">latest seq</span><strong>{state.latestSeq}</strong></div>
                <div className="kv-item"><span className="mini-label">websocket</span><strong>{state.streamState}</strong></div>
                <div className="kv-item"><span className="mini-label">seq gaps</span><strong>{state.sequenceGaps.length}</strong></div>
              </div>
              {state.streamNote ? <div className="observer-incident">{state.streamNote}</div> : null}
              {state.sequenceGaps.map((gap) => <div className="observer-incident" key={`${gap.expected}-${gap.received}`}>sequence gap: expected {gap.expected}, received {gap.received}</div>)}
              {bootstrap.health.incidents.map((incident) => <div className="observer-incident" key={incident}>{incident}</div>)}
            </div>
          </details>
        </aside> : null}
      </div>

      <section className="panel">
        <div className="panel-header">
          <h3>Strategy Timeline</h3>
          <span className="pill">selected mounted session</span>
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

export function ReplayHistorySurface() {
  const [chartTimeframe, setChartTimeframe] = useState<ChartTimeframe>("auto");
  const [sessions, setSessions] = useState<HistorySession[]>([]);
  const [strategies, setStrategies] = useState<StrategyRun[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [selectedView, setSelectedView] = useState<string>(OVERVIEW_VIEW_ID);
  const [sessionIdsBySymbol, setSessionIdsBySymbol] = useState<Record<string, string[]>>({});
  const [bootstrap, setBootstrap] = useState<ObserverBootstrap | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingList(true);
    getJson<HistorySessionsPayload>("/api/observer/history/sessions?limit=20")
      .then((payload) => {
        if (cancelled) return;
        const loadedSessions = payload.items ?? [];
        setSessions(loadedSessions);
        setSessionIdsBySymbol(normalizeSymbolSessionMap(payload.session_ids_by_symbol));

        const strategyRunsFromApi = Array.isArray(payload.strategy_runs)
          ? payload.strategy_runs
              .map((run) => {
                const strategyId = typeof run.strategy_id === "string" ? run.strategy_id.trim() : "";
                if (!strategyId) return null;
                return {
                  strategy_id: strategyId,
                  strategy_label: typeof run.strategy_label === "string" && run.strategy_label.trim() ? run.strategy_label.trim() : strategyId,
                  strategy_source_kind:
                    typeof run.strategy_source_kind === "string" && run.strategy_source_kind.trim()
                      ? run.strategy_source_kind.trim()
                      : "history-session-id",
                  symbols: normalizeSymbolList(run.symbols),
                  symbols_source_kind:
                    typeof run.symbols_source_kind === "string" && run.symbols_source_kind.trim()
                      ? run.symbols_source_kind.trim()
                      : "history-primary-symbol",
                  session_ids: normalizeSymbolList(run.session_ids),
                  session_ids_by_symbol: normalizeSymbolSessionMap(run.session_ids_by_symbol),
                  default_session_id: typeof run.default_session_id === "string" ? run.default_session_id : null,
                  run_type: typeof run.run_type === "string" ? run.run_type : null,
                  scenario_id: typeof run.scenario_id === "string" ? run.scenario_id : null,
                  deck_id: typeof run.deck_id === "string" ? run.deck_id : null,
                } satisfies StrategyRun;
              })
              .filter((run): run is StrategyRun => Boolean(run))
          : [];

        const fallbackStrategies: StrategyRun[] = strategyRunsFromApi.length
          ? strategyRunsFromApi
          : (() => {
              const grouped = new Map<string, StrategyRun>();
              loadedSessions.forEach((session) => {
                const strategyId = (session.strategy_id && session.strategy_id.trim()) || session.session_id;
                if (!grouped.has(strategyId)) {
                  grouped.set(strategyId, {
                    strategy_id: strategyId,
                    strategy_label: (session.strategy_label && session.strategy_label.trim()) || `${session.date} · ${session.run_type}`,
                    strategy_source_kind: (session.strategy_source_kind && session.strategy_source_kind.trim()) || "history-session-id",
                    symbols: [],
                    symbols_source_kind: (session.symbols_source_kind && session.symbols_source_kind.trim()) || "history-primary-symbol",
                    session_ids: [],
                    session_ids_by_symbol: {},
                    default_session_id: session.session_id,
                    run_type: session.run_type,
                    scenario_id: session.scenario_id,
                    deck_id: session.deck_id,
                  });
                }
                const run = grouped.get(strategyId);
                if (!run) return;
                if (!run.session_ids.includes(session.session_id)) run.session_ids.push(session.session_id);
                normalizeSymbolList(session.symbols ?? [session.symbol]).forEach((symbol) => {
                  if (!run.symbols.includes(symbol)) run.symbols.push(symbol);
                  const ids = run.session_ids_by_symbol[symbol] ?? [];
                  if (!ids.includes(session.session_id)) run.session_ids_by_symbol[symbol] = [...ids, session.session_id];
                });
              });
              return [...grouped.values()];
            })();

        setStrategies(fallbackStrategies);
        setSelectedStrategyId((current) => {
          if (current && fallbackStrategies.some((strategy) => strategy.strategy_id === current)) return current;
          return fallbackStrategies[0]?.strategy_id ?? null;
        });
        setSelectedView(OVERVIEW_VIEW_ID);
      })
      .catch((reason) => setError(String(reason)))
      .finally(() => {
        if (!cancelled) setLoadingList(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedStrategy = useMemo(
    () => strategies.find((strategy) => strategy.strategy_id === selectedStrategyId) ?? null,
    [strategies, selectedStrategyId],
  );

  useEffect(() => {
    if (selectedView === OVERVIEW_VIEW_ID) return;
    if (selectedStrategy?.symbols.includes(selectedView)) return;
    setSelectedView(OVERVIEW_VIEW_ID);
  }, [selectedStrategy, selectedView]);

  const selectedSymbol = selectedView === OVERVIEW_VIEW_ID ? null : selectedView;
  const isOverviewMode = selectedView === OVERVIEW_VIEW_ID;
  const summarySessionId = selectedStrategy?.default_session_id ?? selectedStrategy?.session_ids[0] ?? null;
  const symbolSessionId = selectedSymbol
    ? selectedStrategy?.session_ids_by_symbol[selectedSymbol]?.[0] ?? sessionIdsBySymbol[selectedSymbol]?.[0] ?? null
    : null;
  const hasMountedSymbolSession = Boolean(selectedSymbol && symbolSessionId);
  const activeSessionId = hasMountedSymbolSession ? symbolSessionId : summarySessionId;

  useEffect(() => {
    if (!activeSessionId) {
      setBootstrap(null);
      return;
    }
    let cancelled = false;
    setLoadingDetail(true);
    getJson<ObserverBootstrap>(`/api/observer/history/sessions/${activeSessionId}/bootstrap`)
      .then((payload) => {
        if (!cancelled) setBootstrap(payload);
      })
      .catch((reason) => setError(String(reason)))
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeSessionId]);

  const selected = sessions.find((item) => item.session_id === activeSessionId) ?? null;
  const freshnessClass = tone(bootstrap?.freshness_state ?? selected?.freshness_state ?? "stale");
  const replayChartCandles = aggregateCandles(bootstrap?.chart.candles ?? [], chartTimeframe);
  const replayChartMarkers = alignMarkers(bootstrap?.chart.markers.slice(-MARKER_LIMIT) ?? [], chartTimeframe);
  const viewSymbols = selectedStrategy?.symbols ?? [];

  if (loadingList) return <div className="state-block">Loading sanitized observer history…</div>;
  if (error) return <div className="state-block text-alert">ERROR: {error}</div>;
  if (!sessions.length) {
    return (
      <div className="state-block observer-empty-state">
        <strong>No replay history configured.</strong>
        <span>No sanitized dashboard fixture bundles are currently projected into observer history.</span>
      </div>
    );
  }

  return (
    <main className="observer-surface replay-history-surface">
      <section className="panel observer-hero-panel">
        <div className="panel-header">
          <h3>Replay History</h3>
          <div className="observer-chip-row">
            <span className="status-chip status-chip-muted">READ ONLY</span>
            <span className="status-chip status-chip-muted">STATIC</span>
            <span className="status-chip status-chip-muted">GENERATED</span>
          </div>
        </div>
        <div className="panel-body observer-hero-body">
          <div>
            <div className="observer-title-row">
              <h2>Historical observer bundles</h2>
              <span className="pill">{sessions.length} sessions</span>
            </div>
            <p className="strategy-note">Strategy picks the replay run. View picks portfolio overview or symbol detail. No synthetic portfolio PnL is generated in this slice.</p>
          </div>
        </div>
      </section>

      <section className="panel observer-focus-card">
        <div className="panel-header">
          <h3>Strategy + View</h3>
          <span className="pill">replay selector shell</span>
        </div>
        <div className="panel-body observer-focus-body">
          <div className="observer-focus-layout">
            <div className="observer-focus-selector-block">
              {selectedStrategy ? <StrategySelector strategies={strategies} value={selectedStrategy.strategy_id} onChange={setSelectedStrategyId} /> : null}
              <ViewSelector symbols={viewSymbols} value={selectedView} onChange={setSelectedView} />
              <p className="card-meta observer-focus-helper">Overview means portfolio-level replay behavior. Symbol means chart-level replay execution detail.</p>
            </div>
            <div className="observer-top-meta observer-top-meta-live observer-focus-meta-grid">
              <div><span className="mini-label">strategy id</span><strong>{selectedStrategy?.strategy_id ?? "—"}</strong></div>
              <div><span className="mini-label">view</span><strong>{selectedView === OVERVIEW_VIEW_ID ? "Overview (portfolio)" : selectedView}</strong></div>
              <div><span className="mini-label">run type</span><strong>{selectedStrategy?.run_type ?? "—"}</strong></div>
              <div><span className="mini-label">scenario</span><strong>{selectedStrategy?.scenario_id ?? "—"}</strong></div>
              <div><span className="mini-label">deck</span><strong>{selectedStrategy?.deck_id ?? "—"}</strong></div>
              <div><span className="mini-label">mounted replay session</span><strong>{activeSessionId ?? "none"}</strong></div>
            </div>
          </div>
        </div>
        </section>

      <section className="panel replay-detail-panel">
          <div className="panel-header"><h3>{isOverviewMode ? "Portfolio Replay Overview" : "Replay Detail"}</h3><span className={`status-chip status-chip-${freshnessClass}`}>{bootstrap?.freshness_state ?? selected?.freshness_state}</span></div>
          {loadingDetail ? (
            <div className="state-block">Loading sanitized observer bundle…</div>
          ) : bootstrap && selected ? (
            <div className="panel-body replay-detail-body">
              <div className="observer-title-row">
                <h2>{bootstrap.session_label}</h2>
                <span className="pill">replay-static</span>
              </div>
              <div className="observer-top-meta replay-top-meta">
                <div><span className="mini-label">generated</span><strong>{formatTimestamp(bootstrap.generated_at)}</strong></div>
                <div><span className="mini-label">source</span><strong>{bootstrap.provenance?.source_kind ?? selected.source_kind}</strong></div>
                <div><span className="mini-label">receipt ref</span><strong>{bootstrap.provenance?.source_path_ref ?? selected.source_path_ref}</strong></div>
                <div><span className="mini-label">compare</span><strong>{selected.has_compare ? "artifact ref" : "unavailable"}</strong></div>
              </div>
              {isOverviewMode ? (
                <div className="observer-pool-overview">
                  <div className="observer-pool-head">
                    <strong>Portfolio replay projection pending</strong>
                    <span className="status-chip status-chip-muted">truthful placeholder</span>
                  </div>
                  <p className="card-meta">Portfolio-level replay projection is not implemented yet. This overview reports strategy/run context only.</p>
                  <div className="observer-top-meta">
                    <div><span className="mini-label">strategy sessions</span><strong>{selectedStrategy?.session_ids.length ?? 0}</strong></div>
                    <div><span className="mini-label">view symbols</span><strong>{viewSymbols.length}</strong></div>
                    <div><span className="mini-label">latest seq</span><strong>{bootstrap.latest_seq}</strong></div>
                    <div><span className="mini-label">generated</span><strong>{formatTimestamp(bootstrap.generated_at)}</strong></div>
                  </div>
                </div>
              ) : !hasMountedSymbolSession ? (
                <div className="state-block observer-empty-state">
                  <strong>No mounted symbol session for {selectedSymbol}.</strong>
                  <span>This replay strategy exposes the symbol in metadata, but no replay session is mounted for it yet.</span>
                </div>
              ) : (
                <>
                  <div className="metrics-row observer-metrics-row replay-metrics-row">
                    <InfoCard label="symbol" value={bootstrap.symbol} subvalue={selected.scenario_id ?? "scenario unavailable"} />
                    <InfoCard label="events" value={String(selected.event_count)} subvalue={`latest seq ${bootstrap.latest_seq}`} />
                    <InfoCard label="position" value={`${bootstrap.position.side.toUpperCase()} ${bootstrap.position.quantity}`} subvalue="state at replay end" />
                    <InfoCard label="labels" value="STATIC" subvalue={(bootstrap.provenance?.labels ?? selected.tags).join(" · ")} />
                  </div>
                  <div className="observer-grid replay-observer-grid">
                    <section className="panel observer-chart-panel">
                      <div className="panel-header"><h3>Static Chart</h3><div className="observer-chart-controls"><span className="pill">no websocket</span><TimeframeSelector value={chartTimeframe} onChange={setChartTimeframe} /></div></div>
                      <div className="panel-body observer-chart-wrap"><ObserverChart candles={replayChartCandles} markers={replayChartMarkers} /></div>
                    </section>
                <aside className="observer-right-rail">
                    <details className="panel" open>
                      <summary className="panel-header" style={{ cursor: "pointer", listStyle: "none" }}><h3>Provenance diagnostics</h3><span className="pill">sanitized</span></summary>
                      <div className="panel-body observer-list-panel">
                        <div className="observer-incident">source_ref={bootstrap.provenance?.source_path_ref ?? selected.source_path_ref}</div>
                        {bootstrap.provenance?.compare_ref ? <div className="observer-incident">compare_ref={bootstrap.provenance.compare_ref}</div> : null}
                        <div className="observer-incident">deck={selected.deck_id ?? "—"}</div>
                      </div>
                    </details>
                </aside>
              </div>
                </>
              )}
              <section className="panel replay-timeline-panel">
                <div className="panel-header"><h3>Event Timeline</h3><span className="pill">static order</span></div>
                <div className="panel-body observer-timeline-grid">
                  {bootstrap.timeline.map((item) => (
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
            </div>
          ) : (
            <div className="state-block">Select a strategy run to open replay detail.</div>
          )}
      </section>
    </main>
  );
}
