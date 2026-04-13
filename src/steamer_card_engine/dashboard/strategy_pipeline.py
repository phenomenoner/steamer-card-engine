from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fixtures import repo_root
from .strategy_line_state import LINE_STATE_RELATIVE_PATH, load_latest_line_state


class StrategyPipelineDataError(Exception):
    """Raised when the local strategy-pipeline surface cannot be built."""


DEFAULT_CAMPAIGN_ID = "2026-04-failed-auction-short-cluster-slow-cook"
DEFAULT_CAMPAIGN_ROOT = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/lanes/autonomous-slow-cook/campaigns"
)
CAMPAIGN_INDEX_RELATIVE_PATH = Path(
    "StrategyExecuter_Steamer-Antigravity/projects/steamer/lanes/autonomous-slow-cook/campaigns/INDEX.json"
)
RUNTIME_SHADOW_RELATIVE_PATH = Path(".state/steamer/autonomous_slow_cook_handoff_shadow.v1.json")
RUNTIME_ACTIVATION_FALLBACK = Path(".state/steamer/autonomous_slow_cook_runtime/activation.v1.json")
RUNTIME_CONTROL_HINT = "runtime activation dispatch selection"


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


def _truthy_text(value: Any) -> str:
    value_text = str(value or "").strip()
    return value_text


def _campaign_priority(item: dict[str, Any]) -> int:
    try:
        return int(item.get("priority"))
    except (TypeError, ValueError):
        return 99_999


