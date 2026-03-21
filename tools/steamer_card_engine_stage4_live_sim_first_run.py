#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

WORKSPACE = Path('/root/.openclaw/workspace')
PLAYBOOK = WORKSPACE / 'openclaw-async-coding-playbook'
ENGINE_REPO = WORKSPACE / 'steamer-card-engine'
ARTIFACT_ROOT = PLAYBOOK / 'projects/trading-research/artifacts/tw-paper-sim'
DEFAULT_DECK = ENGINE_REPO / 'examples/decks/tw_cash_intraday.toml'
DEFAULT_OUTPUT_ROOT = ENGINE_REPO / 'runs'


def _latest_session_date() -> str:
    candidates = []
    if ARTIFACT_ROOT.exists():
        for child in ARTIFACT_ROOT.iterdir():
            if not child.is_dir():
                continue
            if (child / 'dashboard.json').exists() and (child / 'decisions.jsonl').exists():
                candidates.append(child.name)
    if not candidates:
        raise SystemExit(f'No captured tw-paper-sim session dirs found under {ARTIFACT_ROOT}')
    return sorted(candidates)[-1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run the checked-in Stage 4 Steamer Card Engine live-sim execution primitive.'
    )
    parser.add_argument('--session-date', help='Session date YYYY-MM-DD. Defaults to latest captured tw-paper-sim dir.')
    parser.add_argument('--baseline-dir', help='Override captured baseline dir. Defaults to tw-paper-sim/<session_date>.')
    parser.add_argument('--deck', default=str(DEFAULT_DECK), help='Deck manifest path.')
    parser.add_argument('--output-root', default=str(DEFAULT_OUTPUT_ROOT), help='Engine runs output root.')
    parser.add_argument('--scenario-id', help='Override scenario id.')
    parser.add_argument('--run-id', help='Override run id.')
    parser.add_argument('--max-events', type=int)
    parser.add_argument('--max-decisions', type=int)
    parser.add_argument('--dry-run', action='store_true', help='Validate the contract without emitting a bundle.')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    session_date = args.session_date or _latest_session_date()
    baseline_dir = Path(args.baseline_dir) if args.baseline_dir else (ARTIFACT_ROOT / session_date)
    baseline_dir = baseline_dir.resolve()

    if not baseline_dir.exists():
        raise SystemExit(f'Baseline dir not found: {baseline_dir}')
    if not (baseline_dir / 'decisions.jsonl').exists():
        raise SystemExit(f'Missing required decisions.jsonl in {baseline_dir}')
    if not (baseline_dir / 'dashboard.json').exists():
        raise SystemExit(f'Missing required dashboard.json in {baseline_dir}')

    scenario_id = args.scenario_id or f'tw-live-sim.twse.{session_date}.full-session'
    command = [
        'uv',
        'run',
        '--project',
        str(ENGINE_REPO),
        'steamer-card-engine',
        'sim',
        'run-live',
        '--deck',
        str(Path(args.deck).resolve()),
        '--session-date',
        session_date,
        '--baseline-dir',
        str(baseline_dir),
        '--output-root',
        str(Path(args.output_root).resolve()),
        '--scenario-id',
        scenario_id,
        '--json',
    ]
    if args.run_id:
        command.extend(['--run-id', args.run_id])
    if args.max_events is not None:
        command.extend(['--max-events', str(args.max_events)])
    if args.max_decisions is not None:
        command.extend(['--max-decisions', str(args.max_decisions)])
    if args.dry_run:
        command.append('--dry-run')

    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        if completed.stdout:
            sys.stderr.write(completed.stdout)
        return completed.returncode

    payload = json.loads(completed.stdout)
    receipt: dict[str, object] = {
        'mode': 'dry-run' if args.dry_run else 'emit',
        'session_date': session_date,
        'baseline_dir': str(baseline_dir),
        'scenario_id': scenario_id,
        'command': command,
        'engine_receipt': payload,
    }

    if args.dry_run:
        receipt['verified'] = {
            'side_effect_free': not Path(payload['output_dir']).exists(),
            'run_type': payload.get('run_type', 'live-sim'),
            'capability_posture': payload.get('capability_posture', {'trade_enabled': False}),
        }
    else:
        bundle_dir = Path(payload['bundle_dir']).resolve()
        run_manifest = json.loads((bundle_dir / 'run-manifest.json').read_text(encoding='utf-8'))
        receipt['verified'] = {
            'bundle_dir': str(bundle_dir),
            'run_type': run_manifest.get('run_type'),
            'trade_enabled': run_manifest.get('capability_posture', {}).get('trade_enabled'),
            'has_scenario_spec': (bundle_dir / 'scenario-spec.json').exists(),
            'has_anomalies': (bundle_dir / 'anomalies.json').exists(),
            'has_file_index': (bundle_dir / 'file-index.json').exists(),
        }

    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
