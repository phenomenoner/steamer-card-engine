from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LINE_STATE_RELATIVE_PATH = Path("StrategyExecuter_Steamer-Antigravity/projects/steamer/research/provenance/state")


def latest_line_state_path(*, workspace_root: Path, line_id: str) -> Path | None:
    root = workspace_root / LINE_STATE_RELATIVE_PATH
    if not root.exists():
        return None
    matches = sorted(root.glob(f"*_{line_id}_line_state.json"))
    if not matches:
        return None
    return matches[-1]


def load_latest_line_state(*, workspace_root: Path, line_id: str) -> dict[str, Any] | None:
    path = latest_line_state_path(workspace_root=workspace_root, line_id=line_id)
    if path is None:
        return None
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    payload.setdefault("_path", str(path))
    return payload
