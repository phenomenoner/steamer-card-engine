from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import json
import math
from pathlib import Path
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from .legacy_equivalence import (
    DEFAULT_DATA_ROOT,
    DEFAULT_GATE_CONFIG,
    GATE_EVALUATORS,
    LegacyEquivalenceError,
    load_config,
    resolve_output_dir,
)

TAIPEI = ZoneInfo("Asia/Taipei")


def _tick_ts(row: dict[str, Any]) -> float | None:
    if isinstance(row.get("time"), (int, float)):
        value = float(row["time"])
        return value / 1_000_000 if value > 1_000_000_000_000 else value
    if isinstance(row.get("ws_received_time"), (int, float)):
        return float(row["ws_received_time"])
    return None


class TimeAwareEMA:
    def __init__(self, n_minutes: float):
        alpha_1 = 2.0 / (float(n_minutes) + 1.0)
        one_minus_a1 = max(1.0 - alpha_1, 1e-12)
        self.tau_minutes = -1.0 / math.log(one_minus_a1)
        self.ema: float | None = None
        self.t_prev: float | None = None

    def update(self, x: float, t_seconds: float) -> float:
        if self.ema is None or self.t_prev is None:
            self.ema = float(x)
            self.t_prev = float(t_seconds)
            return self.ema
        dt_min = max(0.0, (float(t_seconds) - self.t_prev) / 60.0)
        alpha_dt = min(1.0, max(0.0, 1.0 - math.exp(-dt_min / self.tau_minutes)))
        self.ema = (1.0 - alpha_dt) * self.ema + alpha_dt * float(x)
        self.t_prev = float(t_seconds)
        return self.ema


def resample_and_median3_for_angle(times: list[float], prices: list[float]) -> tuple[list[float], list[float]]:
    if not times or not prices:
        return [], []
    start_sec = math.floor(times[0])
    end_sec = math.floor(times[-1])
    sec_times: list[float] = []
    sec_prices: list[float] = []
    last_price = float(prices[0])
    j = 0
    n = len(times)
    for sec in range(start_sec + 1, end_sec + 2):
        while j < n and times[j] <= sec:
            last_price = float(prices[j])
            j += 1
        sec_times.append(float(sec))
        sec_prices.append(last_price)
    if len(sec_prices) >= 3:
        filt = list(sec_prices)
        for i in range(1, len(sec_prices) - 1):
            a, b, c = sec_prices[i - 1], sec_prices[i], sec_prices[i + 1]
            filt[i] = sorted((a, b, c))[1]
        sec_prices = filt
    x0 = sec_times[0]
    xs = [(t - x0) / 60.0 for t in sec_times]
    return xs, sec_prices


def regression_angle(times: list[float], prices: list[float]) -> float | None:
    if len(prices) < 10:
        return None
    xs, ys = resample_and_median3_for_angle(times, prices)
    if len(ys) < 2:
        return None
    n = len(ys)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_x2 = sum(x * x for x in xs)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-12:
        slope = 0.0
    else:
        slope = (n * sum_xy - sum_x * sum_y) / denom
    angle = (180.0 / math.pi) * math.atan(slope)
    angle = ((angle + 180.0) % 360.0) - 180.0
    return round(0.0 if abs(angle) < 1e-10 else angle, 2)


@dataclass
class SymbolReplayState:
    open_px: float | None = None
    open_ts: float | None = None
    max_seen: float = 0.0
    min_seen: float = 9_999_999.0
    last_qualified_high_ts: float = 0.0
    ema: TimeAwareEMA = field(default_factory=lambda: TimeAwareEMA(float(DEFAULT_GATE_CONFIG.get("price_ema_min", 5))))
    times: deque[float] = field(default_factory=lambda: deque(maxlen=20000))
    prices: deque[float] = field(default_factory=lambda: deque(maxlen=20000))
    zz_last_swing: float | None = None
    zz_direction: int = 0
    zz_trend: int = 0
    zz_extreme: float | None = None
    zz_last_price: float | None = None


def update_zz(st: SymbolReplayState, price: float, cfg: dict[str, Any]) -> int:
    if st.zz_last_swing is None:
        st.zz_last_swing = price
        st.zz_extreme = price
        st.zz_last_price = price
        st.zz_direction = 0
        st.zz_trend = 0
        return 0
    threshold = max(float(cfg.get("zz_threshold", 0.2)), 0.0)
    hysteresis = float(cfg.get("zz_hysteresis", 0.0))
    direction = st.zz_direction
    trend = st.zz_trend
    extreme = st.zz_extreme if st.zz_extreme is not None else st.zz_last_swing
    if direction >= 0:
        extreme = max(float(extreme), price)
        pullback_pct = 100.0 * (float(extreme) - price) / max(float(extreme), 1e-9)
        if pullback_pct >= threshold and direction != -1:
            direction = -1
            trend = -1
            st.zz_last_swing = price
            extreme = price
    if direction <= 0:
        extreme = min(float(extreme), price)
        rebound_pct = 100.0 * (price - float(extreme)) / max(abs(float(extreme)), 1e-9)
        if rebound_pct >= threshold * (1.0 + max(hysteresis, 0.0)) and direction != 1:
            direction = 1
            trend = 1
            st.zz_last_swing = price
            extreme = price
    st.zz_direction = direction
    st.zz_trend = trend
    st.zz_extreme = float(extreme)
    st.zz_last_price = price
    return trend


