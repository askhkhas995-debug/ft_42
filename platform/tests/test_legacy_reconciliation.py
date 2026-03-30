from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))
sys.path.insert(0, str(ROOT / "core/catalog/src"))

from import_legacy import LegacyImportService, LegacyReconciliationService  # noqa: E402
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


def _add_standalone_assignment(workspace: Path, exam_dir: str, assignment: str) -> None:
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


def test_exact_alias_mapping(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_standalone_assignment(workspace, "Exam02", "ascii_charcater_v2")
    _write(workspace / "Exam02/pools/c-piscine-exam-02.yml", _pool_yaml([["ascii_character_v2"]]))

    LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z").stage_import(write=True)
    report = LegacyReconciliationService(workspace, generated_at="2026-03-06T00:00:00Z").reconcile_staging(write=True)

    assert len(report.alias_mappings) == 1
    mapping = report.alias_mappings[0]
    assert mapping.legacy_assignment_name == "ascii_character_v2"
    assert mapping.canonical_exercise_id == "exams.exam02.ascii_charcater_v2"


def test_ambiguous_alias_rejection(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_standalone_assignment(workspace, "Exam00", "fooa")
    _add_standalone_assignment(workspace, "Exam00", "foob")
    _write(workspace / "Exam00/pools/c-piscine-exam-00.yml", _pool_yaml([["fooc"]]))

    LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z").stage_import(write=True)
    report = LegacyReconciliationService(workspace, generated_at="2026-03-06T00:00:00Z").reconcile_staging(write=True)

    assert report.alias_mappings == []
    assert len(report.ambiguous_mappings) == 1
    assert report.ambiguous_mappings[0].legacy_assignment_name == "fooc"
    assert sorted(report.ambiguous_mappings[0].candidate_exercise_ids) == [
        "exams.exam00.fooa",
        "exams.exam00.foob",
    ]


def test_repaired_pool_resolution(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_standalone_assignment(workspace, "Exam02", "ascii_charcater_v2")
    _add_standalone_assignment(workspace, "Exam02", "fix_a")
    _write(
        workspace / "Exam02/pools/c-piscine-exam-02.yml",
        _pool_yaml([["ascii_character_v2"], ["fix_a"]]),
    )

    LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z").stage_import(write=True)
    service = LegacyReconciliationService(workspace, generated_at="2026-03-06T00:00:00Z")
    report = service.reconcile_staging(write=True)

    assert len(report.auto_repaired_references) == 1
    assert len(report.repaired_pools) == 1
    assert report.validation.ok is True
    repaired_pool_path = (
        service.reconciliation_repaired_root / "datasets/pools/exams/c-piscine-exam-02/pool.yml"
    )
    assert repaired_pool_path.exists()
    assert not (
        service.staging_accepted_root / "datasets/pools/exams/c-piscine-exam-02/pool.yml"
    ).exists()

    catalog = CatalogService(service.reconciliation_validation_root)
    assert [entry.pool_id for entry in catalog.list_pools(track="exams")] == ["exams.exam02.c-piscine-exam-02"]


def test_unresolved_reference_reporting(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_standalone_assignment(workspace, "Exam02", "fix_a")
    _write(workspace / "Exam02/pools/c-piscine-exam-02.yml", _pool_yaml([["missing_assignment"]]))

    LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z").stage_import(write=True)
    report = LegacyReconciliationService(workspace, generated_at="2026-03-06T00:00:00Z").reconcile_staging(write=True)

    assert report.alias_mappings == []
    assert report.repaired_pools == []
    assert len(report.unresolved_references_remaining) == 1
    assert report.unresolved_references_remaining[0].assignment == "missing_assignment"
