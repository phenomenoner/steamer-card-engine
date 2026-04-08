from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

STATE_RELATIVE_PATH = Path(".state/steamer/card-engine-morning-paired-lane")
ACTIVE_PLAN_RELATIVE_PATH = STATE_RELATIVE_PATH / "active_deck_plan.json"
BACKTESTS_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests"
)
VERIFIERS_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/verifiers"
)
CAMPAIGNS_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/lanes/autonomous-slow-cook/campaigns"
)
BACKTICK_FIELD_RE = r"^- {label}:\s*`([^`]+)`"
RECORDED_AT_RE = re.compile(r"^- recorded:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.MULTILINE)
PROPOSAL_PLAN_RE = re.compile(r"proposed_distinct_families_(?P<day>\d{8})\.json$")


@dataclass(frozen=True)
class FamilySourcePattern:
    suffix: str
    kind: str
    label: str
    source_kind: str


@dataclass(frozen=True)
class IndexedArtifact:
    family_id: str | None
    kind: str
    label: str
    source_kind: str
    md_path: Path | None = None
    json_path: Path | None = None
    timestamp: str | None = None

    @property
    def primary_path(self) -> Path | None:
        return self.md_path or self.json_path


@dataclass(frozen=True)
class IndexedBatonReceipt:
    campaign_id: str
    changed_at: str | None
    from_family: str | None
    to_family: str | None
    path: Path
    summary: str | None
    forcing_evidence: str | None
    prior_receipt: str | None


@dataclass(frozen=True)
class StrategyHistorySourceIndex:
    proposal_day: str
    proposal_plan_path: Path
    active_plan_path: Path
    global_sources: dict[str, IndexedArtifact]
    family_sources: dict[str, tuple[IndexedArtifact, ...]]
    baton_receipts: dict[str, tuple[IndexedBatonReceipt, ...]]

    def global_source(self, kind: str) -> IndexedArtifact | None:
        return self.global_sources.get(kind)

    def sources_for_family(self, family_id: str) -> tuple[IndexedArtifact, ...]:
        return self.family_sources.get(family_id, ())

    def source_for_family_kind(self, family_id: str, kind: str) -> IndexedArtifact | None:
        for artifact in self.sources_for_family(family_id):
            if artifact.kind == kind:
                return artifact
        return None

    def latest_baton_change(self, family_id: str | None) -> IndexedBatonReceipt | None:
        if not family_id:
            return None
        receipts = self.baton_receipts.get(family_id, ())
        return receipts[0] if receipts else None


FAMILY_SOURCE_PATTERNS: tuple[FamilySourcePattern, ...] = (
    FamilySourcePattern(
        suffix="_param_estimate",
        kind="parameter-estimate",
        label="parameter estimate",
        source_kind="backtest",
    ),
    FamilySourcePattern(
        suffix="_blocker_surgery",
        kind="gate-analysis",
        label="blocker surgery",
        source_kind="gate-analysis",
    ),
)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json(path)


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_backtick_field(markdown: str, label: str) -> str | None:
    match = re.search(BACKTICK_FIELD_RE.format(label=re.escape(label)), markdown, re.MULTILINE)
    if match is None:
        return None
    return match.group(1).strip()


def _extract_packet_recorded_at(markdown: str) -> str | None:
    match = RECORDED_AT_RE.search(markdown)
    if match is None:
        return None
    return match.group(1)


def _timestamp_sort_key(raw_value: str | None) -> tuple[int, str]:
    value = str(raw_value or "").strip()
    if not value:
        return (0, "")
    return (1, value)


def _latest_matching_file(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"no files matched {pattern} under {root}")
    return matches[-1]


def _require_matching_file(root: Path, pattern: str) -> Path:
    return _latest_matching_file(root, pattern)


def _proposal_day_components(proposal_plan_path: Path, proposal_payload: dict[str, Any]) -> tuple[str, str]:
    match = PROPOSAL_PLAN_RE.search(proposal_plan_path.name)
    compact = match.group("day") if match else ""
    if not compact:
        prepared_at = str(proposal_payload.get("prepared_at") or "")
        compact = prepared_at[:10].replace("-", "") if prepared_at else ""
    if len(compact) != 8:
        raise FileNotFoundError(f"could not derive proposal day from {proposal_plan_path}")
    iso = f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"
    return compact, iso


def _source_timestamp(payload: dict[str, Any], markdown_path: Path | None = None) -> str | None:
    for key in ("generated_at_utc", "generated_at", "prepared_at"):
        value = payload.get(key)
        if value:
            return str(value)
    if markdown_path is not None and markdown_path.exists():
        return _extract_packet_recorded_at(_load_text(markdown_path))
    return None


def _build_global_sources(*, workspace_root: Path, proposal_day_iso: str, family_ids: set[str]) -> dict[str, IndexedArtifact]:
    backtests_root = workspace_root / BACKTESTS_RELATIVE_PATH
    verifiers_root = workspace_root / VERIFIERS_RELATIVE_PATH

    proposal_plan_path = _latest_matching_file(workspace_root / STATE_RELATIVE_PATH, "proposed_distinct_families_*.json")
    proposal_payload = _load_json(proposal_plan_path)
    packet_md_path = _require_matching_file(backtests_root, f"{proposal_day_iso}_distinct_families_morning_packet.md")
    packet_timestamp = _extract_packet_recorded_at(_load_text(packet_md_path))

    bounded_backtest_json_path = _require_matching_file(backtests_root, f"{proposal_day_iso}_distinct_families_bounded_backtest.json")
    bounded_backtest_md_path = bounded_backtest_json_path.with_suffix(".md")
    bounded_backtest_payload = _load_json(bounded_backtest_json_path)

    verifier_json_path = _require_matching_file(verifiers_root, f"{proposal_day_iso}_distinct_families_synthetic_verifier.json")
    verifier_md_path = verifier_json_path.with_suffix(".md")
    verifier_payload = _load_json(verifier_json_path)
    verifier_families = set(verifier_payload.get("positive_case_results", {}).keys()) | set(
        verifier_payload.get("verifier_contract", {}).keys()
    )

    global_sources = {
        "proposal": IndexedArtifact(
            family_id=None,
            kind="proposal",
            label="proposal plan",
            source_kind="control",
            json_path=proposal_plan_path,
            timestamp=str(proposal_payload.get("prepared_at") or "") or None,
        ),
        "packet": IndexedArtifact(
            family_id=None,
            kind="packet",
            label="morning packet",
            source_kind="packet",
            md_path=packet_md_path,
            timestamp=packet_timestamp,
        ),
        "backtest": IndexedArtifact(
            family_id=None,
            kind="backtest",
            label="bounded backtest",
            source_kind="backtest",
            md_path=bounded_backtest_md_path,
            json_path=bounded_backtest_json_path,
            timestamp=_source_timestamp(bounded_backtest_payload),
        ),
        "verifier": IndexedArtifact(
            family_id=None,
            kind="verifier",
            label="synthetic verifier",
            source_kind="verifier",
            md_path=verifier_md_path,
            json_path=verifier_json_path,
            timestamp=_source_timestamp(verifier_payload),
        ),
    }

    family_sources: dict[str, list[IndexedArtifact]] = {family_id: [] for family_id in family_ids}
    for family_id in family_ids:
        family_sources[family_id].append(global_sources["proposal"])
        family_sources[family_id].append(global_sources["packet"])
        family_sources[family_id].append(global_sources["backtest"])
        if family_id in verifier_families:
            family_sources[family_id].append(global_sources["verifier"])

    for pattern in FAMILY_SOURCE_PATTERNS:
        glob_pattern = f"{proposal_day_iso}_*{pattern.suffix}.json"
        for json_path in sorted(backtests_root.glob(glob_pattern)):
            stem = json_path.stem
            family_id = stem[len(f"{proposal_day_iso}_") : -len(pattern.suffix)]
            if family_id not in family_sources:
                continue
            md_path = json_path.with_suffix(".md")
            payload = _load_json(json_path)
            family_sources[family_id].append(
                IndexedArtifact(
                    family_id=family_id,
                    kind=pattern.kind,
                    label=pattern.label,
                    source_kind=pattern.source_kind,
                    md_path=md_path if md_path.exists() else None,
                    json_path=json_path,
                    timestamp=_source_timestamp(payload, md_path if md_path.exists() else None),
                )
            )

    frozen_family_sources = {
        family_id: tuple(
            sorted(
                artifacts,
                key=lambda item: (_timestamp_sort_key(item.timestamp), item.kind, str(item.primary_path or "")),
                reverse=True,
            )
        )
        for family_id, artifacts in family_sources.items()
    }

    return global_sources, frozen_family_sources


def _index_baton_receipts(workspace_root: Path) -> dict[str, tuple[IndexedBatonReceipt, ...]]:
    campaigns_root = workspace_root / CAMPAIGNS_RELATIVE_PATH
    if not campaigns_root.exists():
        return {}

    grouped: dict[str, list[IndexedBatonReceipt]] = defaultdict(list)
    for state_path in campaigns_root.glob("*/STATE.json"):
        state = _load_optional_json(state_path)
        if not state:
            continue
        active_candidate_id = str(state.get("activeCandidateId") or "").strip()
        if not active_candidate_id:
            continue

        receipts_dir = state_path.parent / "receipts"
        if not receipts_dir.exists():
            continue

        for receipt_path in receipts_dir.glob("*.md"):
            markdown = _load_text(receipt_path)
            if _extract_backtick_field(markdown, "new active candidate") != active_candidate_id:
                continue
            grouped[active_candidate_id].append(
                IndexedBatonReceipt(
                    campaign_id=str(state.get("campaignId") or state_path.parent.name),
                    changed_at=_extract_backtick_field(markdown, "timestamp"),
                    from_family=_extract_backtick_field(markdown, "parked candidate"),
                    to_family=_extract_backtick_field(markdown, "new active candidate"),
                    path=receipt_path,
                    summary=_extract_backtick_field(markdown, "summary"),
                    forcing_evidence=_extract_backtick_field(markdown, "forcing evidence"),
                    prior_receipt=_extract_backtick_field(markdown, "prior campaign receipt"),
                )
            )

    return {
        family_id: tuple(
            sorted(
                receipts,
                key=lambda item: (_timestamp_sort_key(item.changed_at), str(item.path)),
                reverse=True,
            )
        )
        for family_id, receipts in grouped.items()
    }


def build_strategy_history_source_index(*, repo: Path, family_ids: Iterable[str]) -> StrategyHistorySourceIndex:
    workspace_root = repo.parent
    proposal_plan_path = _latest_matching_file(workspace_root / STATE_RELATIVE_PATH, "proposed_distinct_families_*.json")
    proposal_payload = _load_json(proposal_plan_path)
    proposal_day, proposal_day_iso = _proposal_day_components(proposal_plan_path, proposal_payload)
    global_sources, frozen_family_sources = _build_global_sources(
        workspace_root=workspace_root,
        proposal_day_iso=proposal_day_iso,
        family_ids=set(family_ids),
    )

    return StrategyHistorySourceIndex(
        proposal_day=proposal_day,
        proposal_plan_path=proposal_plan_path,
        active_plan_path=workspace_root / ACTIVE_PLAN_RELATIVE_PATH,
        global_sources=global_sources,
        family_sources=frozen_family_sources,
        baton_receipts=_index_baton_receipts(workspace_root),
    )
