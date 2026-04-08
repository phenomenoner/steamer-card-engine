from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import tomllib
from typing import Any

from .fixtures import repo_root


@dataclass(frozen=True)
class StrategyCardSource:
    candidate_id: str
    family_id: str
    card_relpath: Path
    deck_relpath: Path


CARD_SOURCES = (
    StrategyCardSource(
        candidate_id="tw_vcp_dryup_reclaim_bounded",
        family_id="tw_vcp_dryup_reclaim",
        card_relpath=Path("examples/cards/tw_vcp_dryup_reclaim_bounded.toml"),
        deck_relpath=Path("examples/decks/tw_cash_vcp_dryup_reclaim_bounded.toml"),
    ),
    StrategyCardSource(
        candidate_id="tw_orb_reclaim_long_5m",
        family_id="tw_orb_reclaim_long",
        card_relpath=Path("examples/cards/tw_orb_reclaim_long_5m.toml"),
        deck_relpath=Path("examples/decks/tw_cash_orb_reclaim_long_5m.toml"),
    ),
    StrategyCardSource(
        candidate_id="tw_gap_reclaim_long_3m",
        family_id="tw_gap_reclaim_long",
        card_relpath=Path("examples/cards/tw_gap_reclaim_long_3m.toml"),
        deck_relpath=Path("examples/decks/tw_cash_gap_reclaim_long_3m.toml"),
    ),
)

PROPOSAL_PLAN_RELATIVE_PATH = Path(
    ".state/steamer/card-engine-morning-paired-lane/proposed_distinct_families_20260409.json"
)
ACTIVE_PLAN_RELATIVE_PATH = Path(
    ".state/steamer/card-engine-morning-paired-lane/active_deck_plan.json"
)
MORNING_PACKET_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/"
    "2026-04-09_distinct_families_morning_packet.md"
)
BOUNDED_BACKTEST_MD_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/"
    "2026-04-09_distinct_families_bounded_backtest.md"
)
BOUNDED_BACKTEST_JSON_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/"
    "2026-04-09_distinct_families_bounded_backtest.json"
)
SYNTHETIC_VERIFIER_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/verifiers/"
    "2026-04-09_distinct_families_synthetic_verifier.md"
)
SYNTHETIC_VERIFIER_JSON_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/verifiers/"
    "2026-04-09_distinct_families_synthetic_verifier.json"
)
GAP_PARAM_ESTIMATE_MD_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/"
    "2026-04-09_tw_gap_reclaim_long_param_estimate.md"
)
GAP_PARAM_ESTIMATE_JSON_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/"
    "2026-04-09_tw_gap_reclaim_long_param_estimate.json"
)
VCP_BLOCKER_SURGERY_MD_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/"
    "2026-04-09_tw_vcp_dryup_reclaim_blocker_surgery.md"
)
VCP_BLOCKER_SURGERY_JSON_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/"
    "2026-04-09_tw_vcp_dryup_reclaim_blocker_surgery.json"
)

