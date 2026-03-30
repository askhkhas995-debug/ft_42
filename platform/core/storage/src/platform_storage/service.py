"""Storage service for local YAML, text, and JSONL artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import yaml


@dataclass(slots=True)
class StorageService:
    """Read and write local storage artifacts."""

    root: Path

    def resolve(self, relative_path: str) -> Path:
        """Resolve a storage-relative path."""
        return self.root / relative_path

    def ensure_parent(self, relative_path: str) -> Path:
        """Ensure the parent directory exists and return the full path."""
        path = self.resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def read_yaml(self, relative_path: str) -> dict:
        """Read a YAML file from storage or runtime."""
        path = self.resolve(relative_path)
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def write_yaml(self, relative_path: str, payload: dict) -> Path:
        """Write a YAML file preserving key order."""
        path = self.ensure_parent(relative_path)
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)
        return path

    def read_text(self, relative_path: str) -> str:
        """Read a UTF-8 text file."""
        path = self.resolve(relative_path)
        return path.read_text(encoding="utf-8")

    def write_text(self, relative_path: str, content: str) -> Path:
        """Write a UTF-8 text file."""
        path = self.ensure_parent(relative_path)
        path.write_text(content, encoding="utf-8")
        return path

    def read_jsonl(self, relative_path: str) -> list[dict]:
        """Read JSONL records."""
        path = self.resolve(relative_path)
        records: list[dict] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records

    def append_jsonl(self, relative_path: str, payload: dict) -> Path:
        """Append one JSONL record."""
        path = self.ensure_parent(relative_path)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=False) + "\n")
        return path
