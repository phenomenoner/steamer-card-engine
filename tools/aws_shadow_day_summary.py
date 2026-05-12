#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys


def parse_json_lines(text: str) -> list[dict]:
    out: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith('{'):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def find_latest_report(root: Path, day: str) -> Path | None:
    candidates = []
    for p in root.glob(f"{day}-postclose-collect-*/postclose_collect_report.json"):
        candidates.append(p)
    # one-shot cron dirs use compact TPE suffix but ISO day prefix
    candidates.extend(root.glob(f"{day}-*/postclose_collect_report.json"))
    candidates = [p for p in candidates if p.exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Steamer AWS shadow comparison day artifacts for CK.")
    parser.add_argument("--day", required=True, help="YYYY-MM-DD")
    parser.add_argument("--shadow-root", default="/root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison")
    parser.add_argument("--report", help="Explicit postclose_collect_report.json")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    shadow_root = Path(args.shadow_root)
    report_path = Path(args.report) if args.report else find_latest_report(shadow_root, args.day)
    if not report_path or not report_path.exists():
        msg = (
            f"BLOCKED aws-shadow-day-summary day={args.day} step=find_postclose_report "
            f"checked={shadow_root} missing=postclose_collect_report.json "
            f"next_action=run_or_verify_13:35_postclose_collect_before_summary"
        )
        (out_dir / "summary.md").write_text(msg + "\n", encoding="utf-8")
        print(msg)
        return 2

    report = json.loads(report_path.read_text())
    stdout_tail = str(report.get("stdout_tail", ""))
    receipts = parse_json_lines(stdout_tail)
    remote_receipt = None
    for obj in reversed(receipts):
        if obj.get("schema") in {"steamer-shadow-postclose-collect/v1", "steamer-shadow-readiness-dryrun/v1"}:
            remote_receipt = obj
            break
    if remote_receipt is None:
        remote_receipt = {}

    status = report.get("status")
    verdict = remote_receipt.get("verdict") or "UNKNOWN"
    active = remote_receipt.get("active_universe_count")
    legacy = remote_receipt.get("legacy_intent_count")
    card = remote_receipt.get("card_shadow_intent_count")
    diff = remote_receipt.get("intent_diff_count")
    observer_only = remote_receipt.get("observer_only")
    submits = remote_receipt.get("submits_orders")
    owns_lifecycle = remote_receipt.get("owns_ec2_lifecycle")
    required = remote_receipt.get("required_artifacts_present")
    selected = remote_receipt.get("selected_inputs") or {}

    if status == "Success" and verdict == "PASS_SHADOW_OBSERVER_DRY_RUN_ARTIFACTS" and observer_only is True and submits is False:
        top = "✅ AWS shadow comparison day summary"
        conclusion = "資料已回來；observer-only 安全旗標正常。"
        if legacy == 0 and card == 0 and diff == 0:
            meaning = "今天是 no-signal parity：兩邊都沒有產生 order intent，所以 diff=0；安全性有證據，signal-case equivalence 還要等有訊號日。"
        elif diff == 0:
            meaning = "今天有可比較 intent 且 diff=0；這是有效 equivalence 樣本。"
        else:
            meaning = "今天有差異樣本；需要打開 intent_diff.jsonl 做策略/轉譯差異分析。"
    else:
        top = "⚠️ AWS shadow comparison day summary"
        conclusion = "summary 找到 artifact，但狀態不是完整綠燈，請照 blocker 處理。"
        meaning = "先不要把這天計入 equivalence 通過樣本。"

    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = f"""{top} — {args.day}

結論：{conclusion}

數據：
- verdict: `{verdict}`
- active_universe_count: `{active}`
- legacy_intent_count: `{legacy}`
- card_shadow_intent_count: `{card}`
- intent_diff_count: `{diff}`
- observer_only: `{observer_only}`
- submits_orders: `{submits}`
- owns_ec2_lifecycle: `{owns_lifecycle}`
- required_artifacts_present: `{required}`

解讀：{meaning}

輸入來源：
- legacy_decisions: `{selected.get('legacy_decisions', '')}`
- orders: `{selected.get('orders', '')}`
- candidate_decisions: `{selected.get('candidate_decisions', '')}`

Receipts：
- local_report: `{report_path}`
- remote_artifact_root: `{report.get('remote_artifact_root')}`
- local_summary_dir: `{out_dir}`

Generated: {generated}
"""
    machine = {
        "schema": "steamer-shadow-day-summary/v1",
        "day": args.day,
        "source_report": str(report_path),
        "local_report_status": status,
        "remote_artifact_root": report.get("remote_artifact_root"),
        "remote_receipt": remote_receipt,
        "summary_markdown": str(out_dir / "summary.md"),
    }
    (out_dir / "summary.json").write_text(json.dumps(machine, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "summary.md").write_text(md, encoding="utf-8")
    print(md.rstrip())
    return 0 if status == "Success" and verdict == "PASS_SHADOW_OBSERVER_DRY_RUN_ARTIFACTS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
