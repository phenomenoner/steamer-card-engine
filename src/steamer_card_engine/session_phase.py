from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo


TWSE_TIMEZONE = ZoneInfo("Asia/Taipei")
TWSE_CALENDAR = "TWSE"
TWSE_SESSION_PHASE_CONTRACT_VERSION = "twse-session-phase/v1"

_PRE_OPEN_END = time(9, 0, 0)
_OPEN_DISCOVERY_END = time(9, 1, 0)
_ENTRY_CUTOFF = time(12, 1, 0)
_FORCED_EXIT_START = time(13, 18, 0)
_FINAL_AUCTION_START = time(13, 25, 0)
_SESSION_END = time(13, 30, 0)

ENTRY_ALLOWED_PHASES = frozenset({"regular_session"})


@dataclass(frozen=True, slots=True)
class SessionPhaseAssessment:
    phase: str
    semantic_label: str
    local_time: str
    timezone: str
    calendar: str
    allows_regular_entry: bool
    allows_exit_monitoring: bool
    forced_exit_active: bool
    contract_status: str
    violation_code: str | None = None
    default_order_profile: str | None = None
    requested_user_def_suffix: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SessionPhaseTraceEntry:
    phase: str
    semantic_label: str
    effective_at_utc: str
    local_time: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SessionPhaseContract:
    version: str
    timezone: str
    calendar: str
    entry_allowed_phases: tuple[str, ...]
    policy_windows: dict[str, str]
    phases: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


TWSE_SESSION_PHASE_CONTRACT = SessionPhaseContract(
    version=TWSE_SESSION_PHASE_CONTRACT_VERSION,
    timezone="Asia/Taipei",
    calendar=TWSE_CALENDAR,
    entry_allowed_phases=tuple(sorted(ENTRY_ALLOWED_PHASES)),
    policy_windows={
        "pre_open_end": _PRE_OPEN_END.isoformat(),
        "open_discovery_end": _OPEN_DISCOVERY_END.isoformat(),
        "entry_cutoff": _ENTRY_CUTOFF.isoformat(),
        "forced_exit_start": _FORCED_EXIT_START.isoformat(),
        "final_auction_start": _FINAL_AUCTION_START.isoformat(),
        "session_end": _SESSION_END.isoformat(),
    },
    phases=(
        {
            "phase": "pre_open_trial_match",
            "semantic_label": "pre_open_warmup",
            "start_local": None,
            "end_local": _PRE_OPEN_END.isoformat(),
            "allows_regular_entry": False,
            "allows_exit_monitoring": False,
            "forced_exit_active": False,
            "default_order_profile": None,
            "requested_user_def_suffix": None,
        },
        {
            "phase": "regular_session_open",
            "semantic_label": "open_discovery",
            "start_local": _PRE_OPEN_END.isoformat(),
            "end_local": _OPEN_DISCOVERY_END.isoformat(),
            "allows_regular_entry": False,
            "allows_exit_monitoring": True,
            "forced_exit_active": False,
            "default_order_profile": None,
            "requested_user_def_suffix": None,
        },
        {
            "phase": "regular_session",
            "semantic_label": "regular_entry",
            "start_local": _OPEN_DISCOVERY_END.isoformat(),
            "end_local": _ENTRY_CUTOFF.isoformat(),
            "allows_regular_entry": True,
            "allows_exit_monitoring": True,
            "forced_exit_active": False,
            "default_order_profile": "regular-entry-market-ioc",
            "requested_user_def_suffix": "Enter",
        },
        {
            "phase": "risk_monitor_only",
            "semantic_label": "exit_monitoring_only",
            "start_local": _ENTRY_CUTOFF.isoformat(),
            "end_local": _FORCED_EXIT_START.isoformat(),
            "allows_regular_entry": False,
            "allows_exit_monitoring": True,
            "forced_exit_active": False,
            "default_order_profile": "exit-monitor-market-ioc",
            "requested_user_def_suffix": "Exit",
        },
        {
            "phase": "forced_exit",
            "semantic_label": "forced_close",
            "start_local": _FORCED_EXIT_START.isoformat(),
            "end_local": _FINAL_AUCTION_START.isoformat(),
            "allows_regular_entry": False,
            "allows_exit_monitoring": True,
            "forced_exit_active": True,
            "default_order_profile": "forced-exit-market-rod",
            "requested_user_def_suffix": "Close",
        },
        {
            "phase": "final_auction",
            "semantic_label": "final_auction_flatten",
            "start_local": _FINAL_AUCTION_START.isoformat(),
            "end_local": _SESSION_END.isoformat(),
            "allows_regular_entry": False,
            "allows_exit_monitoring": True,
            "forced_exit_active": True,
            "default_order_profile": "final-auction-flatten-rod",
            "requested_user_def_suffix": "Close",
        },
        {
            "phase": "session_closed",
            "semantic_label": "post_close",
            "start_local": _SESSION_END.isoformat(),
            "end_local": None,
            "allows_regular_entry": False,
            "allows_exit_monitoring": False,
            "forced_exit_active": False,
            "default_order_profile": None,
            "requested_user_def_suffix": None,
        },
    ),
)