def recent_angle(st: SymbolReplayState, now_ts: float, lag_minutes: int, min_span_seconds: int, threshold: float) -> tuple[bool, float | None]:
    cutoff = now_ts - lag_minutes * 60.0
    pairs_reversed: list[tuple[float, float]] = []
    for t, p in zip(reversed(st.times), reversed(st.prices)):
        if t < cutoff:
            break
        pairs_reversed.append((t, p))
    pairs = list(reversed(pairs_reversed))
    if len(pairs) < 10:
        return False, None
    if now_ts - pairs[0][0] <= min(300, 20 * lag_minutes):
        return False, None
    angle = regression_angle([p[0] for p in pairs], [p[1] for p in pairs])
    if angle is None:
        return False, None
    return angle <= threshold, angle


def is_sweet_range(px: float, last_close: float) -> bool:
    change_pct = 100.0 * (px - last_close) / max(last_close, 1e-9)
    # Legacy config exposes open sweet range defaults in current code, but old
    # traces mainly need the broad safety gate. Keep this permissive and let
    # A-vs-B report any remaining policy lineage.
    return -10.0 <= change_pct <= 10.0


def load_last_close_from_decisions(decisions_path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    if not decisions_path.exists():
        return out
    with decisions_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            state = row.get("state") or {}
            symbol = str(row.get("symbol") or state.get("symbol") or "")
            last_close = state.get("last_close")
            if symbol and isinstance(last_close, (int, float)) and symbol not in out:
                out[symbol] = float(last_close)
    return out


def replay_session(
    *,
    data_root: Path,
    machine: str,
    date: str,
    gate: str,
    cfg: dict[str, Any],
    max_rows: int | None,
    end_local: str | None = None,
    enforce_one_enter_per_symbol: bool = False,
    symbols: set[str] | None = None,
) -> list[dict[str, Any]]:
    session_dir = data_root / machine / date
    ticks_path = session_dir / "ticks.jsonl"
    decisions_path = session_dir / "decisions.jsonl"
    if not ticks_path.exists():
        raise LegacyEquivalenceError(f"missing ticks: {ticks_path}")
    last_close_by_symbol = load_last_close_from_decisions(decisions_path)
    states: dict[str, SymbolReplayState] = {}
    rows: list[dict[str, Any]] = []
    entered_symbols: set[str] = set()
    evaluator = GATE_EVALUATORS[gate]

    with ticks_path.open("r", encoding="utf-8") as file:
        for line in file:
            if max_rows is not None and len(rows) >= max_rows:
                break
            if not line.strip():
                continue
            tick = json.loads(line)
            if "isOpen" not in tick and "isContinuous" not in tick:
                continue
            symbol = str(tick.get("symbol") or "")
            price = tick.get("price")
            bid = tick.get("bid")
            ts = _tick_ts(tick)
            if not symbol or not isinstance(price, (int, float)) or not isinstance(bid, (int, float)) or ts is None:
                continue
            if symbols is not None and symbol not in symbols:
                continue
            # Bound the replay universe to symbols that historical legacy actually
            # evaluated. The live bot has an active target list; raw ticks contain
            # more symbols than the decision stream.
            if last_close_by_symbol and symbol not in last_close_by_symbol:
                continue
            price = float(price)
            bid = float(bid)
            st = states.setdefault(symbol, SymbolReplayState())
            if st.open_px is None:
                st.open_px = price
                st.open_ts = ts
            if price >= st.max_seen * (1.0 + 0.0):
                st.max_seen = price
                st.last_qualified_high_ts = ts
            if price < st.min_seen:
                st.min_seen = price
            st.times.append(ts)
            st.prices.append(price)
            ema_value = st.ema.update(price, ts)
            last_close = last_close_by_symbol.get(symbol, st.open_px or price)
            now_time = datetime.fromtimestamp(ts, TAIPEI).time()
            if end_local and now_time.isoformat() > end_local:
                continue
            # Fast path: REV_SHORT_AFTER_UP returns before slope/zigzag for blind-open
            # and pre-market-gate rows. Avoid expensive feature work for rows whose
            # reason is determined by earlier gate clauses.
            is_open_tick = "isOpen" in tick
            pre_time_gate = (not is_open_tick) and float(cfg.get("market_gate", 0)) >= 5 and now_time.isoformat() < "09:30:00"
            if is_open_tick or pre_time_gate:
                zz_trend = 0
                slope_ok_1, slope_1, slope_2, slope_3 = False, None, None, None
            else:
                zz_trend = update_zz(st, price, cfg)
                _slope_ok_1, slope_1 = recent_angle(st, ts, int(cfg.get("slope_cond_min", 5)), 10, float(cfg.get("slope_cond_threshold", -5.0)))
                _slope_ok_2, slope_2 = recent_angle(st, ts, int(cfg.get("slope_cond_min_2", 10)), 10, float(cfg.get("slope_cond_threshold_2", -10.0)))
                _slope_ok_3, slope_3 = recent_angle(st, ts, int(cfg.get("slope_cond_min_3", 15)), 10, float(cfg.get("slope_cond_threshold_3", -15.0)))
                threshold_1 = float(cfg.get("slope_cond_threshold", -5.0))
                threshold_2 = float(cfg.get("slope_cond_threshold_2", -10.0))
                threshold_3 = float(cfg.get("slope_cond_threshold_3", -15.0))
                sl_1 = slope_1 if slope_1 is not None else 999.0
                sl_2 = slope_2 if slope_2 is not None else 999.0
                sl_3 = slope_3 if slope_3 is not None else 999.0
                slope_ok_1 = bool(
                    sl_1 < threshold_1
                    or ((sl_1 < 0) and (sl_2 < threshold_2))
                    or ((sl_1 < 0) and (sl_2 < 0) and (sl_3 < threshold_3))
                )
            state = {
                "symbol": symbol,
                "px": price,
                "avg_px": mean(list(st.prices)[-20:]),
                "max_seen": st.max_seen,
                "min_seen": st.min_seen,
                "open_px": st.open_px,
                "last_close": last_close,
                "price_ema": ema_value,
                "zz_trend": zz_trend,
                "slope_down_ok": slope_ok_1,
                "slope": slope_1,
                "slope_2": slope_2,
                "slope_3": slope_3,
                "sweet_ok": is_sweet_range(bid, last_close),
                "is_open": "isOpen" in tick,
                "dc_stage": None,
                "dc_stage_states": {},
                "new_high_recent": price >= st.max_seen * float(cfg.get("new_high_tol_pct", 0.97)),
                "last_qualified_high_ts": st.last_qualified_high_ts,
                "now_time": now_time,
                "is_v_shape": False,
                "v_pivot_price": None,
                "v_time": None,
                "v_post_high": None,
                "confirm_end": None,
                "confirm_close": None,
                "now_ts": ts,
                "upper_limit_start_time": None,
                "vcp_is_tight": False,
                "vcp_range_pct": 999.0,
                "vcp_box_high": 0.0,
                "vcp_vol_dryup_ok": False,
                "vcp_current_vol_ratio": 0.0,
            }
            decision = evaluator(state, cfg)
            enter = decision.enter
            reason = decision.reason
            if enforce_one_enter_per_symbol and enter:
                if symbol in entered_symbols:
                    enter = False
                    reason = "lot_limit_reached_replay"
                else:
                    entered_symbols.add(symbol)
            output_state = dict(state)
            output_state["now_time"] = now_time.isoformat()
            rows.append({"symbol": symbol, "gate": gate, "enter": enter, "reason": reason, "state": output_state})
    return rows


def run(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root).resolve()
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(Path(args.config).resolve() if args.config else None)
    symbols = {item.strip() for item in (args.symbols or "").split(",") if item.strip()} or None
    rows = replay_session(data_root=data_root, machine=args.machine, date=args.date, gate=args.gate, cfg=cfg, max_rows=args.max_rows, end_local=args.end_local, enforce_one_enter_per_symbol=args.enforce_one_enter_per_symbol, symbols=symbols)
    if not rows:
        raise LegacyEquivalenceError("replay emitted no rows")
    trace_path = output_dir / "latest_legacy_replay_decisions.jsonl"
    summary_path = output_dir / "latest_legacy_replay_summary.json"
    with trace_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "kind": "steamer_card_engine.latest_legacy_replay.v1",
        "machine": args.machine,
        "date": args.date,
        "gate": args.gate,
        "rows": len(rows),
        "end_local": args.end_local,
        "enter_true": sum(1 for row in rows if row["enter"]),
        "enforce_one_enter_per_symbol": args.enforce_one_enter_per_symbol,
        "symbols": sorted(symbols) if symbols else None,
        "reason_top20": dict(__import__("collections").Counter(row["reason"] for row in rows).most_common(20)),
        "trace_path": str(trace_path),
        "summary_path": str(summary_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "enter_true": summary["enter_true"], "summary_path": str(summary_path), "trace_path": str(trace_path)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit latest-legacy-compatible replay decisions from recorded ticks.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--machine", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--gate", default="REV_SHORT_AFTER_UP")
    parser.add_argument("--config")
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--end-local", help="Optional inclusive local time upper bound, e.g. 09:30:00")
    parser.add_argument("--enforce-one-enter-per-symbol", action="store_true", help="Replay a minimal order-layer lot limit: only the first enter per symbol remains enter=true.")
    parser.add_argument("--symbols", help="Optional comma-separated symbol filter for scoped replay.")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