def _campaign_entry_lookup(campaign_index: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    campaigns = campaign_index.get("campaigns")
    if not isinstance(campaigns, list):
        return [], {}

    ordered = [item for item in campaigns if isinstance(item, dict)]
    ordered.sort(key=_campaign_priority)

    lookup: dict[str, dict[str, Any]] = {}
    for item in ordered:
        campaign_id = _truthy_text(item.get("campaignId"))
        if campaign_id:
            lookup[campaign_id] = item
    return ordered, lookup


def _first_dispatchable(ordered_campaigns: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in ordered_campaigns:
        phase = _truthy_text(item.get("phase"))
        if bool(item.get("dispatchable") is True) and phase != "closed":
            return item
    return None


def _first_entry(ordered_campaigns: list[dict[str, Any]]) -> dict[str, Any] | None:
    return ordered_campaigns[0] if ordered_campaigns else None


def _resolve_path(path_value: str, workspace_root: Path) -> Path | None:
    path_text = _truthy_text(path_value)
    if not path_text:
        return None
    path = Path(path_text)
    if not path.is_absolute():
        path = workspace_root / path
    return path


def _build_runtime_profile(
    *,
    workspace_root: Path,
    campaign_index_ordered: list[dict[str, Any]],
    campaign_index_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    runtime_shadow_path = workspace_root / RUNTIME_SHADOW_RELATIVE_PATH
    runtime_shadow = _load_optional_json(runtime_shadow_path) or {}

    runtime_activation = dict(runtime_shadow.get("runtime_activation") or {})
    runtime_dispatch = dict(runtime_shadow.get("runtime_dispatch") or {})
    runtime_selection = dict(runtime_dispatch.get("selection") or {})

    activation_state_path = _resolve_path(
        _truthy_text(runtime_activation.get("state_path"))
        or _truthy_text(runtime_shadow.get("runtime_activation_path", "")),
        workspace_root,
    )
    activation_state = _load_optional_json(activation_state_path or (workspace_root / RUNTIME_ACTIVATION_FALLBACK)) or {}

    requested_campaign = _truthy_text(runtime_activation.get("campaign_id")) or _truthy_text(activation_state.get("campaignId"))
    dispatch_campaign = _truthy_text(runtime_dispatch.get("campaign_id"))
    fallback_campaign = _truthy_text(runtime_dispatch.get("suggested_campaign_id"))

    runtime_state = _truthy_text(runtime_dispatch.get("state")) or "unavailable"
    runtime_dispatch_reason = _truthy_text(runtime_dispatch.get("reason"))
    runtime_selection_policy = RUNTIME_CONTROL_HINT

    policy_hint = _truthy_text(runtime_selection.get("policy"))
    policy_id = _truthy_text(runtime_selection.get("policy_id"))
    selection_reason = _truthy_text(runtime_selection.get("selection_reason"))
    selection_notes = _truthy_text(runtime_selection.get("selection_notes")) or runtime_selection_policy
    runtime_candidate_set = runtime_selection.get("candidate_set") if isinstance(runtime_selection.get("candidate_set"), list) else []
    runtime_selected_campaign_id = _truthy_text(runtime_selection.get("selected_campaign_id"))

    selected_campaign_id = runtime_selected_campaign_id or dispatch_campaign or requested_campaign
    selected_entry: dict[str, Any] | None = None

    if not selected_campaign_id and fallback_campaign:
        selected_campaign_id = fallback_campaign

    if selected_campaign_id and selected_campaign_id in campaign_index_lookup:
        selected_entry = campaign_index_lookup[selected_campaign_id]

    # Fallback when the runtime shadow is older and does not include explicit selection metadata.
    if not policy_hint:
        if runtime_state == "applied":
            policy_hint = "runtime_dispatch"
            selection_reason = "runtime dispatch campaign selected"
        elif runtime_state == "runtime_fallback" or runtime_state == "campaign_missing":
            policy_hint = "runtime_fallback"
            selection_reason = "runtime dispatch suggests fallback campaign"
        elif runtime_state == "index_default":
            policy_hint = "index_default"
            selection_reason = "no runtime campaign target; using index order"
        elif runtime_state == "index_fallback":
            policy_hint = "index_fallback"
            selection_reason = "runtime target missing; fallback to index selection"
        else:
            policy_hint = "runtime_target_missing"
            selection_reason = "requested runtime campaign not found in INDEX.json"

    if not runtime_candidate_set:
        ordered_dispatchable = [_campaign for _campaign in campaign_index_ordered if bool(_campaign.get("dispatchable") is True) and _truthy_text(_campaign.get("phase")) not in {"closed", "operator-gate"}]
        runtime_candidate_set = [
            {
                "campaignId": str(item.get("campaignId") or ""),
                "priority": int(item.get("priority") or 0) if str(item.get("priority") or "").strip() else 0,
                "phase": _truthy_text(item.get("phase")),
                "dispatchable": bool(item.get("dispatchable") is True),
                "status": _truthy_text(item.get("status")),
            }
            for item in ordered_dispatchable[:10]
        ]

    if not policy_id:
        policy_id = f"runtime_selector_v1/{policy_hint}"

    if not selection_reason:
        selection_reason = "runtime shadow dispatch campaign selected"
    if not selected_entry and selected_campaign_id and selected_campaign_id in campaign_index_lookup:
        selected_entry = campaign_index_lookup[selected_campaign_id]

    if not selected_entry and runtime_selected_campaign_id and runtime_state in {"campaign_missing", "misconfigured_activation"}:
        if fallback_campaign and fallback_campaign in campaign_index_lookup:
            selected_entry = campaign_index_lookup[fallback_campaign]

    if selected_entry and not selected_campaign_id:
        selected_campaign_id = _truthy_text(selected_entry.get("campaignId") or "")

    return {
        "activation_profile": {
            "path": _safe_relpath(
                activation_state_path if activation_state_path else workspace_root / RUNTIME_ACTIVATION_FALLBACK,
                workspace_root,
            ),
            "enabled": bool(runtime_activation.get("enabled") if "enabled" in runtime_activation else activation_state.get("enabled")),
            "campaign_id": _truthy_text(runtime_activation.get("campaign_id")) or _truthy_text(activation_state.get("campaignId")),
            "updated_at": _truthy_text(runtime_activation.get("updated_at")) or _truthy_text(activation_state.get("updated_at")),
            "raw_state_path": _truthy_text(runtime_activation.get("state_path")) or None,
        },
        "dispatch": {
            "state": runtime_state,
            "campaign_id": dispatch_campaign,
            "requested_campaign_id": requested_campaign or None,
            "suggested_campaign_id": fallback_campaign or None,
            "attempted": bool(runtime_dispatch.get("attempted") is True),
            "fallback_used": bool(runtime_dispatch.get("fallback_used") is True),
            "activation_mismatch": bool(runtime_dispatch.get("activation_mismatch") is True),
            "returncode": runtime_dispatch.get("returncode"),
            "reason": runtime_dispatch_reason or None,
            "reason_compact": runtime_dispatch_reason[:280] if len(runtime_dispatch_reason) > 280 else runtime_dispatch_reason,
        },
        "selection": {
            "policy": policy_hint,
            "policy_id": policy_id,
            "selected_campaign_id": selected_campaign_id or None,
            "requested_campaign_id": requested_campaign or None,
            "selected_entry_present": selected_entry is not None,
            "selection_reason": selection_reason,
            "selection_notes": selection_notes,
            "candidate_set": runtime_candidate_set,
            "candidate_count": len(runtime_candidate_set),
        },
        "selected_entry": selected_entry,
        "shadow_path": _safe_relpath(runtime_shadow_path, workspace_root),
    }
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

    line_state_path = Path(str(line_state.get("_path")) if line_state.get("_path") else "")

    campaign_index_path = workspace_root / CAMPAIGN_INDEX_RELATIVE_PATH
    campaign_index = _load_optional_json(campaign_index_path) or {"campaigns": []}
    ordered_campaigns, campaign_lookup = _campaign_entry_lookup(campaign_index)

    runtime_profile = _build_runtime_profile(
        workspace_root=workspace_root,
        campaign_index_ordered=ordered_campaigns,
        campaign_index_lookup=campaign_lookup,
    )

    selected_campaign_id = runtime_profile["selection"].get("selected_campaign_id")
    selected_entry = runtime_profile["selected_entry"]
    if selected_entry is None and selected_campaign_id:
        selected_entry = campaign_lookup.get(selected_campaign_id)

    selected_campaign_root = _resolve_path(
        _truthy_text(selected_entry.get("campaignPath") if selected_entry else "")
        if selected_entry
        else str(DEFAULT_CAMPAIGN_ROOT / selected_campaign_id),
        workspace_root,
    )
    if selected_campaign_root is None:
        selected_campaign_root = workspace_root / DEFAULT_CAMPAIGN_ROOT / DEFAULT_CAMPAIGN_ID

    campaign_state_path = selected_campaign_root / "STATE.json"
    campaign_next_action_path = selected_campaign_root / "NEXT_ACTION.json"
    campaign_status_path = selected_campaign_root / "STATUS.md"
    campaign_gates_path = selected_campaign_root / "GATES.md"

    campaign_state = _load_optional_json(campaign_state_path) if campaign_state_path.exists() else {}
    campaign_next_action = _load_optional_json(campaign_next_action_path) if campaign_next_action_path.exists() else {}
    autonomy_readiness = dict(campaign_state.get("autonomyReadiness") or {})

    runtime_dispatch = runtime_profile["dispatch"]
    runtime_dispatch_state = runtime_dispatch["state"]
    runtime_dispatch_applied = (
        runtime_dispatch_state == "applied"
        and runtime_dispatch.get("attempted") is True
        and (runtime_dispatch.get("returncode") is None or runtime_dispatch.get("returncode") == 0)
    )
    runtime_blocked = runtime_dispatch_state in {
        "unavailable",
        "inactive",
        "campaign_missing",
        "dispatcher_missing",
        "misconfigured_activation",
        "skipped_not_dispatchable",
        "blocked",
    }
    campaign_dispatchable = bool(selected_entry.get("dispatchable") is True) if selected_entry else False
    if runtime_blocked:
        campaign_dispatchable = False
    research_autonomous = bool(autonomy_readiness.get("researchAutonomous", False)) and runtime_dispatch_applied and not runtime_blocked
    attach_autonomous = bool(autonomy_readiness.get("attachAutonomous", False)) and runtime_dispatch_applied and not runtime_blocked

    current_state = f"runtime dispatch {runtime_dispatch_state}"

    summary_note = runtime_dispatch.get("reason") or "No runtime dispatch note is available from the handoff state shadow document."

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
            "headline": "Current canon flow: intake -> family selection -> verifier bridge -> campaign controller -> bounded autonomous research dispatch -> steamer-card-engine handoff / live sim.",
            "current_state": current_state,
            "verdict": f"research-autonomous-{ 'yes' if research_autonomous else 'no' } / attach-autonomous-{ 'yes' if attach_autonomous else 'no' }",
            "note": str(summary_note),
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
            "campaign_index_path": _safe_relpath(campaign_index_path, workspace_root),
            "runtime_shadow_path": runtime_profile.get("shadow_path"),
            "runtime_activation": runtime_profile.get("activation_profile"),
            "runtime_dispatch": runtime_profile.get("dispatch"),
            "runtime_campaign_selection": runtime_profile.get("selection"),
            "selected_campaign_id": selected_campaign_id,
            "selection_hint": RUNTIME_CONTROL_HINT,
        },
        "campaign_state": {
            "campaign_id": _truthy_text(campaign_state.get("campaignId") or selected_campaign_id),
            "status": campaign_state.get("status"),
            "phase": campaign_state.get("phase"),
            "active_candidate_id": campaign_state.get("activeCandidateId"),
            "dispatchable": campaign_dispatchable,
            "cluster_mode": (campaign_state.get("clusterCadence") or {}).get("mode"),
            "cluster_window": (campaign_state.get("clusterCadence") or {}).get("clusterWindow"),
            "max_bounded_slices_per_cluster": (campaign_state.get("clusterCadence") or {}).get("maxBoundedSlicesPerCluster"),
            "next_action_id": campaign_next_action.get("actionId"),
            "next_worker_type": campaign_next_action.get("workerType"),
            "next_candidate_id": campaign_next_action.get("candidateId"),
            "retry_remaining_for_active": ((campaign_state.get("retryBudget") or {}).get("remainingForActive")),
            "stale_after_active": autonomy_readiness.get("staleAfterActive"),
            "stale_after_parked": autonomy_readiness.get("staleAfterParked"),
            "research_autonomous": research_autonomous,
            "attach_autonomous": attach_autonomous,
            "campaign_path": _safe_relpath(selected_campaign_root, workspace_root),
            "state_path": _safe_relpath(campaign_state_path if campaign_state_path.exists() else None, workspace_root),
            "next_action_path": _safe_relpath(campaign_next_action_path if campaign_next_action_path.exists() else None, workspace_root),
            "status_path": _safe_relpath(campaign_status_path if campaign_status_path.exists() else None, workspace_root),
            "gates_path": _safe_relpath(campaign_gates_path if campaign_gates_path.exists() else None, workspace_root),
            "runtime_dispatch": runtime_profile.get("dispatch"),
            "selection": runtime_profile.get("selection"),
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
                _safe_relpath(campaign_state_path if campaign_state_path.exists() else None, workspace_root),
                _safe_relpath(campaign_next_action_path if campaign_next_action_path.exists() else None, workspace_root),
                _safe_relpath(campaign_status_path if campaign_status_path.exists() else None, workspace_root),
                _safe_relpath(campaign_gates_path if campaign_gates_path.exists() else None, workspace_root),
            ]
            if path
        ],
    }