def parse_utc_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = parsed.astimezone(UTC)
        return parsed

    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            numeric = float(text)
        else:
            text = text.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            else:
                parsed = parsed.astimezone(UTC)
            return parsed
    else:
        return None

    abs_numeric = abs(numeric)
    if abs_numeric >= 1e18:
        seconds = numeric / 1e9
    elif abs_numeric >= 1e15:
        seconds = numeric / 1e6
    elif abs_numeric >= 1e12:
        seconds = numeric / 1e3
    else:
        seconds = numeric

    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def to_utc_iso(value: Any) -> str | None:
    parsed = parse_utc_timestamp(value)
    if parsed is None:
        return None
    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def assess_twse_session_phase(value: Any) -> SessionPhaseAssessment | None:
    parsed = parse_utc_timestamp(value)
    if parsed is None:
        return None

    local = parsed.astimezone(TWSE_TIMEZONE)
    local_clock = local.time()

    if local_clock < _PRE_OPEN_END:
        return SessionPhaseAssessment(
            phase="pre_open_trial_match",
            semantic_label="pre_open_warmup",
            local_time=local.strftime("%H:%M:%S"),
            timezone=TWSE_SESSION_PHASE_CONTRACT.timezone,
            calendar=TWSE_SESSION_PHASE_CONTRACT.calendar,
            allows_regular_entry=False,
            allows_exit_monitoring=False,
            forced_exit_active=False,
            contract_status="blocked",
            violation_code="pre-open-regular-entry-blocked",
            default_order_profile=None,
            requested_user_def_suffix=None,
        )
    if local_clock < _OPEN_DISCOVERY_END:
        return SessionPhaseAssessment(
            phase="regular_session_open",
            semantic_label="open_discovery",
            local_time=local.strftime("%H:%M:%S"),
            timezone=TWSE_SESSION_PHASE_CONTRACT.timezone,
            calendar=TWSE_SESSION_PHASE_CONTRACT.calendar,
            allows_regular_entry=False,
            allows_exit_monitoring=True,
            forced_exit_active=False,
            contract_status="blocked",
            violation_code="open-discovery-regular-entry-blocked",
            default_order_profile=None,
            requested_user_def_suffix=None,
        )
    if local_clock < _ENTRY_CUTOFF:
        return SessionPhaseAssessment(
            phase="regular_session",
            semantic_label="regular_entry",
            local_time=local.strftime("%H:%M:%S"),
            timezone=TWSE_SESSION_PHASE_CONTRACT.timezone,
            calendar=TWSE_SESSION_PHASE_CONTRACT.calendar,
            allows_regular_entry=True,
            allows_exit_monitoring=True,
            forced_exit_active=False,
            contract_status="allowed",
            violation_code=None,
            default_order_profile="regular-entry-market-ioc",
            requested_user_def_suffix="Enter",
        )
    if local_clock < _FORCED_EXIT_START:
        return SessionPhaseAssessment(
            phase="risk_monitor_only",
            semantic_label="exit_monitoring_only",
            local_time=local.strftime("%H:%M:%S"),
            timezone=TWSE_SESSION_PHASE_CONTRACT.timezone,
            calendar=TWSE_SESSION_PHASE_CONTRACT.calendar,
            allows_regular_entry=False,
            allows_exit_monitoring=True,
            forced_exit_active=False,
            contract_status="blocked",
            violation_code="entry-cutoff-regular-entry-blocked",
            default_order_profile="exit-monitor-market-ioc",
            requested_user_def_suffix="Exit",
        )
    if local_clock < _FINAL_AUCTION_START:
        return SessionPhaseAssessment(
            phase="forced_exit",
            semantic_label="forced_close",
            local_time=local.strftime("%H:%M:%S"),
            timezone=TWSE_SESSION_PHASE_CONTRACT.timezone,
            calendar=TWSE_SESSION_PHASE_CONTRACT.calendar,
            allows_regular_entry=False,
            allows_exit_monitoring=True,
            forced_exit_active=True,
            contract_status="blocked",
            violation_code="forced-exit-regular-entry-blocked",
            default_order_profile="forced-exit-market-rod",
            requested_user_def_suffix="Close",
        )
    if local_clock < _SESSION_END:
        return SessionPhaseAssessment(
            phase="final_auction",
            semantic_label="final_auction_flatten",
            local_time=local.strftime("%H:%M:%S"),
            timezone=TWSE_SESSION_PHASE_CONTRACT.timezone,
            calendar=TWSE_SESSION_PHASE_CONTRACT.calendar,
            allows_regular_entry=False,
            allows_exit_monitoring=True,
            forced_exit_active=True,
            contract_status="blocked",
            violation_code="final-auction-regular-entry-blocked",
            default_order_profile="final-auction-flatten-rod",
            requested_user_def_suffix="Close",
        )
    return SessionPhaseAssessment(
        phase="session_closed",
        semantic_label="post_close",
        local_time=local.strftime("%H:%M:%S"),
        timezone=TWSE_SESSION_PHASE_CONTRACT.timezone,
        calendar=TWSE_SESSION_PHASE_CONTRACT.calendar,
        allows_regular_entry=False,
        allows_exit_monitoring=False,
        forced_exit_active=False,
        contract_status="blocked",
        violation_code="session-closed-regular-entry-blocked",
        default_order_profile=None,
        requested_user_def_suffix=None,
    )


def build_twse_phase_contract() -> dict[str, Any]:
    return TWSE_SESSION_PHASE_CONTRACT.as_dict()


def append_phase_transition(
    trace: list[SessionPhaseTraceEntry],
    *,
    timestamp_utc: str | None,
    assessment: SessionPhaseAssessment | None,
) -> None:
    if timestamp_utc is None or assessment is None:
        return
    if trace and trace[-1].phase == assessment.phase:
        return
    trace.append(
        SessionPhaseTraceEntry(
            phase=assessment.phase,
            semantic_label=assessment.semantic_label,
            effective_at_utc=timestamp_utc,
            local_time=assessment.local_time,
        )
    )
