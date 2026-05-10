from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "shadow_lane_preflight.py"
spec = importlib.util.spec_from_file_location("shadow_lane_preflight", MODULE_PATH)
assert spec is not None and spec.loader is not None
shadow_lane_preflight = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = shadow_lane_preflight
spec.loader.exec_module(shadow_lane_preflight)


def test_parse_lifecycle_roles_from_cron_lines() -> None:
    text = """
5137f344-041a-48be-933e-edd7ce34607f steamer: EC2 power-on... cron 25 8 * * 1-5 @ Asia/Taipei
32bf7bac-be39-443d-bf7d-30d2fb496b50 steamer: EC2 archive/... cron 40 13 * * 1-5 @ Asia/Taipei
c2eeb4f3-6a84-4910-ac7a-25938dda18da steamer: EC2 stop gua... cron 46 13 * * 1-5 @ Asia/Taipei
"""
    rows = shadow_lane_preflight.parse_openclaw_cron_list(text)
    assert [row.role for row in rows] == ["ec2_power_on", "archive_upload", "ec2_stop_guardrail"]


def test_classify_kickoff_and_verify() -> None:
    assert shadow_lane_preflight.classify_role("steamer: online sim kickoff (EC2)") == "sim_kickoff"
    assert shadow_lane_preflight.classify_role("steamer: online sim verify+autoheal (EC2)") == "sim_verify_autoheal"
