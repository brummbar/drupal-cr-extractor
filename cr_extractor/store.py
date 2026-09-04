"""Local cache of change-record nodes: one JSON file per node."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DEFAULT_DATA_DIR = Path("data")


class Store:
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR):
        self.data_dir = Path(data_dir)
        self.records_dir = self.data_dir / "records"
        self.meta_path = self.data_dir / "meta.json"

    def record_path(self, nid: str) -> Path:
        return self.records_dir / f"{nid}.json"

    def is_current(self, node: dict) -> bool:
        """True if the node is cached and its `changed` timestamp is unchanged."""
        path = self.record_path(str(node["nid"]))
        if not path.exists():
            return False
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        return str(cached.get("changed")) == str(node.get("changed"))

    def exists(self, nid: str) -> bool:
        return self.record_path(nid).exists()

    def save(self, node: dict) -> None:
        self.records_dir.mkdir(parents=True, exist_ok=True)
        path = self.record_path(str(node["nid"]))
        path.write_text(json.dumps(node, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    def iter_records(self) -> Iterator[dict]:
        if not self.records_dir.exists():
            return
        for path in sorted(self.records_dir.glob("*.json")):
            yield json.loads(path.read_text(encoding="utf-8"))

    def count(self) -> int:
        return sum(1 for _ in self.records_dir.glob("*.json")) if self.records_dir.exists() else 0

    def read_meta(self) -> dict:
        if self.meta_path.exists():
            return json.loads(self.meta_path.read_text(encoding="utf-8"))
        return {}

    def write_meta(self, **fields) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        meta = self.read_meta()
        meta.update(fields)
        meta["last_fetch"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
