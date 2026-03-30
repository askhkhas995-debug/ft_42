from __future__ import annotations

from pathlib import Path

from platform_progression import ProgressionService


PLATFORM_ROOT = Path(__file__).resolve().parents[1]


def test_progression_snapshot_exposes_exam_readiness() -> None:
    service = ProgressionService(PLATFORM_ROOT)

    snapshot = service.build_snapshot("local.user")

    assert "current_module" in snapshot
    assert any(
        item["node_id"] == "exams.exam00" for item in snapshot["exam_readiness_summary"]
    )
    assert isinstance(snapshot["missing_content_notices"], list)
