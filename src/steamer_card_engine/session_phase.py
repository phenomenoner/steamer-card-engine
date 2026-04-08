from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo


TWSE_TIMEZONE = ZoneInfo("Asia/Taipei")
TWSE_CALENDAR = "TWSE"
TWSE_SESSION_PHASE_CONTRACT_VERSION = "twse-session-phase/v0"

_PRE_OPEN_END = time(9, 0, 0)
_REGULAR_OPEN_END = time(9, 1, 0)
_FINAL_AUCTION_START = time(13, 25, 0)
_SESSION_END = time(13, 30, 0)

ENTRY_ALLOWED_PHASES = frozenset({"regular_session"})


@dataclass(frozen=True, slots=True)
class SessionPhaseAssessment:
    phase: str
    local_time: str
    timezone: str
    calendar: str
    allows_regular_entry: bool
    contract_status: str
    violation_code: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SessionPhaseTraceEntry:
    phase: str
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
    phases: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


TWSE_SESSION_PHASE_CONTRACT = SessionPhaseContract(
    version=TWSE_SESSION_PHASE_CONTRACT_VERSION,
    timezone="Asia/Taipei",
    calendar=TWSE_CALENDAR,
    entry_allowed_phases=tuple(sorted(ENTRY_ALLOWED_PHASES)),
    phases=(
        {
            "phase": "pre_open_trial_match",
            "start_local": None,
            "end_local": _PRE_OPEN_END.isoformat(),
            "allows_regular_entry": False,
        },
        {
            "phase": "regular_session_open",
            "start_local": _PRE_OPEN_END.isoformat(),
            "end_local": _REGULAR_OPEN_END.isoformat(),
            "allows_regular_entry": False,
        },
        {
            "phase": "regular_session",
            "start_local": _REGULAR_OPEN_END.isoformat(),
            "end_local": _FINAL_AUCTION_START.isoformat(),
            "allows_regular_entry": True,
        },
        {
            "phase": "final_auction",
            "start_local": _FINAL_AUCTION_START.isoformat(),
            "end_local": _SESSION_END.isoformat(),
            "allows_regular_entry": False,
        },
        {
            "phase": "session_closed",
            "start_local": _SESSION_END.isoformat(),
            "end_local": None,
            "allows_regular_entry": False,
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
        phase = "pre_open_trial_match"
        allows_regular_entry = False
        contract_status = "blocked"
        violation_code = "pre-open-regular-entry-blocked"
    elif local_clock < _REGULAR_OPEN_END:
        phase = "regular_session_open"
        allows_regular_entry = False
        contract_status = "blocked"
        violation_code = "open-discovery-regular-entry-blocked"
    elif local_clock < _FINAL_AUCTION_START:
        phase = "regular_session"
        allows_regular_entry = True
        contract_status = "allowed"
        violation_code = None
    elif local_clock < _SESSION_END:
        phase = "final_auction"
        allows_regular_entry = False
        contract_status = "blocked"
        violation_code = "final-auction-regular-entry-blocked"
    else:
        phase = "session_closed"
        allows_regular_entry = False
        contract_status = "blocked"
        violation_code = "session-closed-regular-entry-blocked"

    return SessionPhaseAssessment(
        phase=phase,
        local_time=local.strftime("%H:%M:%S"),
        timezone=TWSE_SESSION_PHASE_CONTRACT.timezone,
        calendar=TWSE_SESSION_PHASE_CONTRACT.calendar,
        allows_regular_entry=allows_regular_entry,
        contract_status=contract_status,
        violation_code=violation_code,
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
            effective_at_utc=timestamp_utc,
            local_time=assessment.local_time,
        )
    )
