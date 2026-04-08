from __future__ import annotations

from dataclasses import dataclass
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
SYNTHETIC_VERIFIER_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/verifiers/"
    "2026-04-09_distinct_families_synthetic_verifier.md"
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


def build_strategy_powerhouse_view(root: Path | None = None) -> dict[str, Any]:
    repo = root or repo_root()
    workspace_root = _workspace_root(repo)

    proposal_plan_path = workspace_root / PROPOSAL_PLAN_RELATIVE_PATH
    active_plan_path = workspace_root / ACTIVE_PLAN_RELATIVE_PATH
    verifier_path = workspace_root / SYNTHETIC_VERIFIER_RELATIVE_PATH

    proposal_plan = _load_json(proposal_plan_path)
    active_plan = _load_json(active_plan_path)

    source_packet_raw = str(proposal_plan.get("source_packet", ""))
    if not source_packet_raw:
        raise StrategyPowerhouseDataError("proposal plan is missing source_packet")
    source_packet_path = _resolve_workspace_path(workspace_root, source_packet_raw)

    morning_packet = _load_text(source_packet_path)

    packet_sections = _extract_sections(morning_packet)
    readiness_section = packet_sections.get("Morning/live-sim readiness", "")
    family_statuses = _extract_family_statuses(morning_packet)
    attachable_candidates = _extract_attachable_candidates(readiness_section)
    positive_case_families = _extract_positive_case_families(morning_packet)
    contract_only_families = _extract_contract_only_families(morning_packet)
    priority_candidate = _extract_priority_candidate(readiness_section)

    proposed_targets = proposal_plan.get("targets", [])
    active_targets = active_plan.get("targets", [])
    proposed_target_ids = {str(item.get("variant_id")) for item in proposed_targets}
    active_target_ids = {str(item.get("variant_id")) for item in active_targets}
    proposed_deck_paths = {
        str(item.get("variant_id")): str(item.get("deck_path"))
        for item in proposed_targets
        if item.get("variant_id") and item.get("deck_path")
    }

    cards: list[dict[str, Any]] = []
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

        cards.append(
            {
                "candidate_id": source.candidate_id,
                "family_id": source.family_id,
                "display_name": str(card.get("name", source.candidate_id)),
                "card_id": str(card.get("card_id", "unknown")),
                "deck_id": str(deck.get("deck_id", "unknown")),
                "status": status.lower(),
                "validation_status": proof_state,
                "next_gate": next_gate,
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

    return {
        "updated_at": proposal_plan.get("prepared_at"),
        "topology_changed": False,
        "boundary": {
            "note": (
                "This tab is a read-only local artifact summary. It exposes research/control truth from local files, "
                "not live execution authority, and it does not mutate governance state."
            ),
            "execution_authority": "none",
            "governance_mutation": False,
            "primary_execution_surface": "steamer-card-engine",
            "strategy_powerhouse_role": "research / packaging / control-plane support only",
        },
        "proposal": {
            "proposal_family": proposal_plan.get("family"),
            "proposal_prepared_at": proposal_plan.get("prepared_at"),
            "proposal_state": "proposed-not-active",
            "source_packet": _safe_relpath(source_packet_path, workspace_root),
            "truthful_boundary": proposal_plan.get("truthful_boundary"),
            "active_family": active_plan.get("family"),
            "active_plan_source": _safe_relpath(
                _resolve_workspace_path(workspace_root, active_plan.get("source_packet", "")),
                workspace_root,
            )
            if active_plan.get("source_packet")
            else None,
        },
        "metrics": {
            "card_count": len(cards),
            "ready_count": ready_count,
            "hold_count": hold_count,
            "synthetic_proven_count": synthetic_count,
        },
        "sources": [
            {
                "label": "proposal plan",
                "kind": "proposal",
                "path": _safe_relpath(proposal_plan_path, workspace_root),
            },
            {
                "label": "active plan",
                "kind": "control",
                "path": _safe_relpath(active_plan_path, workspace_root),
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
        ],
        "cards": cards,
    }
