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
    if (!ids.length) return;
    symbolAliases(key).forEach((alias) => {
      normalized[alias] = ids;
    });
  });
  return normalized;
}

function symbolAliases(symbol: string | null | undefined): string[] {
  const raw = typeof symbol === "string" ? symbol.trim() : "";
  if (!raw) return [];
  const aliases = new Set<string>([raw]);
  const upper = raw.toUpperCase();
  aliases.add(upper);
  if (upper.endsWith(".TW")) aliases.add(upper.slice(0, -3));
  if (/^\d{4,6}[A-Z]?$/.test(upper)) aliases.add(`${upper}.TW`);
  return [...aliases].filter(Boolean);
}

function resolveMountedSymbolSessionId(
  symbol: string | null | undefined,
  strategy: StrategyRun | null | undefined,
  fallbackMap: Record<string, string[]>,
): string | null {
  for (const alias of symbolAliases(symbol)) {
    const strategySession = strategy?.session_ids_by_symbol[alias]?.[0];
    if (strategySession) return strategySession;
    const fallbackSession = fallbackMap[alias]?.[0];
    if (fallbackSession) return fallbackSession;
  }
  return null;
}

function defaultSymbolView(
  strategy: StrategyRun | null | undefined,
  loadedSessions: ObserverSession[],
  fallbackMap: Record<string, string[]>,
  defaultSessionId?: string | null,
): string {
  const defaultSession = loadedSessions.find((session) => session.session_id === defaultSessionId);
  if (defaultSession?.symbol && resolveMountedSymbolSessionId(defaultSession.symbol, strategy, fallbackMap)) return defaultSession.symbol;
  for (const session of loadedSessions) {
    if (session.symbol && resolveMountedSymbolSessionId(session.symbol, strategy, fallbackMap)) return session.symbol;
  }
  for (const symbol of strategy?.symbols ?? []) {
    if (resolveMountedSymbolSessionId(symbol, strategy, fallbackMap)) return symbol;
  }
  return OVERVIEW_VIEW_ID;
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
      <span className="mini-label">Strategy Card selector</span>
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
      <span className="mini-label">Strategy Card view</span>
      <select id="observer-view-select" value={value} onChange={(event) => onChange(event.target.value)}>
        <option value={OVERVIEW_VIEW_ID}>Overview · trades / position / PnL / receipts</option>
        {symbols.map((symbol) => (
          <option key={symbol} value={symbol}>
            Symbol Detail · {symbol}
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

function streamTone(value: StreamState, hasSequenceGaps: boolean) {
  if (value === "live") return hasSequenceGaps ? "alert" : "accent";
  if (value === "connecting" || value === "idle" || value === "ended") return "muted";
  return "alert";
}

function streamLabel(value: StreamState, gapCount = 0) {
  const gapSuffix = gapCount > 0 ? ` · GAPS: ${gapCount}` : "";
  if (value === "ended") return `STREAM CLOSED · CLEAN${gapSuffix}`;
  if (value === "closed") return `STREAM CLOSED · UNEXPECTED${gapSuffix}`;
  if (value === "error") return `STREAM ERROR${gapSuffix}`;
  if (value === "connecting") return `STREAM CONNECTING${gapSuffix}`;
  if (value === "idle") return `STREAM IDLE${gapSuffix}`;
  return `STREAM LIVE${gapSuffix}`;
}

function ObserverTrustStrip({
  mode,
  sessionId,
  sessionLabel,
  bundleId,
  generatedAt,
}: {
  mode: "live" | "replay";
  sessionId?: string | null;
  sessionLabel?: string | null;
  bundleId?: string | null;
  generatedAt?: string | null;
}) {
  const sessionText = sessionLabel ? `${sessionId} · ${sessionLabel}` : sessionId;
  return (
    <div className="observer-trust-strip observer-trust-strip-inline" aria-label="Observer session identity">
      <span className="status-chip status-chip-muted">{mode === "replay" ? "NO LIVE STREAM" : "OBSERVER STREAM"}</span>
      {sessionText ? <span className="pill">session {sessionText}</span> : null}
      {bundleId ? <span className="pill">bundle {bundleId}</span> : null}
      {generatedAt ? <span className="pill">generated {formatTimestamp(generatedAt)}</span> : null}
    </div>
  );
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
          } satisfies ChartMarker,
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
          } satisfies ChartMarker,
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


function ReconciliationStateBlock({
  label,
  state,
  reason,
}: {
  label: string;
  state: "empty" | "degraded" | "stale" | "derived" | "unavailable";
  reason: string;
}) {
  const chipTone = state === "degraded" || state === "stale" ? "alert" : state === "derived" ? "muted" : "muted";
  return (
    <div className={`observer-state-block observer-state-${state}`}>
      <div className="observer-state-block-head">
        <span className={`status-chip status-chip-${chipTone}`}>{state.toUpperCase()}</span>
        <strong>{label}</strong>
      </div>
      <p className="card-meta">{reason}</p>
      <span className="observer-state-receipt">receipt lane: {label.toLowerCase()} · trust anchor only</span>
    </div>
  );
}

function displayNumber(value: number | null | undefined) {
  return value == null ? "unavailable" : String(value);
}

function summarizePosition(position: PositionSummary | null | undefined) {
  if (!position) return "unavailable";
  return `${position.side.toUpperCase()} ${displayNumber(position.quantity)} · avg ${displayNumber(position.avg_price)} · mark ${displayNumber(position.market_price)}`;
}

function summarizePnL(position: PositionSummary | null | undefined) {
  if (!position || (position.unrealized_pnl == null && position.realized_pnl == null)) {
    return "unavailable · sanitized observer bundle does not provide portfolio PnL";
  }
  return `uPnL ${displayNumber(position.unrealized_pnl)} · rPnL ${displayNumber(position.realized_pnl)}`;
}

function countFillEvents(bootstraps: ObserverBootstrap[]) {
  const fillIds = new Set<string>();
  let timelineFillCount = 0;
  bootstraps.forEach((bootstrap) => {
    if (bootstrap.last_fill?.fill_id) fillIds.add(bootstrap.last_fill.fill_id);
    bootstrap.timeline.forEach((entry) => {
      if (entry.event_type === "fill_received") timelineFillCount += 1;
    });
  });
  return Math.max(fillIds.size, timelineFillCount);
}

function summarizeReceiptState(bootstraps: ObserverBootstrap[]) {
  if (!bootstraps.length) return "unavailable · no mounted bootstrap loaded";
  const degraded = bootstraps.filter((bootstrap) => bootstrap.freshness_state !== "fresh").length;
  const sourceKinds = normalizeSymbolList(bootstraps.map((bootstrap) => bootstrap.provenance?.source_kind ?? "unknown"));
  return `${degraded ? `${degraded} degraded · ` : ""}${sourceKinds.join(" / ") || "unknown source"} · sanitized trust anchor`;
}

function summarizeStrategyOverview(strategy: StrategyRun, viewSymbols: string[], bootstraps: ObserverBootstrap[]) {
  const loadedSessionIds = new Set(bootstraps.map((bootstrap) => bootstrap.session_id));
  const mountedSymbols = normalizeSymbolList(bootstraps.map((bootstrap) => bootstrap.symbol));
  const openOrders = bootstraps.reduce((total, bootstrap) => total + bootstrap.open_orders.length, 0);
  const positionBootstraps = bootstraps.filter((bootstrap) => bootstrap.position && bootstrap.position.side !== "flat" && bootstrap.position.quantity !== 0);
  return {
    sessionsTotal: strategy.session_ids.length,
    sessionsLoaded: loadedSessionIds.size,
    mountedSymbols: mountedSymbols.length || viewSymbols.length,
    openOrders,
    fillCount: countFillEvents(bootstraps),
    positionSummary: positionBootstraps.length
      ? positionBootstraps.map((bootstrap) => `${bootstrap.symbol}: ${summarizePosition(bootstrap.position)}`).join(" · ")
      : "flat/empty or unavailable from mounted session data",
    pnlSummary: bootstraps.some((bootstrap) => bootstrap.position?.unrealized_pnl != null || bootstrap.position?.realized_pnl != null)
      ? bootstraps.map((bootstrap) => `${bootstrap.symbol}: ${summarizePnL(bootstrap.position)}`).join(" · ")
      : "unavailable · sanitized observer bundle does not provide portfolio PnL",
    receiptState: summarizeReceiptState(bootstraps),
  };
}

function sanitizeReceiptRef(value: string | null | undefined) {
  if (!value) return "—";
  const trimmed = value.trim();
  if (!trimmed) return "—";
  const withoutFragment = trimmed.split("#", 1)[0].split("?", 1)[0];
  const withoutProtocol = withoutFragment.replace(/^[a-z][a-z0-9+.-]*:\/\//i, "").replace(/^[a-z][a-z0-9+.-]*:/i, "");
  const last = withoutProtocol.split(/[\/]/).filter(Boolean).pop() ?? withoutProtocol;
  return last.replace(/[^a-zA-Z0-9._:@-]/g, "•").slice(0, 96);
}

function ReceiptTrustPanel({ bootstrap, selected }: { bootstrap: ObserverBootstrap; selected?: HistorySession | null }) {
  const sourceKind = bootstrap.provenance?.source_kind ?? selected?.source_kind ?? "unknown";
  const sourceRef = sanitizeReceiptRef(bootstrap.provenance?.source_path_ref ?? selected?.source_path_ref);
  const compareRef = sanitizeReceiptRef(bootstrap.provenance?.compare_ref);
  const labels = bootstrap.provenance?.labels?.length ? bootstrap.provenance.labels : selected?.tags ?? [];
  return (
    <details className="panel receipt-trust-panel" open>
      <summary className="panel-header" style={{ cursor: "pointer", listStyle: "none" }}>
        <h3>Receipt Drawer · Trust Anchor</h3>
        <span className="pill">sanitized</span>
      </summary>
      <div className="panel-body observer-list-panel receipt-trust-body">
        <div className="observer-top-meta receipt-trust-grid">
          <div><span className="mini-label">session</span><strong>{bootstrap.session_id}</strong></div>
          <div><span className="mini-label">schema</span><strong>{bootstrap.schema_version}</strong></div>
          <div><span className="mini-label">generated</span><strong>{formatTimestamp(bootstrap.generated_at)}</strong></div>
          <div><span className="mini-label">freshness / validity</span><strong>{bootstrap.freshness_state}</strong></div>
          <div><span className="mini-label">source kind</span><strong>{sourceKind}</strong></div>
          <div><span className="mini-label">receipt ref</span><strong>{sourceRef}</strong></div>
          {compareRef !== "—" ? <div><span className="mini-label">compare ref</span><strong>{compareRef}</strong></div> : null}
          <div><span className="mini-label">labels</span><strong>{labels.length ? labels.join(" · ") : "—"}</strong></div>
        </div>
        <ul className="receipt-authority-list">
          <li>read-only API surface · no POST / PUT / PATCH / DELETE</li>
          <li>no broker control in browser · no order submit / cancel / modify</li>
          <li>sanitized payload only · raw path/key is reduced to a receipt basename</li>
          <li>degraded or unavailable lanes must remain explicit in the UI</li>
        </ul>
      </div>
    </details>
  );
}

function ObserverChart({ candles, markers, mode = "live" }: { candles: Candle[]; markers: ChartMarker[]; mode?: "live" | "replay" }) {
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
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: "rgba(141,170,186,0.2)", tickMarkFormatter: (time: UTCTimestamp | number) => formatChartTime(time as number) },
        localization: { timeFormatter: (time: UTCTimestamp | number) => formatChartTime(time as number) },
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

  return (
    <div className="observer-chart-shell">
      <div className="observer-chart-legend" aria-label="Chart marker legend">
        <span className="mini-label">{mode === "replay" ? "replay markers" : "live markers"}</span>
        <span><i className="legend-dot legend-buy" />buy/order</span>
        <span><i className="legend-dot legend-sell" />sell/order</span>
        <span><i className="legend-dot legend-fill" />fill</span>
        <span><i className="legend-dot legend-derived" />derived · not trust anchor</span>
      </div>
      <div className="observer-chart" ref={hostRef} />
    </div>
  );
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
  const [overviewBootstraps, setOverviewBootstraps] = useState<ObserverBootstrap[]>([]);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState<string | null>(null);
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
              .map((run): StrategyRun | null => {
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
                  run_type: typeof run.run_type === "string" ? run.run_type : null,
                  scenario_id: typeof run.scenario_id === "string" ? run.scenario_id : null,
                  deck_id: typeof run.deck_id === "string" ? run.deck_id : null,
                  symbols_source_kind:
                    typeof run.symbols_source_kind === "string" && run.symbols_source_kind.trim()
                      ? run.symbols_source_kind.trim()
                      : payload.symbol_pool?.source_kind ?? "observer-sessions-fallback",
                  session_ids: normalizeSymbolList(run.session_ids),
                  session_ids_by_symbol: normalizeSymbolSessionMap(run.session_ids_by_symbol),
                  default_session_id: typeof run.default_session_id === "string" ? run.default_session_id : null,
                } satisfies StrategyRun;
              })
              .filter((run): run is StrategyRun => run !== null)
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
        const strategyForDefaultSession = normalizedStrategies.find((strategy) =>
          strategy.session_ids.includes(payload.default_session_id ?? ""),
        );
        const fallbackStrategy = strategyForDefaultSession ?? normalizedStrategies[0] ?? null;
        setSelectedStrategyId((current) => {
          if (current && normalizedStrategies.some((strategy) => strategy.strategy_id === current)) return current;
          return fallbackStrategy?.strategy_id ?? null;
        });
        setSelectedView((current) => {
          if (current !== OVERVIEW_VIEW_ID && resolveMountedSymbolSessionId(current, fallbackStrategy, normalizedSessionMap)) return current;
          return defaultSymbolView(fallbackStrategy, loadedSessions, normalizedSessionMap, payload.default_session_id);
        });
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
    if (resolveMountedSymbolSessionId(selectedView, selectedStrategy, sessionIdsBySymbol)) return;
    if (selectedStrategy?.symbols.includes(selectedView)) return;
    setSelectedView(OVERVIEW_VIEW_ID);
  }, [selectedStrategy, selectedView, sessionIdsBySymbol]);

  const strategySummarySessionId = selectedStrategy?.default_session_id ?? selectedStrategy?.session_ids[0] ?? null;
  const selectedSymbol = selectedView === OVERVIEW_VIEW_ID ? null : selectedView;
  const mountedSymbolSessionId = selectedSymbol ? resolveMountedSymbolSessionId(selectedSymbol, selectedStrategy, sessionIdsBySymbol) : null;
  const hasMountedSymbolSession = Boolean(selectedSymbol && mountedSymbolSessionId);
  const isOverviewMode = selectedView === OVERVIEW_VIEW_ID;
  const activeSessionId = hasMountedSymbolSession ? mountedSymbolSessionId : strategySummarySessionId;

  useEffect(() => {
    let cancelled = false;
    const sessionIds = selectedStrategy?.session_ids ?? [];

    async function loadOverviewBootstraps() {
      if (!selectedStrategy || !isOverviewMode || !sessionIds.length) {
        setOverviewBootstraps([]);
        setOverviewError(null);
        setOverviewLoading(false);
        return;
      }
      setOverviewLoading(true);
      try {
        const bootstraps = await Promise.all(
          sessionIds.map((sessionId) => getJson<ObserverBootstrap>(`/api/observer/sessions/${sessionId}/bootstrap`)),
        );
        if (cancelled) return;
        setOverviewBootstraps(bootstraps);
        setOverviewError(null);
      } catch (reason) {
        if (cancelled) return;
        setOverviewBootstraps([]);
        setOverviewError(String(reason));
      } finally {
        if (!cancelled) setOverviewLoading(false);
      }
    }

    void loadOverviewBootstraps();
    return () => {
      cancelled = true;
    };
  }, [isOverviewMode, selectedStrategy]);

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
    const selectedSession: ObserverSession = session;

    let socket: WebSocket | null = null;
    let cancelled = false;

    async function loadSelectedSession() {
      setLoading(true);
      try {
        const bootstrap = await getJson<ObserverBootstrap>(`/api/observer/sessions/${selectedSession.session_id}/bootstrap`);
        if (cancelled) return;
        setError(null);
        setState({
          session: selectedSession,
          bootstrap: { ...bootstrap, chart: { ...bootstrap.chart, markers: bootstrap.chart.markers.slice(-MARKER_LIMIT) } },
          timeline: bootstrap.timeline,
          events: [],
          latestSeq: bootstrap.latest_seq,
          streamState: "connecting",
          streamNote: null,
          sequenceGaps: [],
        });
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        socket = new WebSocket(`${protocol}://${window.location.host}/api/observer/sessions/${selectedSession.session_id}/stream?after_seq=${bootstrap.latest_seq}`);
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
  const overviewSummary = summarizeStrategyOverview(selectedStrategy, viewSymbols, overviewBootstraps.length ? overviewBootstraps : [bootstrap]);

  return (
    <main className="observer-surface">
      <section className="panel observer-status-strip">
        <div className="panel-header">
          <h3>Observer Status</h3>
          <div className="observer-chip-row">
            <span className={`status-chip status-chip-${freshnessClass}`}>LIVE FRESHNESS · {bootstrap.freshness_state.toUpperCase()}</span>
            <span className={`status-chip status-chip-${streamTone(state.streamState, state.sequenceGaps.length > 0)}`}>{streamLabel(state.streamState, state.sequenceGaps.length)}</span>
            <span className={`status-chip status-chip-${state.sequenceGaps.length ? "alert" : "muted"}`}>SEQ GAPS {state.sequenceGaps.length}</span>
          </div>
        </div>
        <div className="panel-body observer-status-body observer-top-meta">
          <div><span className="mini-label">session id</span><strong>{bootstrap.session_id}</strong></div>
          <div><span className="mini-label">latest seq</span><strong>{state.latestSeq}</strong></div>
          <div><span className="mini-label">feed lag</span><strong>{bootstrap.health.feed_freshness_seconds}s</strong></div>
          <div><span className="mini-label">generated</span><strong>{formatTimestamp(bootstrap.generated_at)}</strong></div>
          <div><span className="mini-label">stream note</span><strong>{state.streamNote ?? "none"}</strong></div>
        </div>
        <div className="panel-body observer-status-trust-body">
          <ObserverTrustStrip mode="live" sessionId={bootstrap.session_id} sessionLabel={bootstrap.session_label} bundleId={sanitizeReceiptRef(bootstrap.provenance?.source_path_ref ?? bootstrap.provenance?.compare_ref ?? bootstrap.provenance?.source_kind)} generatedAt={bootstrap.generated_at} />
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
          <h3>Strategy Card selector</h3>
          <span className="pill">Overview / Symbol Detail</span>
        </div>
        <div className="panel-body observer-focus-body">
          <div className="observer-title-row observer-focus-title-row">
            <h2>{selectedStrategy.strategy_label}</h2>
            <span className="pill">{selectedStrategy.strategy_source_kind}</span>
          </div>
          <p className="strategy-note observer-focus-copy">Strategy Card picks the strategy run. Overview summarizes strategy-card truth; Symbol Detail opens one mounted chart and execution trace.</p>
          <div className="observer-focus-layout">
            <div className="observer-focus-selector-block">
              <StrategySelector strategies={strategies} value={selectedStrategy.strategy_id} onChange={setSelectedStrategyId} />
              <ViewSelector symbols={viewSymbols} value={selectedView} onChange={setSelectedView} />
              <p className="card-meta observer-focus-helper">Overview = trades / position / PnL truth / receipts. Symbol Detail = bar chart / orders / fills / health timeline.</p>
            </div>
            <div className="observer-top-meta observer-top-meta-live observer-focus-meta-grid">
              <div><span className="mini-label">strategy id</span><strong>{selectedStrategy.strategy_id}</strong></div>
              <div><span className="mini-label">view</span><strong>{selectedView === OVERVIEW_VIEW_ID ? "Strategy Card Overview" : `Symbol Detail · ${selectedView}`}</strong></div>
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
          <InfoCard label="position" value={`${bootstrap.position.side.toUpperCase()} ${bootstrap.position.quantity}`} subvalue={`avg ${bootstrap.position.avg_price ?? "unavailable"}`} />
          <InfoCard label="last fill" value={bootstrap.last_fill ? `${bootstrap.last_fill.side.toUpperCase()} ${bootstrap.last_fill.quantity}` : "EMPTY"} subvalue={bootstrap.last_fill ? `${bootstrap.last_fill.price} @ ${formatTimestamp(bootstrap.last_fill.filled_at)}` : "intentional empty · no fills yet"} />
          <InfoCard label="open orders" value={String(bootstrap.open_orders.length)} subvalue={bootstrap.open_orders[0] ? `${bootstrap.open_orders[0].status} · ${bootstrap.open_orders[0].side}` : "intentional empty · no working orders"} />
        </div>
      ) : null}

      <div className="observer-grid">
        <section className="panel observer-chart-panel">
          <div className="panel-header">
            <h3>{isOverviewMode ? "Strategy Card Overview" : "Symbol Detail · Bar Chart"}</h3>
            {!isOverviewMode ? <div className="observer-chart-controls"><span className="pill">snapshot + stream reconcile</span><TimeframeSelector value={chartTimeframe} onChange={setChartTimeframe} /></div> : null}
          </div>
          <div className="panel-body observer-chart-wrap">
            {isOverviewMode ? (
              <div className="observer-pool-overview">
                <div className="observer-pool-head">
                  <strong>Strategy Card Overview</strong>
                  <span className="status-chip status-chip-muted">read-only receipt truth</span>
                </div>
                <p className="card-meta">Trades, position, PnL, and receipt state are derived only from mounted sanitized observer bootstraps. PnL stays unavailable when the payload does not provide it.</p>
                {overviewLoading ? <ReconciliationStateBlock label="overview" state="derived" reason="Loading mounted session bootstraps for strategy-card summary." /> : null}
                {overviewError ? <ReconciliationStateBlock label="overview" state="degraded" reason={`Unable to load every mounted session bootstrap: ${overviewError}`} /> : null}
                <div className="observer-top-meta observer-overview-grid">
                  <div><span className="mini-label">strategy sessions</span><strong>{overviewSummary.sessionsLoaded}/{overviewSummary.sessionsTotal}</strong></div>
                  <div><span className="mini-label">mounted symbols</span><strong>{overviewSummary.mountedSymbols}</strong></div>
                  <div><span className="mini-label">open orders</span><strong>{overviewSummary.openOrders}</strong></div>
                  <div><span className="mini-label">fills / trades</span><strong>{overviewSummary.fillCount}</strong></div>
                  <div><span className="mini-label">position summary</span><strong>{overviewSummary.positionSummary}</strong></div>
                  <div><span className="mini-label">PnL truth</span><strong>{overviewSummary.pnlSummary}</strong></div>
                  <div><span className="mini-label">receipt / trust state</span><strong>{overviewSummary.receiptState}</strong></div>
                  <div><span className="mini-label">active receipt seq</span><strong>{bootstrap.latest_seq}</strong></div>
                </div>
              </div>
            ) : missingSymbolSelection ? (
              <div className="state-block observer-empty-state">
                <strong>No mounted symbol session for {selectedSymbol}.</strong>
                <span>View selector includes full universe symbols, but this symbol does not have a mounted observer session yet.</span>
              </div>
            ) : (
              <ObserverChart candles={chartCandles} markers={chartMarkers} mode="live" />
            )}
          </div>
        </section>

        {!isOverviewMode && !missingSymbolSelection ? <aside className="observer-right-rail">
          <section className="panel observer-reconciliation-panel">
            <div className="panel-header">
              <h3>Symbol Detail · Execution State</h3>
              <div className="observer-chip-row">
                <span className="pill">orders ↔ fills ↔ position</span>
                <span className="status-chip status-chip-muted">DERIVED PRESENTATION</span>
              </div>
            </div>
            <div className="panel-body observer-reconciliation-body">
              <ReconciliationStateBlock
                label="derived"
                state="derived"
                reason="This panel presents the latest API snapshot plus observer stream updates. Treat it as presentation state; receipt/provenance remains the trust anchor."
              />
            </div>
          </section>

          <section className="panel">
            <div className="panel-header"><h3>Symbol Detail · Position</h3><span className={`status-chip status-chip-${freshnessClass}`}>{bootstrap.health.freshness_state}</span></div>
            <div className="panel-body">
              <div className="kv-grid observer-kv-grid">
                <div className="kv-item"><span className="mini-label">side</span><strong>{bootstrap.position.side}</strong></div>
                <div className="kv-item"><span className="mini-label">qty</span><strong>{displayNumber(bootstrap.position.quantity)}</strong></div>
                <div className="kv-item"><span className="mini-label">avg</span><strong>{displayNumber(bootstrap.position.avg_price)}</strong></div>
                <div className="kv-item"><span className="mini-label">mark</span><strong>{displayNumber(bootstrap.position.market_price)}</strong></div>
                <div className="kv-item"><span className="mini-label">uPnL</span><strong>{displayNumber(bootstrap.position.unrealized_pnl)}</strong></div>
                <div className="kv-item"><span className="mini-label">rPnL</span><strong>{displayNumber(bootstrap.position.realized_pnl)}</strong></div>
              </div>
              {bootstrap.position.unrealized_pnl == null && bootstrap.position.realized_pnl == null ? (
                <ReconciliationStateBlock label="position" state="unavailable" reason="PnL is not present in the sanitized observer bundle; UI does not synthesize a fake zero." />
              ) : null}
            </div>
          </section>

          <section className="panel">
            <div className="panel-header"><h3>Symbol Detail · Open Orders</h3><span className="pill">sanitized lane</span></div>
            <div className="panel-body observer-list-panel">
              {bootstrap.open_orders.length ? bootstrap.open_orders.map((order) => (
                <div className="history-item" key={order.order_id}>
                  <div className="history-item-head"><div><div className="card-title history-title">{order.order_id}</div><div className="card-meta">{order.side} · qty {order.quantity}</div></div><span className="status-chip status-chip-muted">{order.status}</span></div>
                  <p className="card-meta">limit {order.limit_price ?? "mkt"} · filled {order.filled_quantity}</p>
                </div>
              )) : (
                <ReconciliationStateBlock label="orders" state="empty" reason="No open orders at this observer point. This is an intentional empty state, not a missing table." />
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panel-header"><h3>Symbol Detail · Last Fill / Trade</h3><span className="pill">sanitized lane</span></div>
            <div className="panel-body observer-list-panel">
              {bootstrap.last_fill ? (
                <div className="history-item history-item-highlight">
                  <div className="history-item-head"><div><div className="card-title history-title">{bootstrap.last_fill.fill_id}</div><div className="card-meta">{formatTimestamp(bootstrap.last_fill.filled_at)}</div></div><span className="status-chip status-chip-accent">fill</span></div>
                  <p className="card-meta">{bootstrap.last_fill.side} · {bootstrap.last_fill.quantity} @ {bootstrap.last_fill.price}</p>
                </div>
              ) : (
                <ReconciliationStateBlock label="fills" state="empty" reason="No fill has been observed for this mounted session yet." />
              )}
            </div>
          </section>

          <details className="panel">
            <summary className="panel-header" style={{ cursor: "pointer", listStyle: "none" }}>
              <h3>Symbol Detail · Timeline / Health</h3>
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
          <h3>{isOverviewMode ? "Strategy Card Overview · Timeline" : "Symbol Detail · Timeline"}</h3>
          <div className="observer-chip-row">
            <span className="pill">selected mounted session</span>
            <span className="status-chip status-chip-muted">append-only order</span>
            <span className="status-chip status-chip-muted">cursor follows chart time</span>
          </div>
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
              <span className="observer-timeline-cursor">cursor {formatTimestamp(item.event_time)} · seq {item.seq}</span>
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
              .map((run): StrategyRun | null => {
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
              .filter((run): run is StrategyRun => run !== null)
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
            <span className="status-chip status-chip-muted">BUNDLE VALIDITY</span>
            <span className="status-chip status-chip-muted">NO LIVE STREAM</span>
          </div>
        </div>
        <div className="panel-body observer-hero-body">
          <div>
            <div className="observer-title-row">
              <h2>Historical observer bundles</h2>
              <span className="pill">{sessions.length} sessions</span>
            </div>
            <p className="strategy-note">Strategy picks the replay run. View picks portfolio overview or symbol detail. Historical bundle validity is separate from live freshness. No synthetic portfolio PnL is generated in this slice.</p>
          </div>
        </div>
        <div className="panel-body observer-status-trust-body">
          <ObserverTrustStrip mode="replay" sessionId={selected?.session_id ?? activeSessionId} sessionLabel={selected?.session_label} bundleId={sanitizeReceiptRef(selected?.source_path_ref)} generatedAt={selected?.generated_at} />
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
              <div><span className="mini-label">view</span><strong>{selectedView === OVERVIEW_VIEW_ID ? "Strategy Card Overview" : `Symbol Detail · ${selectedView}`}</strong></div>
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
              <div className="observer-title-row replay-frame-title">
                <h2>{bootstrap.session_label}</h2>
                <span className="pill">replay-static</span>
                <span className="status-chip status-chip-muted">BUNDLE VALID @ {formatTimestamp(bootstrap.generated_at)}</span>
              </div>
              <div className="replay-frame-banner">
                <strong>Replay frame</strong>
                <span>Historical bundle playback. No websocket, no broker controls, no frontend-synthesized portfolio PnL.</span>
              </div>
              <div className="observer-top-meta replay-top-meta">
                <div><span className="mini-label">generated</span><strong>{formatTimestamp(bootstrap.generated_at)}</strong></div>
                <div><span className="mini-label">source</span><strong>{bootstrap.provenance?.source_kind ?? selected.source_kind}</strong></div>
                <div><span className="mini-label">receipt ref</span><strong>{sanitizeReceiptRef(bootstrap.provenance?.source_path_ref ?? selected.source_path_ref)}</strong></div>
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
                      <div className="panel-body observer-chart-wrap"><ObserverChart candles={replayChartCandles} markers={replayChartMarkers} mode="replay" /></div>
                    </section>
                <aside className="observer-right-rail">
                    <ReceiptTrustPanel bootstrap={bootstrap} selected={selected} />
                </aside>
              </div>
                </>
              )}
              <section className="panel replay-timeline-panel">
                <div className="panel-header"><h3>Event Timeline</h3><div className="observer-chip-row"><span className="pill">static order</span><span className="status-chip status-chip-muted">replay scrub source</span></div></div>
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
              <span className="observer-timeline-cursor">cursor {formatTimestamp(item.event_time)} · seq {item.seq}</span>
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
