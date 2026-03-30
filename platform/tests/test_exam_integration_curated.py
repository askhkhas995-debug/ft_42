from __future__ import annotations

import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = WORKSPACE_ROOT / "platform"
for relative in (
    "tooling",
    "core/catalog/src",
    "core/scheduler/src",
    "core/grading/src",
    "core/storage/src",
    "core/sandbox/src",
    "core/exams/src",
):
    sys.path.insert(0, str(PLATFORM_ROOT / relative))

from import_legacy import CuratedExamIntegrationService  # noqa: E402


def test_curated_exam_integration_real_staged_data(tmp_path: Path) -> None:
    service = CuratedExamIntegrationService(WORKSPACE_ROOT)

    report = service.run_exam_integration(
        write=False,
        target_root=tmp_path / "curated_exam_integration_repo",
    )

    assert report.runnable_pool_count == 4
    assert report.runnable_exercise_count == 78
    assert report.total_curated_exercise_count == 78
    assert len(report.pool_results) == 4
    assert all(item.fully_runnable for item in report.pool_results)
    assert all(item.selected_first_assignment for item in report.pool_results)
    assert all(item.failing_submission_verified for item in report.pool_results)
    assert all(item.retry_verified for item in report.pool_results)
    assert all(item.passing_submission_verified for item in report.pool_results)
    assert all(item.next_level_verified for item in report.pool_results)
    assert all(item.finished_session_verified for item in report.pool_results)
    assert [item.pool_id for item in report.pool_results] == [
        "exams.curated.exam00.v1",
        "exams.curated.exam01.v1",
        "exams.curated.exam02.v1",
        "exams.curated.exam_final.v1",
    ]
    assert [item.attempts_total for item in report.pool_results] == [8, 11, 11, 16]

    unresolved_gap_blockers = [item for item in report.remaining_blockers if item["type"] == "unresolved_gap"]
    assert len(unresolved_gap_blockers) == 8
    assert len(report.remaining_blockers) == 8
