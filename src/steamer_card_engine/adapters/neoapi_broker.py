from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import time
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
            "sell_first_daytrade": bool(status & 8),
            "limitdown_price": limit_down,
            "limitup_price": limit_up,
        }
        if not getattr(quote, "is_success", False) or not (status & 8) or limit_down is None or limit_up is None:
            receipt["status"] = "quote-gate-failed"
            receipt["issues"].append("quote_gate_failed")
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

        sold_qty, sell_terminal = self._wait_filled(sdk, account, plan.symbol, sell_no)
        receipt["steps"].append({"step": "entry-fill", "filled_qty": sold_qty, "terminal_order": sell_terminal})
        if sold_qty <= 0:
            receipt["status"] = "entry-not-filled-no-position"
            return receipt

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

        bought_qty, buy_terminal = self._wait_filled(sdk, account, plan.symbol, buy_no)
        receipt["steps"].append({"step": "buyback-fill", "filled_qty": bought_qty, "terminal_order": buy_terminal})
        if bought_qty >= sold_qty:
            receipt["status"] = "round-trip-closed"
        else:
            receipt["status"] = "open-risk-partial-buyback"
            receipt["issues"].append(f"open_short_qty_{sold_qty - bought_qty}")
        receipt["ended_at"] = datetime.now().isoformat()
        return receipt

    def _wait_filled(self, sdk: Any, account: Any, symbol: str, order_no: str | None) -> tuple[int, dict[str, Any]]:
        terminal: dict[str, Any] = {}
        deadline = time.time() + 20
        while time.time() < deadline:
            result = sdk.stock.get_order_results(account)
            rows = list(getattr(result, "data", []) or [])
            terminal = _find_order(rows, order_no=order_no, symbol=symbol)
            filled_qty = _to_int(terminal.get("filled_qty") or terminal.get("filledQty"), 0)
            status = _to_int(terminal.get("status"), -1)
            if filled_qty > 0 or status in {30, 50, 90}:
                return filled_qty, terminal
            time.sleep(1)
        return _to_int(terminal.get("filled_qty") or terminal.get("filledQty"), 0), terminal
