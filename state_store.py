from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List
from utils import now_utc_iso


def load_json(path: str, default: Any):
    p = Path(path)
    if not p.exists():
        return default
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Corrupt or empty; preserve file by rewriting default later when saved
        return default


def save_json(path: str, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class PostedCache:
    def __init__(self, path: str = "posted.json"):
        self.path = path
        raw = load_json(self.path, default={"items": []})
        # items: list of {"id": str, "tweet_id": str|None, "timestamp": iso}
        self.items: List[Dict[str, Any]] = raw.get("items", [])
        self._ids = {item.get("id") for item in self.items}

    def contains(self, uid: str) -> bool:
        return uid in self._ids

    def add(self, uid: str, tweet_id: str | None) -> None:
        self.items.append({"id": uid, "tweet_id": tweet_id, "timestamp": now_utc_iso()})
        self._ids.add(uid)
        save_json(self.path, {"items": self.items})

    def count_since(self, iso_start: str) -> int:
        from utils import parse_iso
        start = parse_iso(iso_start)
        n = 0
        for item in self.items:
            t = parse_iso(item.get("timestamp", ""))
            if t >= start:
                n += 1
        return n

