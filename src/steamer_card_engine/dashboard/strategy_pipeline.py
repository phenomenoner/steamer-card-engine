from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fixtures import repo_root
from .strategy_line_state import LINE_STATE_RELATIVE_PATH, load_latest_line_state


class StrategyPipelineDataError(Exception):
    """Raised when the local strategy-pipeline surface cannot be built."""


def _workspace_root(repo: Path) -> Path:
    return repo.parent


def _safe_relpath(path: Path | None, base: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_strategy_pipeline_view(root: Path | None = None) -> dict[str, Any]:
    repo = root or repo_root()
    workspace_root = _workspace_root(repo)

    line_state = load_latest_line_state(
        workspace_root=workspace_root,
        line_id="intraday_failed_auction_short",
    )
    if line_state is None:
        raise StrategyPipelineDataError(
            "missing line state: StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/state/*_intraday_failed_auction_short_line_state.json"
        )

    control_root = workspace_root / ".state/steamer/card-engine-morning-paired-lane"
    proposal_matches = sorted(control_root.glob("proposed_distinct_families_*.json")) if control_root.exists() else []
    proposal_plan_path = proposal_matches[-1] if proposal_matches else control_root / "proposed_distinct_families_latest.json"
    active_plan_path = control_root / "active_deck_plan.json"
    activation_latest_path = control_root / "activation_latest.json"
    nightly_state_path = workspace_root / "StrategyExecuter_Steamer-Antigravity/projects/steamer/production/nightly_state.json"
    pipeline_eod_latest_path = workspace_root / "StrategyExecuter_Steamer-Antigravity/projects/steamer/ops/pipeline-eod/LATEST.md"

    proposal_plan = _load_optional_json(proposal_plan_path)
    active_plan = _load_optional_json(active_plan_path)
    activation_latest = _load_optional_json(activation_latest_path)
    nightly_state = _load_optional_json(nightly_state_path)

    line_state_path = Path(str(line_state.get("_path")))

    components = [
        {
            "component_id": "intake-adapters",
            "label": "靈感入口 / intake adapters",
            "role": "collect and normalize ideas into governed intake artifacts",
            "current_surface": "generic ingest core + x_scout first adapter",
            "status": "active",
            "source_paths": [
                "StrategyExecuter_Steamer-Antigravity/projects/steamer/handoffs/2026-04-12_strategy-intake-lanes_checkpoint.md",
            ],
            "note": "入口已打開，但仍維持 adapter-first；第二個真來源出現前不先造 registry。",
        },
        {
            "component_id": "research-canon",
            "label": "研究收斂 / family canon",
            "role": "select the parent family and bounded first variant",
            "current_surface": "failed-auction-short family-selection packet",
            "status": "active",
            "source_paths": [
                "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/backtests/2026-04-12_intraday_failed_auction_short_family_selection.md",
                _safe_relpath(line_state_path, workspace_root),
            ],
            "note": "已定錨 parent family 與 Variant 1。",
        },
        {
            "component_id": "verifier-bridge",
            "label": "驗證橋 / verifier bridge",
            "role": "run the first bounded real-data event scan and emit a verdict",
            "current_surface": str(line_state.get("verifier_id") or "unknown verifier"),
            "status": str(line_state.get("run_state") or "unknown"),
            "source_paths": [
                "StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/verifiers/2026-04-12_ifa_short_v1_orb_vwap_event_scan.md",
                _safe_relpath(line_state_path, workspace_root),
            ],
            "note": str(line_state.get("blocking_reason") or "No blocking reason recorded."),
        },
        {
            "component_id": "dashboard-observability",
            "label": "Dashboard 觀測面",
            "role": "render read-only strategy/control truth for operators and collaborators",
            "current_surface": "Steamer Dashboard",
            "status": "active",
            "source_paths": [
                "steamer-card-engine/src/steamer_card_engine/dashboard/strategy_powerhouse.py",
                "steamer-card-engine/src/steamer_card_engine/dashboard/strategy_pipeline.py",
            ],
            "note": "現已可在 dashboard 中看到 focus lines、架構對照與 pipeline tab。",
        },
        {
            "component_id": "live-sim-execution",
            "label": "Live Sim 執行面",
            "role": "replay / card / deck / live sim runtime surface",
            "current_surface": "steamer-card-engine",
            "status": str(line_state.get("live_sim_attach_state") or "unknown"),
            "source_paths": [
                _safe_relpath(active_plan_path if active_plan_path.exists() else None, workspace_root),
                _safe_relpath(proposal_plan_path if proposal_plan_path.exists() else None, workspace_root),
            ],
            "note": "下游 execution surface；在 verifier 結果與 handoff gate 沒過前，不應提早 attach。",
        },
    ]

    autonomous_drivers = [
        {
            "driver_id": "xscout-intake",
            "label": "x_scout ingest",
            "role": "collect low-noise strategy ideas into the intake lane",
            "state": "active",
            "schedule_or_trigger": "periodic scout + ingest path",
            "source_path": "StrategyExecuter_Steamer-Antigravity/docs/STEAMER_POWERHOUSE_PIPELINE.md",
            "break_risk": "Without a structured line state, intake can keep generating cards while the downstream line is actually blocked.",
        },
        {
            "driver_id": "pipeline-eod-1345",
            "label": "pipeline eod 13:45",
            "role": "day-end operational closure / checks",
            "state": "active" if pipeline_eod_latest_path.exists() else "missing",
            "schedule_or_trigger": "market-day eod lane",
            "source_path": _safe_relpath(pipeline_eod_latest_path if pipeline_eod_latest_path.exists() else None, workspace_root),
            "break_risk": "EOD closure can be healthy while a new research line is still only contract-deep.",
        },
        {
            "driver_id": "nightly-eval",
            "label": "nightly eval",
            "role": "nightly governance / candidate health summary",
            "state": "active" if nightly_state is not None else "unknown",
            "schedule_or_trigger": "nightly eval loop",
            "source_path": _safe_relpath(nightly_state_path if nightly_state_path.exists() else None, workspace_root),
            "break_risk": "Nightly state does not automatically mean the new failed-auction verifier line is runnable end-to-end.",
        },
        {
            "driver_id": "runtime-activation",
            "label": "autonomous runtime activation",
            "role": "proposal/active paired-lane activation and runtime gating",
            "state": "active" if activation_latest is not None else "unknown",
            "schedule_or_trigger": "activation / promotion lane",
            "source_path": _safe_relpath(activation_latest_path if activation_latest_path.exists() else None, workspace_root),
            "break_risk": "If handoff gates are implicit, activation logic can look alive while the new research line is not actually handoff-ready.",
        },
    ]

    proposal_family = str((proposal_plan or {}).get("family") or "") or None
    active_family = str((active_plan or {}).get("family") or "") or None

    return {
        "updated_at": line_state.get("updated_at"),
        "topology_changed": False,
        "summary": {
            "headline": "Current canon flow: intake -> family selection -> verifier bridge -> dashboard observability -> steamer-card-engine handoff / live sim.",
            "current_state": "autonomous-with-guardrails target; not autonomous-safe yet",
            "verdict": "not-yet",
            "note": "The line is opened and visible, but the verifier bridge and machine-readable handoff gate are not complete enough for autonomous non-stop execution.",
        },
        "line_state": {
            "line_id": line_state.get("line_id"),
            "title": line_state.get("title"),
            "family_id": line_state.get("family_id"),
            "variant_id": line_state.get("variant_id"),
            "verifier_id": line_state.get("verifier_id"),
            "run_state": line_state.get("run_state"),
            "verdict": line_state.get("verdict"),
            "blocking_reason": line_state.get("blocking_reason"),
            "handoff_ready": line_state.get("handoff_ready"),
            "live_sim_attach_state": line_state.get("live_sim_attach_state"),
            "state_path": _safe_relpath(line_state_path, workspace_root),
        },
        "canon_flow": list(line_state.get("stage_states") or []),
        "components": components,
        "autonomous_drivers": autonomous_drivers,
        "handoff_gate": dict(line_state.get("handoff_gate") or {}),
        "control_plane": {
            "proposal_family": proposal_family,
            "active_family": active_family,
            "proposal_plan_path": _safe_relpath(proposal_plan_path if proposal_plan_path.exists() else None, workspace_root),
            "active_plan_path": _safe_relpath(active_plan_path if active_plan_path.exists() else None, workspace_root),
            "activation_latest_path": _safe_relpath(activation_latest_path if activation_latest_path.exists() else None, workspace_root),
            "nightly_state_path": _safe_relpath(nightly_state_path if nightly_state_path.exists() else None, workspace_root),
            "line_state_root": _safe_relpath(workspace_root / LINE_STATE_RELATIVE_PATH, workspace_root),
        },
        "sources": [
            path
            for path in [
                _safe_relpath(line_state_path, workspace_root),
                _safe_relpath(proposal_plan_path if proposal_plan_path.exists() else None, workspace_root),
                _safe_relpath(active_plan_path if active_plan_path.exists() else None, workspace_root),
                _safe_relpath(activation_latest_path if activation_latest_path.exists() else None, workspace_root),
                _safe_relpath(nightly_state_path if nightly_state_path.exists() else None, workspace_root),
                _safe_relpath(pipeline_eod_latest_path if pipeline_eod_latest_path.exists() else None, workspace_root),
            ]
            if path
        ],
    }
