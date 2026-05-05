from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
import re
import time
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from steamer_card_engine.live_execution import RoundTripPlan


def _get_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except Exception:
        return default


def _public_obj(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    out: dict[str, Any] = {}
    for key in dir(obj):
        if key.startswith("_") or key in {"account", "branch_no", "name"}:
            continue
        try:
            value = getattr(obj, key)
        except Exception:
            continue
        if callable(value):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
        else:
            out[key] = str(value)
    return out



def _quote_value(payload: Any, *names: str) -> Any:
    if isinstance(payload, dict):
        for name in names:
            if name in payload:
                return payload.get(name)
    return _get_attr(payload, *names)


def _safe_market_quote(sdk: Any, symbol: str) -> dict[str, Any]:
    try:
        sdk.init_realtime()
        intraday = sdk.marketdata.rest_client.stock.intraday
        payload = intraday.quote(symbol=symbol)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    price = _to_float(_quote_value(payload, "price", "lastPrice", "closePrice"))
    reference = _to_float(_quote_value(payload, "previousClose", "referencePrice"))
    change_pct = _to_float(_quote_value(payload, "changePercent", "percentChange"))
    if change_pct is None and price is not None and reference not in {None, 0}:
        change_pct = (price - reference) / reference * 100
    return {
        "ok": price is not None,
        "price": price,
        "reference_price": reference,
        "change_percent": change_pct,
    }


def _entry_filter_allows(plan: RoundTripPlan, market_quote: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    policy = plan.entry_filter or {}
    price = market_quote.get("price")
    change_pct = market_quote.get("change_percent")
    max_price = _to_float(policy.get("max_price"))
    min_change = _to_float(policy.get("min_change_percent"))
    max_change = _to_float(policy.get("max_change_percent"))
    if not market_quote.get("ok"):
        issues.append("entry_market_quote_unavailable")
    if max_price is not None and (price is None or price >= max_price):
        issues.append("entry_price_filter_failed")
    if min_change is not None and (change_pct is None or change_pct < min_change):
        issues.append("entry_change_percent_below_min")
    if max_change is not None and (change_pct is None or change_pct > max_change):
        issues.append("entry_change_percent_above_max")
    return not issues, issues


def _short_pnl_percent(*, entry_price: float, current_price: float) -> float:
    if entry_price <= 0:
        return 0.0
    return (entry_price - current_price) / entry_price * 100

def _sanitize_response(response: Any) -> dict[str, Any]:
    data = getattr(response, "data", None)
    if isinstance(data, list):
        public_data: Any = [_public_obj(row) for row in data[:20]]
    else:
        public_data = _public_obj(data)
    return {
        "type": type(response).__name__,
        "is_success": bool(getattr(response, "is_success", False)),
        "message": str(getattr(response, "message", "") or "")[:300],
        "data": public_data,
    }



def _filled_qty(row: dict[str, Any]) -> int:
    return _to_int(row.get("filled_qty") or row.get("filledQty") or row.get("filled_quantity") or row.get("filledQuantity"), 0)


def _filled_money(row: dict[str, Any]) -> float | None:
    return _to_float(row.get("filled_money") or row.get("filledMoney") or row.get("filled_amount") or row.get("filledAmount"))


def _filled_avg_price(row: dict[str, Any]) -> float | None:
    return _to_float(
        row.get("filled_avg_price")
        or row.get("filledAvgPrice")
        or row.get("avg_price")
        or row.get("avgPrice")
    )


def _filled_price(row: dict[str, Any]) -> float | None:
    return _to_float(row.get("filled_price") or row.get("filledPrice"))


def _average_filled_price(row: dict[str, Any]) -> float | None:
    avg = _filled_avg_price(row)
    if avg is not None:
        return avg
    price = _filled_price(row)
    if price is not None:
        return price
    qty = _filled_qty(row)
    money = _filled_money(row)
    if qty > 0 and money is not None:
        return money / qty
    return None


def _fill_source(row: dict[str, Any], default: str) -> str:
    if _filled_avg_price(row) is not None:
        return f"{default}.filled_avg_price"
    if _filled_price(row) is not None:
        return f"{default}.filled_price"
    if _filled_money(row) is not None and _filled_qty(row) > 0:
        return f"{default}.filled_money/filled_qty"
    return "missing"

def _order_no(response: Any) -> str | None:
    data = getattr(response, "data", None)
    value = _get_attr(data, "order_no", "orderNo", "ord_no", "order_id")
    return str(value) if value else None


def _find_order(rows: list[Any], *, order_no: str | None, symbol: str) -> dict[str, Any]:
    fallback: dict[str, Any] = {}
    for row in rows:
        public = _public_obj(row) or {}
        if symbol and symbol not in {str(public.get("stock_no", "")), str(public.get("symbol", "")), str(public.get("stockNo", ""))}:
            continue
        if order_no:
            order_values = {
                str(public.get("order_no", "")),
                str(public.get("orderNo", "")),
                str(public.get("ord_no", "")),
                str(public.get("order_id", "")),
            }
            if order_no not in order_values:
                continue
        fallback = public
    return fallback


@dataclass(slots=True)
class _FillReportStore:
    reports: list[dict[str, Any]] = field(default_factory=list)

    def callback(self, code: Any, content: Any) -> None:
        public = _public_obj(content) or {}
        public["callback_code"] = str(code) if code is not None else None
        public["received_at"] = datetime.now().isoformat()
        self.reports.append(public)
        self.reports = self.reports[-100:]

    def match(self, *, order_no: str | None, symbol: str) -> dict[str, Any]:
        matched: dict[str, Any] = {}
        for row in self.reports:
            row_order_no = str(row.get("order_no") or row.get("orderNo") or row.get("ord_no") or row.get("order_id") or "")
            row_symbol = str(row.get("stock_no") or row.get("stockNo") or row.get("symbol") or "")
            if order_no and row_order_no and row_order_no != order_no:
                continue
            if symbol and row_symbol and row_symbol != symbol:
                continue
            if _filled_qty(row) > 0 and _average_filled_price(row) is not None:
                matched = row
        return matched


@dataclass(slots=True)
class NeoApiCredentials:
    personal_id: str
    api_key: str
    cert_path: Path
    cert_password: str


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "").replace("_", "-")


def _pick(values: dict[str, str], names: list[str]) -> str | None:
    for name in names:
        value = values.get(_normalize_key(name))
        if value:
            return value
    return None


def load_neoapi_credentials(secret_dir: Path) -> NeoApiCredentials:
    info_path = secret_dir / "login_info.txt"
    values: dict[str, str] = {}
    loose: list[str] = []
    for line in info_path.read_text(errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
        elif ":" in stripped:
            key, value = stripped.split(":", 1)
        else:
            loose.append(stripped)
            continue
        values[_normalize_key(key)] = value.strip().strip("\"'")
    if loose:
        values["cert-pwd"] = loose[-1].strip().strip("\"'")

    personal_id = _pick(values, ["id", "身分證", "身份證", "account"])
    api_key = _pick(values, ["api-key", "apikey", "api key", "password", "pwd", "密碼"])
    cert = _pick(values, ["憑證檔", "cert", "cert-file", "certpath", "憑證"])
    cert_password = _pick(values, ["cert-pwd", "certpwd", "cert-password", "憑證密碼", "ca-password"])
    if cert_password and ("預設密碼" in cert_password or "default" in cert_password.lower()):
        cert_password = personal_id

    cert_path = Path(cert) if cert else None
    if cert_path is None:
        matches = sorted(list(secret_dir.glob("*.p12")) + list(secret_dir.glob("*.pfx")))
        cert_path = matches[0] if matches else None
    if cert_path is not None and not cert_path.is_absolute():
        cert_path = secret_dir / cert_path

    missing = [
        name
        for name, value in [
            ("personal_id", personal_id),
            ("api_key", api_key),
            ("cert_path", cert_path),
            ("cert_password", cert_password),
        ]
        if not value
    ]
    if missing:
        raise ValueError("missing_neoapi_credentials:" + ",".join(missing))
    assert personal_id and api_key and cert_path and cert_password
    if not re.match(r"^[A-Z][0-9]{9}$", personal_id):
        raise ValueError("invalid_neoapi_personal_id_shape")
    if not cert_path.exists():
        raise FileNotFoundError("neoapi_cert_file_missing")
    return NeoApiCredentials(
        personal_id=personal_id,
        api_key=api_key,
        cert_path=cert_path,
        cert_password=cert_password,
    )


@dataclass(slots=True)
class NeoApiBrokerAdapter:
    """Thin NeoAPI round-trip adapter.

    The SDK is injected/lazy-imported to keep strategy/runtime import surfaces free
    of broker dependencies and to make tests use fake SDKs without credentials.
    """

    credentials: NeoApiCredentials
    expected_account_no: str | None = None
    sdk_factory: Any | None = None
    constants_factory: Any | None = None
    adapter_id: str = "neoapi-live"

    def _sdk(self) -> Any:
        if self.sdk_factory is not None:
            return self.sdk_factory()
        from fubon_neo.sdk import FubonSDK  # type: ignore

        return FubonSDK(30, 2)

    def _constants(self) -> dict[str, Any]:
        if self.constants_factory is not None:
            return self.constants_factory()
        from fubon_neo.constant import BSAction, MarketType, OrderType, PriceType, TimeInForce  # type: ignore
        from fubon_neo.sdk import Order  # type: ignore

        return {
            "Order": Order,
            "BSAction": BSAction,
            "MarketType": MarketType,
            "OrderType": OrderType,
            "PriceType": PriceType,
            "TimeInForce": TimeInForce,
        }

    def execute_round_trip(self, plan: RoundTripPlan) -> dict[str, Any]:
        constants = self._constants()
        sdk = self._sdk()
        fill_store = _FillReportStore()
        started_at = datetime.now().isoformat()
        receipt: dict[str, Any] = {
            "schema_version": "steamer-live-execution-roundtrip/v1",
            "adapter_id": self.adapter_id,
            "mode": "live",
            "plan_id": plan.plan_id,
            "symbol": plan.symbol,
            "quantity": plan.quantity,
            "started_at": started_at,
            "status": "unknown",
            "steps": [],
            "issues": [],
        }

        if hasattr(sdk, "set_on_filled"):
            try:
                sdk.set_on_filled(fill_store.callback)
                receipt["active_fill_callback"] = {"registered": True}
            except Exception as exc:
                receipt["active_fill_callback"] = {"registered": False, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
        else:
            receipt["active_fill_callback"] = {"registered": False, "error": "sdk.set_on_filled unavailable"}

        login = sdk.apikey_login(
            self.credentials.personal_id,
            self.credentials.api_key,
            str(self.credentials.cert_path),
            self.credentials.cert_password,
        )
        receipt["login"] = {
            "ok": bool(getattr(login, "is_success", False)),
            "accounts_count": len(getattr(login, "data", []) or []),
        }
        if not getattr(login, "is_success", False):
            receipt["status"] = "login-failed"
            receipt["issues"].append("login_failed")
            return receipt

        accounts = list(getattr(login, "data", []) or [])
        account = next((row for row in accounts if str(getattr(row, "account_type", "")).lower() == "stock"), accounts[0])
        if self.expected_account_no:
            actual_account_no = str(
                _get_attr(account, "account", "account_no", "accountNo", "account_id", "accountId") or ""
            )
            receipt["account_gate"] = {
                "expected_account_no": self.expected_account_no,
                "actual_account_no": actual_account_no,
                "matched": actual_account_no == self.expected_account_no,
            }
            if actual_account_no != self.expected_account_no:
                receipt["status"] = "account-mismatch-refused"
                receipt["issues"].append("account_mismatch")
                return receipt
        quote = sdk.stock.query_symbol_quote(account, plan.symbol)
        quote_data = getattr(quote, "data", None)
        status = _to_int(_get_attr(quote_data, "status", "disposition_status"), -1)
        limit_down = _to_float(_get_attr(quote_data, "limitdown_price", "limit_down_price", "limitDownPrice"))
        limit_up = _to_float(_get_attr(quote_data, "limitup_price", "limit_up_price", "limitUpPrice"))
        receipt["quote_gate"] = {
            "ok": bool(getattr(quote, "is_success", False)),
            "status": status,
            "sell_first_daytrade": bool(status >= 0 and (status & 8)),
            "limitdown_price": limit_down,
            "limitup_price": limit_up,
        }
        if not getattr(quote, "is_success", False) or not (status >= 0 and (status & 8)) or limit_down is None or limit_up is None:
            receipt["status"] = "quote-gate-failed"
            receipt["issues"].append("quote_gate_failed")
            return receipt

        if plan.entry_filter:
            market_quote = _safe_market_quote(sdk, plan.symbol)
            receipt["entry_filter"] = {"policy": plan.entry_filter, "market_quote": market_quote}
            entry_allowed, entry_issues = _entry_filter_allows(plan, market_quote)
            if not entry_allowed:
                receipt["status"] = "entry-filter-refused"
                receipt["issues"].extend(entry_issues)
                return receipt

        Order = constants["Order"]
        sell_order = Order(
            buy_sell=constants["BSAction"].Sell,
            symbol=plan.symbol,
            price=str(limit_down),
            quantity=plan.quantity,
            market_type=constants["MarketType"].Common,
            price_type=constants["PriceType"].Limit,
            time_in_force=constants["TimeInForce"].IOC,
            order_type=constants["OrderType"].DayTrade,
            user_def="OCSELL",
        )
        sell_response = sdk.stock.place_order(account, sell_order)
        sell_no = _order_no(sell_response)
        receipt["steps"].append(
            {"step": "sell-first-daytrade", "order_no": sell_no, "response": _sanitize_response(sell_response)}
        )
        if not getattr(sell_response, "is_success", False):
            receipt["status"] = "entry-place-failed"
            receipt["issues"].append("entry_place_failed")
            return receipt

        sold_qty, sell_terminal = self._wait_filled(sdk, account, plan.symbol, sell_no, fill_store=fill_store)
        receipt["steps"].append({"step": "entry-fill", "filled_qty": sold_qty, "terminal_order": sell_terminal})
        if sold_qty <= 0:
            receipt["status"] = "entry-not-filled-no-position"
            return receipt

        entry_price = _average_filled_price(sell_terminal)
        receipt["entry_fill_price"] = {
            "source": _fill_source(sell_terminal, str(sell_terminal.get("fill_source") or "fill")),
            "filled_money": _filled_money(sell_terminal),
            "filled_qty": _filled_qty(sell_terminal),
            "filled_avg_price": _filled_avg_price(sell_terminal),
            "filled_price": _filled_price(sell_terminal),
            "average_price": entry_price,
        }
        if entry_price is None:
            receipt["status"] = "entry-fill-price-missing"
            receipt["issues"].append("missing_filled_money_or_qty_for_entry_price")
            return receipt
        exit_trigger = self._wait_exit_trigger(sdk=sdk, plan=plan, entry_price=entry_price)
        receipt["exit_trigger"] = exit_trigger

        buy_order = Order(
            buy_sell=constants["BSAction"].Buy,
            symbol=plan.symbol,
            price=str(limit_up),
            quantity=sold_qty,
            market_type=constants["MarketType"].Common,
            price_type=constants["PriceType"].Limit,
            time_in_force=constants["TimeInForce"].IOC,
            order_type=constants["OrderType"].Stock,
            user_def="OCBUY",
        )
        buy_response = sdk.stock.place_order(account, buy_order)
        buy_no = _order_no(buy_response)
        receipt["steps"].append(
            {"step": "buyback", "order_no": buy_no, "response": _sanitize_response(buy_response)}
        )
        if not getattr(buy_response, "is_success", False):
            receipt["status"] = "open-risk-buyback-place-failed"
            receipt["issues"].append(f"open_short_qty_{sold_qty}")
            return receipt

        bought_qty, buy_terminal = self._wait_filled(sdk, account, plan.symbol, buy_no, fill_store=fill_store)
        receipt["steps"].append({"step": "buyback-fill", "filled_qty": bought_qty, "terminal_order": buy_terminal})
        if bought_qty >= sold_qty:
            receipt["status"] = "round-trip-closed"
        else:
            receipt["status"] = "open-risk-partial-buyback"
            receipt["issues"].append(f"open_short_qty_{sold_qty - bought_qty}")
        receipt["ended_at"] = datetime.now().isoformat()
        return receipt

    def _wait_exit_trigger(self, *, sdk: Any, plan: RoundTripPlan, entry_price: float) -> dict[str, Any]:
        policy = plan.exit_policy or {}
        take_profit = _to_float(policy.get("take_profit_percent"))
        stop_loss = _to_float(policy.get("stop_loss_percent"))
        timezone_name = str(policy.get("timezone") or "Asia/Taipei")
        force_cover_time = str(policy.get("force_cover_time") or "")
        deadline = time.time()
        try:
            if force_cover_time:
                hh, mm, ss = [int(part) for part in force_cover_time.split(":")]
                tz = ZoneInfo(timezone_name)
                now = datetime.now(tz)
                force_dt = datetime.combine(now.date(), dt_time(hh, mm, ss), tzinfo=tz)
                deadline = force_dt.timestamp()
        except Exception:
            deadline = time.time()
        # If no exit policy is supplied, preserve the old stage-1 immediate-cover smoke behavior.
        if not policy:
            return {"reason": "immediate-stage1-smoke", "entry_price": entry_price}
        last_quote: dict[str, Any] = {}
        while True:
            market_quote = _safe_market_quote(sdk, plan.symbol)
            last_quote = market_quote
            price = market_quote.get("price")
            if price is not None:
                pnl_pct = _short_pnl_percent(entry_price=entry_price, current_price=float(price))
                if take_profit is not None and pnl_pct >= take_profit:
                    return {"reason": "take-profit", "entry_price": entry_price, "current_price": price, "pnl_percent": pnl_pct}
                if stop_loss is not None and pnl_pct <= stop_loss:
                    return {"reason": "stop-loss", "entry_price": entry_price, "current_price": price, "pnl_percent": pnl_pct}
            if time.time() >= deadline:
                return {"reason": "force-cover-time", "entry_price": entry_price, "last_quote": last_quote, "deadline_epoch": deadline}
            time.sleep(1)

    def _wait_filled(
        self,
        sdk: Any,
        account: Any,
        symbol: str,
        order_no: str | None,
        *,
        fill_store: _FillReportStore | None = None,
        timeout_seconds: int = 35,
        readback_interval_seconds: int = 30,
    ) -> tuple[int, dict[str, Any]]:
        terminal: dict[str, Any] = {}
        last_readback = 0.0
        readback_seen_at: float | None = None
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if fill_store is not None:
                active = fill_store.match(order_no=order_no, symbol=symbol)
                if active:
                    active = dict(active)
                    active["fill_source"] = "active_filled_callback"
                    return _filled_qty(active), active

            now = time.time()
            should_readback = not terminal or now - last_readback >= readback_interval_seconds
            if should_readback:
                last_readback = now
                result = sdk.stock.get_order_results(account)
                rows = list(getattr(result, "data", []) or [])
                terminal = _find_order(rows, order_no=order_no, symbol=symbol)
                filled_qty = _filled_qty(terminal)
                status = _to_int(terminal.get("status"), -1)
                if filled_qty > 0 or status in {30, 50, 90}:
                    readback_seen_at = now

            # Use readback as a bounded safe-net, but give the lower-latency active
            # filled callback a short grace window before returning readback data.
            if readback_seen_at is not None and now - readback_seen_at >= 2:
                terminal = dict(terminal)
                terminal["fill_source"] = "order_results_readback"
                return _filled_qty(terminal), terminal
            time.sleep(0.2)

        terminal = dict(terminal)
        if terminal:
            terminal["fill_source"] = "order_results_readback_timeout"
        return _filled_qty(terminal), terminal
