from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))
sys.path.insert(0, str(ROOT / "core/catalog/src"))

from import_legacy import (  # noqa: E402
    LegacyImportService,
    LegacyManualCurationService,
    LegacyReconciliationService,
)
from platform_catalog import CatalogService  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _profile(*, name: str, user_files: list[str], common_files: list[str] | None = None) -> str:
    payload = {
        "name": name,
        "unit": "c",
        "compile_user": True,
        "white_list": ["write"],
        "user_files": user_files,
        "common_files": common_files or [],
        "tests": {"method": "typical", "count": 3},
        "python3": True,
    }
    return yaml.safe_dump(payload, sort_keys=False)


def _pool_yaml(assignments: list[list[str]]) -> str:
    return yaml.safe_dump(
        {
            "penalty": 0,
            "practice": False,
            "has_trace": True,
            "start_zero": True,
            "incremental_time": True,
            "no_next": True,
            "docs": "c-piscine",
            "levels": [{"assignments": item} for item in assignments],
        },
        sort_keys=False,
    )


def _create_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "platform/datasets/exercises/exams").mkdir(parents=True, exist_ok=True)
    (workspace / "platform/datasets/pools/exams").mkdir(parents=True, exist_ok=True)
    (workspace / "platform/runtime/reports/import_legacy").mkdir(parents=True, exist_ok=True)
    return workspace


def _add_assignment(workspace: Path, exam_dir: str, assignment: str) -> None:
    _write(
        workspace / f"{exam_dir}/subjects/{assignment}/subject.en.txt",
        f"Assignment name  : {assignment}\n\nLegacy exercise {assignment}.\n",
    )
    _write(
        workspace / f"{exam_dir}/corrections/{assignment}/profile.yml",
        _profile(name=assignment, user_files=[f"{assignment}.c"]),
    )
    _write(workspace / f"{exam_dir}/corrections/{assignment}/generator.py", "print('ok')\n")
    _write(
        workspace / f"{exam_dir}/corrections/{assignment}/{assignment}.c",
        "int main(void){return 0;}\n",
    )


def _run_stage_and_reconcile(workspace: Path) -> None:
    LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z").stage_import(write=True)
    LegacyReconciliationService(workspace, generated_at="2026-03-06T00:00:00Z").reconcile_staging(write=True)


def test_exact_manual_override_application(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_assignment(workspace, "Exam00", "expected_task")
    _write(workspace / "Exam00/pools/c-piscine-exam-00.yml", _pool_yaml([["legacy_named_task"]]))

    _run_stage_and_reconcile(workspace)
    service = LegacyManualCurationService(workspace, generated_at="2026-03-06T00:00:00Z")
    service.manual_overrides_root.mkdir(parents=True, exist_ok=True)
    _write(
        service.manual_aliases_path,
        yaml.safe_dump(
            {
                "schema_version": 1,
                "aliases": [
                    {
                        "exam_group": "exam00",
                        "legacy_assignment_name": "legacy_named_task",
                        "canonical_exercise_id": "exams.exam00.expected_task",
                        "justification": "Confirmed by curator from legacy subject naming drift.",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(
        service.manual_pool_overrides_path,
        yaml.safe_dump({"schema_version": 1, "overrides": []}, sort_keys=False),
    )

    report = service.curate_manual_overrides(write=True)

    assert len(report.applied_overrides) == 1
    assert report.applied_overrides[0].override_type == "manual_alias_override"
    assert report.unresolved_references_remaining == []
    assert len(report.repaired_pools) == 1
    repaired_pool = service.manual_repaired_root / "datasets/pools/exams/c-piscine-exam-00/pool.yml"
    assert repaired_pool.exists()
    assert not (service.staging_accepted_root / "datasets/pools/exams/c-piscine-exam-00/pool.yml").exists()
    queue_text = service.manual_review_queue_path.read_text(encoding="utf-8")
    assert "Remaining unresolved cases: 0" in queue_text
    assert "legacy_named_task" not in queue_text


def test_invalid_override_rejection(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_assignment(workspace, "Exam00", "expected_task")
    _write(workspace / "Exam00/pools/c-piscine-exam-00.yml", _pool_yaml([["legacy_named_task"]]))

    _run_stage_and_reconcile(workspace)
    service = LegacyManualCurationService(workspace, generated_at="2026-03-06T00:00:00Z")
    service.manual_overrides_root.mkdir(parents=True, exist_ok=True)
    _write(
        service.manual_aliases_path,
        yaml.safe_dump(
            {
                "schema_version": 1,
                "aliases": [
                    {
                        "exam_group": "exam00",
                        "legacy_assignment_name": "legacy_named_task",
                        "canonical_exercise_id": "exams.exam00.expected_task",
                        "justification": "bad override",
                        "unexpected_key": "boom",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    _write(
        service.manual_pool_overrides_path,
        yaml.safe_dump({"schema_version": 1, "overrides": []}, sort_keys=False),
    )

    with pytest.raises(ValueError, match="unknown keys"):
        service.curate_manual_overrides(write=True)


def test_override_driven_repaired_pool_resolution(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_assignment(workspace, "Exam02", "shared_target")
    (workspace / "Exam01/subjects").mkdir(parents=True, exist_ok=True)
    (workspace / "Exam01/corrections").mkdir(parents=True, exist_ok=True)
    _write(workspace / "Exam01/pools/c-piscine-exam-01.yml", _pool_yaml([["legacy_shared_target"]]))

    _run_stage_and_reconcile(workspace)
    service = LegacyManualCurationService(workspace, generated_at="2026-03-06T00:00:00Z")
    service.manual_overrides_root.mkdir(parents=True, exist_ok=True)
    _write(
        service.manual_aliases_path,
        yaml.safe_dump({"schema_version": 1, "aliases": []}, sort_keys=False),
    )
    _write(
        service.manual_pool_overrides_path,
        yaml.safe_dump(
            {
                "schema_version": 1,
                "overrides": [
                    {
                        "source_id": "Exam01",
                        "pool_name": "c-piscine-exam-01.yml",
                        "level": 0,
                        "legacy_assignment_name": "legacy_shared_target",
                        "canonical_exercise_id": "exams.exam02.shared_target",
                        "justification": "Legacy pool intentionally reused the accepted exam02 exercise.",
                    }
                ],
            },
            sort_keys=False,
        ),
    )

    report = service.curate_manual_overrides(write=True)

    assert len(report.applied_overrides) == 1
    assert report.applied_overrides[0].override_type == "manual_pool_override"
    assert report.unresolved_references_remaining == []
    assert len(report.repaired_pools) == 1
    assert report.validation.ok is True

    catalog = CatalogService(service.manual_validation_root)
    assert [entry.pool_id for entry in catalog.list_pools(track="exams")] == ["exams.exam01.c-piscine-exam-01"]
