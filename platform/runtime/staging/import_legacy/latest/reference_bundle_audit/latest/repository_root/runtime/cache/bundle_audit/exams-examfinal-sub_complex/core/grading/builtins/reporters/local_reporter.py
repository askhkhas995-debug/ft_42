"""Builtin local YAML report exporter."""

from __future__ import annotations

from pathlib import Path

import yaml


class LocalReporter:
    """Persist grading results to local report storage."""

    plugin_id = "builtin.reporter.local"

    def validate(self, config: dict, exercise_manifest: dict) -> list[str]:
        return []

    def persist(self, report: dict, output_path: Path) -> Path:
        """Write a report to a YAML file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(report, handle, sort_keys=False)
        return output_path
