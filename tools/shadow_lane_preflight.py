#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import re
import subprocess
from typing import Any

STEAMER_LIFECYCLE_KEYWORDS = [
    "EC2 power-on",
    "online sim kickoff",
    "online sim verify",
    "archive/upload",
    "EC2 stop guardrail",
]

FORBIDDEN_LIFECYCLE_TOKENS = [
    "start-instances",
    "stop-instances",
    "steamer_ec2_power_on_daily.py",
    "steamer_ec2_stop_guardrail_daily.py",
]


@dataclass
class CronLine:
    job_id: str
    line: str
    role: str | None = None


def run_command(command: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
    proc = subprocess.run(command, cwd=str(cwd) if cwd else None, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def classify_role(line: str) -> str | None:
    lowered = line.lower()
    if "ec2 power-on" in lowered:
        return "ec2_power_on"
    if "online sim k" in lowered or "online sim kickoff" in lowered:
        return "sim_kickoff"
    if "online sim v" in lowered or "verify" in lowered or "autoheal" in lowered:
        return "sim_verify_autoheal"
    if "archive" in lowered:
        return "archive_upload"
    if "ec2 stop gua" in lowered or "stop guardrail" in lowered:
        return "ec2_stop_guardrail"
    return None


def parse_openclaw_cron_list(text: str) -> list[CronLine]:
    rows: list[CronLine] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "steamer" not in line.lower():
            continue
        match = re.match(r"([0-9a-f]{8}-[0-9a-f-]{27,})\s+(.+)", line)
        if not match:
            continue
        job_id = match.group(1)
        rows.append(CronLine(job_id=job_id, line=line, role=classify_role(line)))
    return rows


def inspect_live_cron() -> tuple[list[CronLine], dict[str, Any]]:
    code, stdout, stderr = run_command(["openclaw", "cron", "list"])
    meta = {"command": "openclaw cron list", "exit_code": code, "stderr": stderr[:2000]}
    if code != 0:
        return [], meta
    return parse_openclaw_cron_list(stdout), meta


def inspect_spec_tokens(paths: list[Path]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            files = [p for p in path.rglob("*") if p.is_file()]
        else:
            files = [path]
        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for token in FORBIDDEN_LIFECYCLE_TOKENS:
                if token in text:
                    hits.append({"path": str(file_path), "token": token})
    return hits


def build_preflight(*, repo_root: Path, output_dir: Path, dry_run_manifest: Path | None) -> dict[str, Any]:
    live_rows, cron_meta = inspect_live_cron()
    roles: dict[str, list[str]] = {}
    for row in live_rows:
        if row.role:
            roles.setdefault(row.role, []).append(row.job_id)

    spec_roots = [
        repo_root / "docs" / "AWS_SHADOW_COMPARISON_LANE_PLAN_2026-05-10.md",
        repo_root / "ops" / "execution-packets" / "2026-05-10_order-intent-equivalence-goal.packet.md",
    ]
    if dry_run_manifest:
        spec_roots.append(dry_run_manifest)
    forbidden_hits = inspect_spec_tokens(spec_roots)
    # The plan is allowed to mention existing lifecycle scripts as observations,
    # but a proposed dry-run manifest must not introduce them.
    manifest_forbidden_hits = [hit for hit in forbidden_hits if dry_run_manifest and Path(hit["path"]).resolve() == dry_run_manifest.resolve()]

    required_roles = ["ec2_power_on", "sim_kickoff", "sim_verify_autoheal", "archive_upload", "ec2_stop_guardrail"]
    missing_roles = [role for role in required_roles if not roles.get(role)]
    duplicate_lifecycle_roles = {role: ids for role, ids in roles.items() if role in {"ec2_power_on", "ec2_stop_guardrail"} and len(ids) > 1}

    verdict = "PASS_SHADOW_PREFLIGHT_DRY_RUN"
    blockers = []
    if cron_meta["exit_code"] != 0:
        verdict = "BLOCKED_CRON_READBACK"
        blockers.append("openclaw cron list failed")
    if missing_roles:
        verdict = "NEEDS_SHADOW_PREFLIGHT_REVIEW"
        blockers.append(f"missing expected lifecycle roles: {missing_roles}")
    if duplicate_lifecycle_roles:
        verdict = "NEEDS_SHADOW_PREFLIGHT_REVIEW"
        blockers.append(f"duplicate lifecycle owners: {duplicate_lifecycle_roles}")
    if manifest_forbidden_hits:
        verdict = "FAILS_NO_LIFECYCLE_OWNERSHIP_RULE"
        blockers.append("dry-run manifest contains forbidden lifecycle start/stop tokens")

    return {
        "kind": "steamer_card_engine.shadow_lane_preflight.v1",
        "verdict": verdict,
        "blockers": blockers,
        "live_cron_meta": cron_meta,
        "live_lifecycle_roles": roles,
        "live_steamer_rows": [asdict(row) for row in live_rows],
        "duplicate_lifecycle_roles": duplicate_lifecycle_roles,
        "missing_roles": missing_roles,
        "dry_run_manifest": str(dry_run_manifest) if dry_run_manifest else None,
        "manifest_forbidden_lifecycle_hits": manifest_forbidden_hits,
        "rules": {
            "shadow_lane_must_not_start_or_stop_ec2": True,
            "shadow_lane_should_launch_under_existing_kickoff": True,
            "shadow_lane_should_archive_under_existing_archive_job": True,
        },
        "recommended_next_step": "Add an EC2-side observer worker manifest only after this preflight passes and the manifest contains no start/stop lifecycle ownership.",
    }


def write_report(summary: dict[str, Any]) -> str:
    lines = [
        "# AWS shadow lane preflight",
        "",
        f"## Verdict\n{summary['verdict']}",
        "",
        f"## Blockers\n{summary['blockers']}",
        "",
        "## Live lifecycle roles",
    ]
    for role, ids in summary["live_lifecycle_roles"].items():
        lines.append(f"- {role}: `{ids}`")
    lines.extend([
        "",
        "## Rules",
        "- Shadow lane must not start or stop EC2.",
        "- Shadow lane should be launched by existing kickoff after EC2 readiness.",
        "- Shadow lane artifacts should be archived by existing archive/upload job.",
        "",
        "## Recommended next step",
        summary["recommended_next_step"],
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run preflight for the Steamer AWS shadow comparison lane.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dry-run-manifest")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    dry_run_manifest = Path(args.dry_run_manifest).resolve() if args.dry_run_manifest else None
    summary = build_preflight(repo_root=repo_root, output_dir=output_dir, dry_run_manifest=dry_run_manifest)
    summary_path = output_dir / "shadow_lane_preflight_summary.json"
    report_path = output_dir / "shadow_lane_preflight_report.md"
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(write_report(summary), encoding="utf-8")
    print(json.dumps({"verdict": summary["verdict"], "summary_path": str(summary_path), "report_path": str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
