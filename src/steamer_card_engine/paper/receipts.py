from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(payload: object) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def stable_hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def with_receipt_hash(receipt: dict[str, Any]) -> dict[str, Any]:
    enriched = json.loads(json.dumps(receipt))
    hashes = enriched.setdefault("hashes", {})
    hashes["receipt_hash"] = stable_hash({**enriched, "hashes": {**hashes, "receipt_hash": None}})
    return enriched