SECTION_RE = re.compile(r"^## (?P<title>[^\n]+)\n(?P<body>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
FAMILY_SECTION_RE = re.compile(
    r"^### \d+\) `(?P<family>[^`]+)`\n(?P<body>.*?)(?=^### \d+\)|^## |\Z)",
    re.MULTILINE | re.DOTALL,
)


class StrategyPowerhouseDataError(Exception):
    """Raised when the local strategy-powerhouse source surface cannot be built."""


def _workspace_root(repo: Path) -> Path:
    return repo.parent


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json(path)


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def _safe_relpath(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _resolve_workspace_path(workspace_root: Path, raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return workspace_root / path


def _extract_sections(markdown: str) -> dict[str, str]:
    return {match.group("title").strip(): match.group("body").strip() for match in SECTION_RE.finditer(markdown)}


def _extract_family_sections(markdown: str) -> dict[str, str]:
    return {match.group("family").strip(): match.group("body").strip() for match in FAMILY_SECTION_RE.finditer(markdown)}


def _extract_family_statuses(markdown: str) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for match in FAMILY_SECTION_RE.finditer(markdown):
        family_id = match.group("family").strip()
        body = match.group("body")
        status_match = re.search(r"- status: `([^`]+)`", body)
        if status_match is not None:
            statuses[family_id] = status_match.group(1).strip().upper()
    return statuses


def _extract_attachable_candidates(readiness_section: str) -> set[str]:
    attachable_match = re.search(
        r"Attachable now.*?:\s*(?P<body>.*?)(?=\n- \*\*If choosing only one morning priority family now:|\Z)",
        readiness_section,
        re.DOTALL,
    )
    if attachable_match is None:
        return set()
    return set(re.findall(r"`([^`]+)`", attachable_match.group("body")))


def _extract_hold_line(readiness_section: str, candidate_id: str) -> str | None:
    match = re.search(
        rf"`{re.escape(candidate_id)}`\s+stays\s+HOLD\s+until\s+([^\n]+)",
        readiness_section,
    )
    if match is None:
        return None
    return match.group(1).strip().rstrip(".")


def _extract_priority_candidate(readiness_section: str) -> str | None:
    match = re.search(r"use `([^`]+)` first", readiness_section)
    if match is None:
        return None
    return match.group(1).strip()


def _extract_positive_case_families(markdown: str) -> set[str]:
    sections = _extract_sections(markdown)
    body = sections.get("Synthetic verifier status", "") or sections.get("Implemented positive-case slices", "")
    return set(re.findall(r"`(tw_[a-z0-9_]+)`\s*→\s*synthetic", body)) | set(
        re.findall(r"^- (tw_[a-z0-9_]+)\s*$", body, flags=re.MULTILINE)
    )


def _extract_packet_recorded_at(markdown: str) -> str | None:
    match = re.search(r"^- recorded:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", markdown, re.MULTILINE)
    if match is None:
        return None
    return match.group(1)


def _extract_contract_only_families(markdown: str) -> set[str]:
    sections = _extract_sections(markdown)
    body = sections.get("Synthetic verifier status", "")
    contract_only_match = re.search(
        r"contract-only slice remains:\s*(?P<body>.*)",
        body,
        re.DOTALL,
    )
    if contract_only_match is None:
        return set()
    return set(re.findall(r"`(tw_[a-z0-9_]+)`", contract_only_match.group("body")))


def _parameter_summary(parameters: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"label": key, "value": value}
        for key, value in parameters.items()
        if key != "candidate_id"
    ]


def _normalize_status(raw_status: str | None, *, attachable: bool, proof_state: str) -> str:
    normalized = (raw_status or "").strip().lower()
    if "hold" in normalized:
        return "hold"
    if attachable or "attachable" in normalized or "ready" in normalized:
        if proof_state == "synthetic-proven":
            return "synthetic-proven"
        return "ready"
    if proof_state == "synthetic-proven":
        return "synthetic-proven"
    return normalized or "unknown"


def _proposal_state_label(candidate_id: str, active_target_ids: set[str], proposed_target_ids: set[str]) -> str:
    if candidate_id in active_target_ids:
        return "active"
    if candidate_id in proposed_target_ids:
        return "proposed"
    return "unlisted"


def _normalize_timestamp(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return f"{value}T00:00:00+08:00"
    return value


def _timestamp_sort_key(raw_value: str | None) -> tuple[int, float, str]:
    value = _normalize_timestamp(raw_value)
    if value is None:
        return (0, float("-inf"), "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (1, parsed.timestamp(), value)
    except ValueError:
        return (0, float("-inf"), value)


def _format_bps(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):+.1f} bps"


def _summarize_plan_targets(plan: dict[str, Any] | None, *, workspace_root: Path) -> list[dict[str, Any]]:
    if not plan:
        return []

    targets: list[dict[str, Any]] = []
    for item in plan.get("targets", []) or []:
        variant_id = str(item.get("variant_id") or "unknown")
        raw_deck_path = item.get("deck_path")
        resolved_deck_path = (
            _resolve_workspace_path(workspace_root, raw_deck_path)
            if raw_deck_path
            else None
        )
        deck_manifest_present = bool(resolved_deck_path and resolved_deck_path.exists())
        deck_id = None
        if deck_manifest_present and resolved_deck_path is not None:
            deck_payload = _load_toml(resolved_deck_path)
            raw_deck_id = deck_payload.get("deck_id")
            if raw_deck_id is not None:
                deck_id = str(raw_deck_id)

        targets.append(
            {
                "variant_id": variant_id,
                "deck_id": deck_id,
                "deck_path": (
                    _safe_relpath(resolved_deck_path, workspace_root)
                    if resolved_deck_path is not None
                    else None
                ),
                "deck_manifest_present": deck_manifest_present,
            }
        )

    return targets


def _target_display_labels(targets: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for item in targets:
        deck_id = item.get("deck_id")
        variant_id = item.get("variant_id")
        if deck_id and variant_id:
            labels.append(f"{deck_id} ({variant_id})")
        elif deck_id:
            labels.append(str(deck_id))
        elif variant_id:
            labels.append(str(variant_id))
    return labels


def _divergence_state(
    *,
    active_family: str | None,
    proposal_family: str | None,
    active_target_ids: set[str],
    proposed_target_ids: set[str],
    active_truth_state: str,
) -> dict[str, Any]:
    if active_truth_state != "present":
        note = "Active plan truth is missing or empty, so proposed-vs-active divergence cannot be fully confirmed."
        return {
            "state": "unknown",
            "family_differs": proposal_family is not None,
            "target_differs": bool(proposed_target_ids),
            "note": note,
        }

    family_differs = bool((active_family or "").strip() != (proposal_family or "").strip())
    target_differs = active_target_ids != proposed_target_ids
    if family_differs or target_differs:
        note = (
            "Proposed family/targets diverge from the current active paired-lane plan; "
            "strategy-powerhouse remains support only and has not changed active execution."
        )
        state = "diverged"
    else:
        note = "Proposed family/targets match the active plan truth."
        state = "aligned"

    return {
        "state": state,
        "family_differs": family_differs,
        "target_differs": target_differs,
        "note": note,
    }


def _baton_readiness_state(active_truth_state: str) -> str:
    if active_truth_state == "present":
        return "proposed-read-only"
    if active_truth_state == "empty":
        return "active-truth-empty"
    return "active-truth-missing"


def _baton_readiness_summary(
    *,
    active_family: str | None,
    active_truth_state: str,
    cards: list[dict[str, Any]],
) -> str:
    if active_truth_state != "present":
        return (
            "Active plan truth is missing or empty. Proposed families remain read-only proposal truth and do not "
            "replace the active paired lane."
        )

    proposal_parts = [f"{card['candidate_id']}: {card['handoff_readiness']}" for card in cards]
    return (
        f"Active paired lane remains `{active_family or 'unknown'}` in steamer-card-engine. Proposal baton stays read-only: "
        + "; ".join(proposal_parts)
        + "."
    )


def _latest_packet_sort_key(item: dict[str, Any]) -> tuple[int, tuple[int, float, str]]:
    kind_priority = {
        "gate-analysis": 4,
        "parameter-estimate": 3,
        "packet": 2,
        "backtest": 1,
    }
    return (kind_priority.get(str(item.get("kind")), 0), _timestamp_sort_key(item.get("timestamp")))


def _build_history_entry(
    *,
    event_id: str,
    timestamp: str | None,
    kind: str,
    title: str,
    summary: str,
    path: str,
    source_kind: str,
    status: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "timestamp": _normalize_timestamp(timestamp),
        "kind": kind,
        "title": title,
        "summary": summary,
        "status": status,
        "path": path,
        "source_kind": source_kind,
    }


def _backtest_history_entry(
    *,
    family_id: str,
    family_report: dict[str, Any],
    bounded_backtest: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    signals = int(family_report.get("selected_signals_total", 0) or 0)
    days = int(family_report.get("selected_signal_days", 0) or 0)
    summary = (
        f"{signals} signals / {days} days / avg {_format_bps(family_report.get('selected_avg_return_bps'))} "
        f"/ median {_format_bps(family_report.get('selected_median_return_bps'))}."
    )
    status = "hold" if signals == 0 else "recorded-signal"
    return _build_history_entry(
        event_id=f"{family_id}-bounded-backtest",
        timestamp=str(bounded_backtest.get("generated_at_utc") or ""),
        kind="backtest",
        title="Bounded backtest packet",
        summary=summary,
        status=status,
        path=_safe_relpath(workspace_root / BOUNDED_BACKTEST_MD_RELATIVE_PATH, workspace_root),
        source_kind="backtest",
    )


def _verifier_history_entry(
    *,
    family_id: str,
    verifier_payload: dict[str, Any],
    workspace_root: Path,
    positive_case_families: set[str],
    contract_only_families: set[str],
) -> dict[str, Any]:
    result = dict(verifier_payload.get("positive_case_results", {}).get(family_id, {}))
    trigger_result = dict(result.get("trigger_result", {}))
    summary_parts: list[str] = []
    symbol = trigger_result.get("symbol")
    if symbol:
        summary_parts.append(f"synthetic trigger on {symbol}")
    if trigger_result.get("return_bps") is not None:
        summary_parts.append(f"return {_format_bps(trigger_result.get('return_bps'))}")

    status = "missing"
    if family_id in contract_only_families:
        status = "contract-only"
        summary_parts.append("latest handoff still carries this family as contract-only")
    elif family_id in positive_case_families:
        status = "positive-case"
        summary_parts.append("morning packet carries this verifier as a positive-case bridge")

    if not summary_parts:
        summary_parts.append("Verifier receipt exists for this family.")

    if not result:
        summary_parts.append("verifier file does not contain a dedicated result for this family")

    return _build_history_entry(
        event_id=f"{family_id}-synthetic-verifier",
        timestamp=str(verifier_payload.get("generated_at_utc") or ""),
        kind="verifier",
        title="Synthetic verifier receipt",
        summary="; ".join(summary_parts),
        status=status,
        path=_safe_relpath(workspace_root / SYNTHETIC_VERIFIER_RELATIVE_PATH, workspace_root),
        source_kind="verifier",
    )


def _vcp_blocker_history_entry(*, blocker_payload: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    latest10d = dict(blocker_payload.get("latest10d", {}))
    rows_total = int(latest10d.get("rows_total", 0) or 0)
    summary = dict(blocker_payload.get("summary", {}))
    main_blocker = summary.get("main_blocker") or "recorded VCP context not materialized"
    return _build_history_entry(
        event_id="tw_vcp_dryup_reclaim-blocker-surgery",
        timestamp=str(blocker_payload.get("generated_at") or ""),
        kind="gate-analysis",
        title="Blocker surgery packet",
        summary=f"Verdict HOLD after {rows_total:,} latest10d rows: {main_blocker}.",
        status=str(blocker_payload.get("verdict") or "hold").lower(),
        path=_safe_relpath(workspace_root / VCP_BLOCKER_SURGERY_MD_RELATIVE_PATH, workspace_root),
        source_kind="gate-analysis",
    )


def _gap_param_history_entry(*, gap_payload: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    selected = dict(gap_payload.get("selected", {}))
    summary = (
        f"Selected {selected.get('signals_total', 0)} signals / {selected.get('signal_days', 0)} days "
        f"with avg {_format_bps(selected.get('avg_return_bps'))} and median {_format_bps(selected.get('median_return_bps'))}."
    )
    return _build_history_entry(
        event_id="tw_gap_reclaim_long-parameter-estimate",
        timestamp=str(gap_payload.get("generated_at_utc") or ""),
        kind="parameter-estimate",
        title="Targeted parameter estimate",
        summary=summary,
        status="selected",
        path=_safe_relpath(workspace_root / GAP_PARAM_ESTIMATE_MD_RELATIVE_PATH, workspace_root),
        source_kind="backtest",
    )


def _packet_history_entry(
    *,
    family_id: str,
    packet_body: str,
    packet_status: str | None,
    packet_path: Path,
    workspace_root: Path,
    packet_recorded_at: str | None,
    handoff_readiness: str,
) -> dict[str, Any]:
    why_match = re.search(r"- why distinct: ([^\n]+)", packet_body)
    why_text = why_match.group(1).strip() if why_match else "Family carried in the distinct-family morning packet."
    status = "hold" if (packet_status or "").lower().startswith("hold") else "packetized"
    summary = f"{why_text} Handoff: {handoff_readiness}."
    return _build_history_entry(
        event_id=f"{family_id}-morning-packet",
        timestamp=packet_recorded_at,
        kind="packet",
        title="Morning packet handoff",
        summary=summary,
        status=status,
        path=_safe_relpath(packet_path, workspace_root),
        source_kind="packet",
    )


def _proposal_history_entry(
    *,
    family_id: str,
    candidate_id: str,
    proposal_plan: dict[str, Any],
    proposal_plan_path: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    return _build_history_entry(
        event_id=f"{family_id}-proposal-plan",
        timestamp=str(proposal_plan.get("prepared_at") or ""),
        kind="plan",
        title="Distinct-family proposal plan",
        summary=(
            f"Candidate `{candidate_id}` remains proposal truth only; active deck plan was not silently replaced."
        ),
        status="proposal-only",
        path=_safe_relpath(proposal_plan_path, workspace_root),
        source_kind="control",
    )


def build_strategy_powerhouse_view(root: Path | None = None) -> dict[str, Any]:
    repo = root or repo_root()
    workspace_root = _workspace_root(repo)

    proposal_plan_path = workspace_root / PROPOSAL_PLAN_RELATIVE_PATH
    active_plan_path = workspace_root / ACTIVE_PLAN_RELATIVE_PATH
    source_packet_path = workspace_root / MORNING_PACKET_RELATIVE_PATH
    verifier_path = workspace_root / SYNTHETIC_VERIFIER_RELATIVE_PATH
    verifier_json_path = workspace_root / SYNTHETIC_VERIFIER_JSON_RELATIVE_PATH
    bounded_backtest_json_path = workspace_root / BOUNDED_BACKTEST_JSON_RELATIVE_PATH
    bounded_backtest_md_path = workspace_root / BOUNDED_BACKTEST_MD_RELATIVE_PATH
    gap_param_estimate_json_path = workspace_root / GAP_PARAM_ESTIMATE_JSON_RELATIVE_PATH
    vcp_blocker_json_path = workspace_root / VCP_BLOCKER_SURGERY_JSON_RELATIVE_PATH

    proposal_plan = _load_json(proposal_plan_path)
    active_plan = _load_optional_json(active_plan_path)
    morning_packet = _load_text(source_packet_path)
    bounded_backtest = _load_json(bounded_backtest_json_path)
    verifier_payload = _load_json(verifier_json_path)

    packet_sections = _extract_sections(morning_packet)
    family_packet_sections = _extract_family_sections(morning_packet)
    packet_recorded_at = _extract_packet_recorded_at(morning_packet)
    readiness_section = packet_sections.get("Morning/live-sim readiness", "")
    family_statuses = _extract_family_statuses(morning_packet)
    attachable_candidates = _extract_attachable_candidates(readiness_section)
    positive_case_families = _extract_positive_case_families(morning_packet)
    contract_only_families = _extract_contract_only_families(morning_packet)
    priority_candidate = _extract_priority_candidate(readiness_section)

    proposed_targets = proposal_plan.get("targets", [])
    active_targets = active_plan.get("targets", []) if active_plan else []
    proposed_target_ids = {str(item.get("variant_id")) for item in proposed_targets}
    active_target_ids = {str(item.get("variant_id")) for item in active_targets}
    proposed_deck_paths = {
        str(item.get("variant_id")): str(item.get("deck_path"))
        for item in proposed_targets
        if item.get("variant_id") and item.get("deck_path")
    }

    vcp_blocker_payload = _load_json(vcp_blocker_json_path) if vcp_blocker_json_path.exists() else None
    gap_param_estimate_payload = _load_json(gap_param_estimate_json_path) if gap_param_estimate_json_path.exists() else None

    cards: list[dict[str, Any]] = []
    used_source_map: dict[str, dict[str, str]] = {
        _safe_relpath(proposal_plan_path, workspace_root): {
            "label": "proposal plan",
            "kind": "proposal",
            "path": _safe_relpath(proposal_plan_path, workspace_root),
        },
        _safe_relpath(active_plan_path, workspace_root): {
            "label": "active plan",
            "kind": "control",
            "path": _safe_relpath(active_plan_path, workspace_root),
        },
        _safe_relpath(source_packet_path, workspace_root): {
            "label": "morning packet",
            "kind": "packet",
            "path": _safe_relpath(source_packet_path, workspace_root),
        },
        _safe_relpath(verifier_path, workspace_root): {
            "label": "synthetic verifier",
            "kind": "verifier",
            "path": _safe_relpath(verifier_path, workspace_root),
        },
        _safe_relpath(bounded_backtest_md_path, workspace_root): {
            "label": "bounded backtest",
            "kind": "backtest",
            "path": _safe_relpath(bounded_backtest_md_path, workspace_root),
        },
    }

    for source in CARD_SOURCES:
        card_path = repo / source.card_relpath
        deck_path = _resolve_workspace_path(
            workspace_root,
            proposed_deck_paths.get(source.candidate_id, repo / source.deck_relpath),
        )
        if not card_path.exists():
            raise StrategyPowerhouseDataError(f"missing strategy card manifest: {card_path}")
        if not deck_path.exists():
            raise StrategyPowerhouseDataError(f"missing strategy deck manifest: {deck_path}")

        card = _load_toml(card_path)
        deck = _load_toml(deck_path)
        parameters = dict(card.get("parameters", {}))
        metadata = dict(card.get("metadata", {}))
        family_report = dict(bounded_backtest.get("family_reports", {}).get(source.family_id, {}))
        if not family_report:
            raise StrategyPowerhouseDataError(f"missing bounded backtest family report for {source.family_id}")

        hold_gate = _extract_hold_line(readiness_section, source.candidate_id)
        packet_status = family_statuses.get(source.family_id)
        proof_state = "contract-only"
        proof_note = "Synthetic verifier has not yet emitted a dedicated receipt for this family."
        if source.family_id in positive_case_families:
            proof_state = "synthetic-proven"
            proof_note = "Synthetic verifier contains a positive-case trigger receipt for this family."
        elif source.family_id in contract_only_families:
            proof_state = "ready"
            proof_note = "This family is carried by recorded-data evidence; synthetic verifier remains contract-only."

        status = _normalize_status(
            packet_status,
            attachable=source.candidate_id in attachable_candidates,
            proof_state=proof_state,
        )
        next_gate = None
        if hold_gate is not None:
            next_gate = "needs-real-trigger"
        elif source.candidate_id in attachable_candidates:
            next_gate = "observation-ready"

        handoff_readiness = "proposal only"
        if source.candidate_id == priority_candidate:
            handoff_readiness = "priority-1 observation proposal"
        elif source.candidate_id in attachable_candidates:
            handoff_readiness = "secondary observation proposal"
        if hold_gate is not None:
            handoff_readiness = "HOLD until a recorded trigger exists beyond synthetic proof"

        links = [
            {
                "label": "card manifest",
                "kind": "card",
                "path": _safe_relpath(card_path, repo),
            },
            {
                "label": "deck manifest",
                "kind": "deck",
                "path": _safe_relpath(deck_path, workspace_root),
            },
            {
                "label": "morning packet",
                "kind": "packet",
                "path": _safe_relpath(source_packet_path, workspace_root),
            },
            {
                "label": "synthetic verifier",
                "kind": "verifier",
                "path": _safe_relpath(verifier_path, workspace_root),
            },
            {
                "label": "proposal plan",
                "kind": "proposal",
                "path": _safe_relpath(proposal_plan_path, workspace_root),
            },
            {
                "label": "bounded backtest",
                "kind": "backtest",
                "path": _safe_relpath(bounded_backtest_md_path, workspace_root),
            },
        ]
        backtest_packet = metadata.get("backtest_packet")
        if isinstance(backtest_packet, str) and backtest_packet:
            links.append(
                {
                    "label": "backtest packet",
                    "kind": "backtest",
                    "path": _safe_relpath(_resolve_workspace_path(workspace_root, backtest_packet), workspace_root),
                }
            )

        family_timeline = [
            _proposal_history_entry(
                family_id=source.family_id,
                candidate_id=source.candidate_id,
                proposal_plan=proposal_plan,
                proposal_plan_path=proposal_plan_path,
                workspace_root=workspace_root,
            ),
            _packet_history_entry(
                family_id=source.family_id,
                packet_body=family_packet_sections.get(source.family_id, ""),
                packet_status=packet_status,
                packet_path=source_packet_path,
                workspace_root=workspace_root,
                packet_recorded_at=packet_recorded_at,
                handoff_readiness=handoff_readiness,
            ),
            _backtest_history_entry(
                family_id=source.family_id,
                family_report=family_report,
                bounded_backtest=bounded_backtest,
                workspace_root=workspace_root,
            ),
            _verifier_history_entry(
                family_id=source.family_id,
                verifier_payload=verifier_payload,
                workspace_root=workspace_root,
                positive_case_families=positive_case_families,
                contract_only_families=contract_only_families,
            ),
        ]

        if source.family_id == "tw_vcp_dryup_reclaim" and vcp_blocker_payload is not None:
            family_timeline.append(
                _vcp_blocker_history_entry(blocker_payload=vcp_blocker_payload, workspace_root=workspace_root)
            )
            blocker_path = _safe_relpath(workspace_root / VCP_BLOCKER_SURGERY_MD_RELATIVE_PATH, workspace_root)
            links.append({"label": "blocker surgery", "kind": "gate-analysis", "path": blocker_path})
            used_source_map[blocker_path] = {
                "label": "blocker surgery",
                "kind": "gate-analysis",
                "path": blocker_path,
            }
        if source.family_id == "tw_gap_reclaim_long" and gap_param_estimate_payload is not None:
            family_timeline.append(
                _gap_param_history_entry(gap_payload=gap_param_estimate_payload, workspace_root=workspace_root)
            )
            gap_path = _safe_relpath(workspace_root / GAP_PARAM_ESTIMATE_MD_RELATIVE_PATH, workspace_root)
            links.append({"label": "parameter estimate", "kind": "backtest", "path": gap_path})
            used_source_map[gap_path] = {
                "label": "parameter estimate",
                "kind": "backtest",
                "path": gap_path,
            }

        family_timeline.sort(
            key=lambda item: (_timestamp_sort_key(item.get("timestamp")), item.get("event_id", "")),
            reverse=True,
        )
        packet_candidates = [
            item for item in family_timeline if item["kind"] in {"gate-analysis", "parameter-estimate", "packet", "backtest"}
        ]
        latest_packet = max(packet_candidates, key=_latest_packet_sort_key) if packet_candidates else None
        verifier_history = [item for item in family_timeline if item["kind"] == "verifier"]

        for link in links:
            used_source_map.setdefault(link["path"], link)

        cards.append(
            {
                "candidate_id": source.candidate_id,
                "family_id": source.family_id,
                "display_name": str(card.get("name", source.candidate_id)),
                "card_id": str(card.get("card_id", "unknown")),
                "deck_id": str(deck.get("deck_id", "unknown")),
                "status": status.lower(),
                "validation_status": proof_state,
                "current_gate": next_gate,
                "next_gate": next_gate,
                "handoff_state": handoff_readiness,
                "handoff_readiness": handoff_readiness,
                "proposal_state": _proposal_state_label(
                    source.candidate_id,
                    active_target_ids=active_target_ids,
                    proposed_target_ids=proposed_target_ids,
                ),
                "proposal_priority": "first" if source.candidate_id == priority_candidate else "secondary",
                "notes": str(metadata.get("notes", "")),
                "proof_note": proof_note,
                "selected_parameter_summary": _parameter_summary(parameters),
                "symbol_pool": list(card.get("symbol_pool", [])),
                "feature_requirements": list(card.get("feature_requirements", [])),
                "latest_packet": latest_packet,
                "verifier_history": verifier_history,
                "family_timeline": family_timeline,
                "related_links": links,
            }
        )

    cards.sort(
        key=lambda item: (
            item["proposal_priority"] != "first",
            item["status"] == "hold",
            item["candidate_id"],
        )
    )

    ready_count = sum(1 for card in cards if card["status"] == "ready")
    hold_count = sum(1 for card in cards if card["status"] == "hold")
    synthetic_count = sum(1 for card in cards if card["validation_status"] == "synthetic-proven")
    history_event_count = sum(len(card["family_timeline"]) for card in cards)
    verifier_receipt_count = sum(len(card["verifier_history"]) for card in cards)
    active_plan_targets = _summarize_plan_targets(active_plan, workspace_root=workspace_root)
    proposed_plan_targets = _summarize_plan_targets(proposal_plan, workspace_root=workspace_root)

    active_truth_state = "present"
    if active_plan is None:
        active_truth_state = "missing"
    elif not active_plan_targets:
        active_truth_state = "empty"

    divergence = _divergence_state(
        active_family=str(active_plan.get("family")) if active_plan and active_plan.get("family") else None,
        proposal_family=str(proposal_plan.get("family")) if proposal_plan.get("family") else None,
        active_target_ids=active_target_ids,
        proposed_target_ids=proposed_target_ids,
        active_truth_state=active_truth_state,
    )
    readiness_summary = _baton_readiness_summary(
        active_family=str(active_plan.get("family")) if active_plan and active_plan.get("family") else None,
        active_truth_state=active_truth_state,
        cards=cards,
    )

    return {
        "updated_at": proposal_plan.get("prepared_at"),
        "topology_changed": False,
        "boundary": {
            "note": (
                "This tab is a read-only local artifact history browser. It exposes research/control truth from local files, "
                "not live execution authority, and it does not mutate governance state."
            ),
            "execution_authority": "none",
            "governance_mutation": False,
            "primary_execution_surface": "steamer-card-engine",
            "strategy_powerhouse_role": "research / packaging / control-plane support only",
        },
        "baton_line": {
            "today": str(proposal_plan.get("prepared_at") or "")[:10] or None,
            "read_only_note": (
                "Read-only support surface only. strategy-powerhouse does not own execution; "
                "steamer-card-engine remains the execution surface."
            ),
            "active": {
                "truth_state": active_truth_state,
                "family": active_plan.get("family") if active_plan else None,
                "prepared_at": active_plan.get("prepared_at") if active_plan else None,
                "source_packet": (
                    _safe_relpath(
                        _resolve_workspace_path(workspace_root, active_plan.get("source_packet", "")),
                        workspace_root,
                    )
                    if active_plan and active_plan.get("source_packet")
                    else None
                ),
                "targets": active_plan_targets,
                "target_labels": _target_display_labels(active_plan_targets),
                "attachment_summary": (
                    f"{len(active_plan_targets)} active deck target(s) attached to the current paired-lane plan."
                    if active_truth_state == "present"
                    else (
                        "Active plan file exists but carries no attached deck targets."
                        if active_truth_state == "empty"
                        else "No active plan file was found for the paired lane."
                    )
                ),
            },
            "proposal": {
                "family": proposal_plan.get("family"),
                "prepared_at": proposal_plan.get("prepared_at"),
                "source_packet": _safe_relpath(source_packet_path, workspace_root),
                "targets": proposed_plan_targets,
                "target_labels": _target_display_labels(proposed_plan_targets),
            },
            "handoff_readiness": {
                "state": _baton_readiness_state(active_truth_state),
                "summary": readiness_summary,
            },
            "divergence": divergence,
        },
        "proposal": {
            "proposal_family": proposal_plan.get("family"),
            "proposal_prepared_at": proposal_plan.get("prepared_at"),
            "proposal_state": "proposed-not-active",
            "source_packet": _safe_relpath(source_packet_path, workspace_root),
            "truthful_boundary": proposal_plan.get("truthful_boundary"),
            "active_family": active_plan.get("family") if active_plan else None,
            "active_plan_source": _safe_relpath(
                _resolve_workspace_path(workspace_root, active_plan.get("source_packet", "")),
                workspace_root,
            )
            if active_plan and active_plan.get("source_packet")
            else None,
        },
        "metrics": {
            "card_count": len(cards),
            "ready_count": ready_count,
            "hold_count": hold_count,
            "synthetic_proven_count": synthetic_count,
            "history_event_count": history_event_count,
            "verifier_receipt_count": verifier_receipt_count,
        },
        "sources": list(used_source_map.values()),
        "cards": cards,
    }
