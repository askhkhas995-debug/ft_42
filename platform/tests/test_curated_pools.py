from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))
sys.path.insert(0, str(ROOT / "core/catalog/src"))

from import_legacy import (  # noqa: E402
    CuratedExamPoolService,
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


def test_curated_pool_generation_tracks_direct_and_auto_provenance(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_assignment(workspace, "Exam00", "fix_a")
    _add_assignment(workspace, "Exam00", "fix_z")
    _write(workspace / "Exam00/pools/c-piscine-exam-00.yml", _pool_yaml([["fix_a", "fix_z"]]))

    _add_assignment(workspace, "Exam01", "ft_strcat")
    _add_assignment(workspace, "Exam01", "ascii_charcater_v2")
    _write(
        workspace / "Exam01/pools/c-piscine-exam-01.yml",
        _pool_yaml([["ft_strcat", "ascii_character_v2", "missing_assignment"]]),
    )

    LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z").stage_import(write=True)
    LegacyReconciliationService(workspace, generated_at="2026-03-06T00:00:00Z").reconcile_staging(write=True)
    LegacyManualCurationService(workspace, generated_at="2026-03-06T00:00:00Z").curate_manual_overrides(write=True)

    service = CuratedExamPoolService(workspace, generated_at="2026-03-06T00:00:00Z")
    report = service.build_curated_pools(write=True)
    summary = report.to_dict()["summary"]

    assert summary["usable_pool_count"] == 2
    assert summary["provenance_summary"]["imported_directly"] == 3
    assert summary["provenance_summary"]["repaired_automatically"] == 1
    assert summary["unresolved_gap_count"] >= 1
    assert report.validation.ok is True

    catalog = CatalogService(service.curated_validation_root)
    assert sorted(entry.pool_id for entry in catalog.list_pools(track="exams")) == [
        "exams.curated.exam00.v1",
        "exams.curated.exam01.v1",
    ]


def test_curated_pool_generation_tracks_manual_provenance(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)
    _add_assignment(workspace, "Exam02", "shared_target")
    (workspace / "Exam01/subjects").mkdir(parents=True, exist_ok=True)
    (workspace / "Exam01/corrections").mkdir(parents=True, exist_ok=True)
    _write(workspace / "Exam01/pools/c-piscine-exam-01.yml", _pool_yaml([["legacy_shared_target"]]))

    LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z").stage_import(write=True)
    LegacyReconciliationService(workspace, generated_at="2026-03-06T00:00:00Z").reconcile_staging(write=True)

    manual = LegacyManualCurationService(workspace, generated_at="2026-03-06T00:00:00Z")
    manual.manual_overrides_root.mkdir(parents=True, exist_ok=True)
    _write(manual.manual_aliases_path, yaml.safe_dump({"schema_version": 1, "aliases": []}, sort_keys=False))
    _write(
        manual.manual_pool_overrides_path,
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
                        "justification": "Curated manual decision.",
                    }
                ],
            },
            sort_keys=False,
        ),
    )
    manual.curate_manual_overrides(write=True)

    report = CuratedExamPoolService(workspace, generated_at="2026-03-06T00:00:00Z").build_curated_pools(write=True)
    summary = report.to_dict()["summary"]

    assert summary["provenance_summary"]["repaired_manually"] == 1
    curated_pool = next(bundle for bundle in report.curated_pools if bundle.public_exam_name == "exam01")
    assert curated_pool.provenance_entries[0].provenance == "repaired_manually"
