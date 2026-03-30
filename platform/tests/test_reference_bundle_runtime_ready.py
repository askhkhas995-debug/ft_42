from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))
sys.path.insert(0, str(ROOT / "core/catalog/src"))
sys.path.insert(0, str(ROOT / "core/scheduler/src"))
sys.path.insert(0, str(ROOT / "core/grading/src"))
sys.path.insert(0, str(ROOT / "core/storage/src"))
sys.path.insert(0, str(ROOT / "core/sandbox/src"))
sys.path.insert(0, str(ROOT / "core/exams/src"))

from import_legacy import ReferenceBundleAuditService, RuntimeReadyRepairService  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_yaml(path: Path, payload: object) -> None:
    _write(path, yaml.safe_dump(payload, sort_keys=False))


def _manifest(
    *,
    exercise_id: str,
    group: str,
    slug: str,
    expected_file: str,
    compile_mode: str,
    origin_path: str,
) -> dict[str, object]:
    headers = ["stdio.h"] if compile_mode == "standalone_program" else []
    return {
        "schema_version": 1,
        "id": exercise_id,
        "slug": slug,
        "title": slug,
        "summary": slug,
        "track": "exams",
        "group": group,
        "source": {
            "kind": "legacy_import",
            "origin_id": exercise_id,
            "origin_path": origin_path,
            "copyright_status": "legacy_migrated",
        },
        "language": "c",
        "difficulty": {"level": 1, "category": "exam"},
        "pedagogy": {
            "modes": ["exam"],
            "concepts": [],
            "skills": [],
            "misconceptions": [],
            "prerequisite_ids": [],
            "followup_ids": [],
            "estimated_minutes": 15,
        },
        "files": {
            "statement": "statement.md",
            "starter_dir": "starter",
            "reference_dir": "reference",
            "tests_dir": "tests",
        },
        "student_contract": {
            "expected_files": [expected_file],
            "allowed_functions": [],
            "forbidden_functions": [],
            "required_headers": headers,
            "output_contract": {"channel": "stdout", "newline_policy": "ignore"},
            "norm": {"enabled": False},
        },
        "build": {
            "compiler": "gcc",
            "standard": "c11",
            "flags": ["-Wall", "-Wextra", "-Werror"],
            "link_flags": [],
            "compile_mode": compile_mode,
            "entry_files": [expected_file],
        },
        "runtime": {
            "argv_policy": "explicit_per_test",
            "stdin_policy": "explicit_per_test",
            "timeout_seconds": 2,
            "memory_limit_mb": 64,
            "file_write_policy": "deny",
            "network_access": False,
        },
        "grading": {
            "strategy": "output_diff",
            "comparator": "builtin.comparator.output_diff",
            "rubric_id": "rubric.c.default",
            "pass_policy": {"mode": "all_tests", "threshold": 1.0},
            "edge_case_suite_id": f"legacy.{exercise_id}",
            "analyzer_ids": ["builtin.analyzer.failure_classifier"],
        },
        "variants": {
            "default": "normal",
            "available": [
                {
                    "id": "normal",
                    "kind": "normal",
                    "starter_dir": "starter",
                    "reference_dir": "reference",
                    "tests_dir": "tests",
                    "description": "test",
                }
            ],
        },
        "metadata": {
            "author": "test",
            "reviewers": [],
            "created_at": "2026-03-07T00:00:00Z",
            "updated_at": "2026-03-07T00:00:00Z",
            "status": "migrated",
        },
    }


def _tests_yml() -> dict[str, object]:
    return {
        "cases": [
            {
                "id": "smoke",
                "argv": [],
                "stdin": "",
                "expected_stdout": None,
                "expected_stderr": "",
                "expected_exit_code": 0,
            }
        ]
    }


def _bundle_root(workspace: Path, group: str, slug: str) -> Path:
    return workspace / "platform/runtime/staging/import_legacy/latest/accepted/datasets/exercises/exams" / group / slug


def _pool_root(workspace: Path) -> Path:
    return workspace / "platform/runtime/staging/import_legacy/latest/curated_pools/v1/datasets/pools/exams/curated-exam00-v1"


def _create_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    (workspace / "platform/runtime/staging/import_legacy/latest/accepted/datasets/exercises/exams").mkdir(parents=True, exist_ok=True)
    (workspace / "platform/runtime/staging/import_legacy/latest/curated_pools/v1/datasets/pools/exams").mkdir(parents=True, exist_ok=True)
    (workspace / "platform/runtime/staging/import_legacy/latest/curated_pools/v1/reports").mkdir(parents=True, exist_ok=True)
    (workspace / "platform").mkdir(parents=True, exist_ok=True)
    (workspace / "platform/core").symlink_to(ROOT / "core", target_is_directory=True)
    return workspace


def _add_bundle(
    workspace: Path,
    *,
    slug: str,
    expected_file: str,
    compile_mode: str,
    reference_files: dict[str, str],
    starter_files: dict[str, str],
    tests_main: str | None,
    origin_path: str,
    origin_generator_name: str = "generator.py",
    origin_main: str | None = None,
) -> None:
    group = "exam00"
    exercise_id = f"exams.{group}.{slug}"
    root = _bundle_root(workspace, group, slug)
    _write_yaml(root / "exercise.yml", _manifest(
        exercise_id=exercise_id,
        group=group,
        slug=slug,
        expected_file=expected_file,
        compile_mode=compile_mode,
        origin_path=origin_path,
    ))
    _write(root / "statement.md", f"# {slug}\n")
    for name, content in starter_files.items():
        _write(root / "starter" / name, content)
    for name, content in reference_files.items():
        _write(root / "reference" / name, content)
    _write_yaml(root / "tests/tests.yml", _tests_yml())
    if tests_main is not None:
        _write(root / "tests/main.c", tests_main)

    origin_root = workspace / origin_path
    _write(origin_root / origin_generator_name, "print('ok')\n")
    if origin_main is not None:
        _write(origin_root / "main.c", origin_main)


def _add_pool(workspace: Path) -> None:
    payload = {
        "schema_version": 1,
        "id": "exams.curated.exam00.v1",
        "title": "Curated EXAM00 v1",
        "track": "exams",
        "mode": "exam",
        "description": "Synthetic runtime-ready test pool.",
        "selection": {
            "strategy": "random",
            "repeat_policy": "avoid_passed",
            "seed_policy": "deterministic_per_session",
        },
        "timing": {
            "total_time_seconds": 3600,
            "per_level_time_seconds": 900,
            "cooldown": {"enabled": False, "seconds": 0, "scope": "pool"},
        },
        "levels": [
            {
                "level": 0,
                "title": "Level 0",
                "min_picks": 1,
                "max_picks": 1,
                "time_limit_seconds": 900,
                "unlock_if": {"all_of": [], "any_of": []},
                "exercise_refs": [{"exercise_id": "exams.exam00.good_start", "variant": "normal", "weight": 1, "order": 1}],
            },
            {
                "level": 1,
                "title": "Level 1",
                "min_picks": 1,
                "max_picks": 1,
                "time_limit_seconds": 900,
                "unlock_if": {"all_of": [0], "any_of": []},
                "exercise_refs": [{"exercise_id": "exams.exam00.fixable_name", "variant": "normal", "weight": 1, "order": 1}],
            },
            {
                "level": 2,
                "title": "Level 2",
                "min_picks": 1,
                "max_picks": 1,
                "time_limit_seconds": 900,
                "unlock_if": {"all_of": [1], "any_of": []},
                "exercise_refs": [{"exercise_id": "exams.exam00.harness_fix", "variant": "normal", "weight": 1, "order": 1}],
            },
            {
                "level": 3,
                "title": "Level 3",
                "min_picks": 1,
                "max_picks": 1,
                "time_limit_seconds": 900,
                "unlock_if": {"all_of": [2], "any_of": []},
                "exercise_refs": [{"exercise_id": "exams.exam00.manual_bad", "variant": "normal", "weight": 1, "order": 1}],
            },
        ],
        "metadata": {
            "created_at": "2026-03-07T00:00:00Z",
            "updated_at": "2026-03-07T00:00:00Z",
            "status": "curated_v1",
        },
    }
    _write_yaml(_pool_root(workspace) / "pool.yml", payload)


def _build_fixture_workspace(tmp_path: Path) -> Path:
    workspace = _create_workspace(tmp_path)
    _add_bundle(
        workspace,
        slug="good_start",
        expected_file="good_start.c",
        compile_mode="standalone_program",
        starter_files={"good_start.c": "int main(void){return 0;}\n"},
        reference_files={"good_start.c": "#include <stdio.h>\nint main(void){printf(\"ok\\n\");return 0;}\n"},
        tests_main=None,
        origin_path="Exam00/corrections/good_start",
    )
    _add_bundle(
        workspace,
        slug="fixable_name",
        expected_file="fixable_name.c",
        compile_mode="standalone_program",
        starter_files={"fixable_alt.c": "int main(void){return 0;}\n"},
        reference_files={"fixable_alt.c": "#include <stdio.h>\nint main(void){printf(\"fixed\\n\");return 0;}\n"},
        tests_main=None,
        origin_path="Exam00/corrections/fixable_name",
        origin_generator_name="genrator.py",
    )
    _add_bundle(
        workspace,
        slug="harness_fix",
        expected_file="harness_fix.c",
        compile_mode="function_with_harness",
        starter_files={"harness_fix.c": "int harness_fix(void){return 0;}\n"},
        reference_files={"harness_fix.c": "int harness_fix(void){return 7;}\n"},
        tests_main=None,
        origin_path="Exam00/corrections/harness_fix",
        origin_main="#include <stdio.h>\nint harness_fix(void);\nint main(void){printf(\"%d\\n\", harness_fix());return 0;}\n",
    )
    _add_bundle(
        workspace,
        slug="manual_bad",
        expected_file="manual_bad.c",
        compile_mode="standalone_program",
        starter_files={"manual_bad.c": "int main(void){return 0;}\n"},
        reference_files={
            "manual_bad.c": "#include <stdio.h>\nint main(int ac, char **av){(void)av;if(ac!=2){printf(\"\\n\");return 1;}printf(\"bad\\n\");return 0;}\n"
        },
        tests_main=None,
        origin_path="Exam00/corrections/manual_bad",
    )
    _add_pool(workspace)
    return workspace


def test_reference_bundle_audit_classifies_bundle_failures(tmp_path: Path) -> None:
    workspace = _build_fixture_workspace(tmp_path)
    report = ReferenceBundleAuditService(workspace).audit_reference_bundles(write=True)
    by_id = {item.exercise_id: item for item in report.results}

    assert by_id["exams.exam00.good_start"].runtime_valid is True
    assert by_id["exams.exam00.fixable_name"].primary_failure_class == "missing_expected_user_file_mapping"
    assert by_id["exams.exam00.fixable_name"].repairability == "auto_repairable"
    assert by_id["exams.exam00.harness_fix"].primary_failure_class == "broken_harness_path"
    assert by_id["exams.exam00.harness_fix"].repairability == "auto_repairable"
    assert by_id["exams.exam00.manual_bad"].primary_failure_class in {"malformed_test_fixture", "runtime_wrong_output"}


def test_safe_repair_application_does_not_mutate_raw_staged_data(tmp_path: Path) -> None:
    workspace = _build_fixture_workspace(tmp_path)
    service = RuntimeReadyRepairService(workspace)
    service.build_runtime_ready_subset(write=True)

    raw_reference = _bundle_root(workspace, "exam00", "fixable_name") / "reference/fixable_name.c"
    repaired_reference = service.runtime_ready_repo_root / "datasets/exercises/exams/exam00/fixable_name/reference/fixable_name.c"
    assert raw_reference.exists() is False
    assert repaired_reference.exists() is True


def test_runtime_ready_output_generation_records_applied_repairs(tmp_path: Path) -> None:
    workspace = _build_fixture_workspace(tmp_path)
    service = RuntimeReadyRepairService(workspace)
    report = service.build_runtime_ready_subset(write=True)

    assert any(item.repair_class == "alternate_filename_normalization" and item.applied for item in report.applied_repairs)
    assert any(item.repair_class == "harness_main_discovery" and item.applied for item in report.applied_repairs)
    assert any(item.repair_class == "generator_filename_typo" and item.applied for item in report.applied_repairs)
    assert any(item.pool_id == "exams.curated.exam00.v1" and item.dropped_levels == [3] for item in report.pool_summaries)


def test_runtime_ready_subset_excludes_unrepaired_bundle(tmp_path: Path) -> None:
    workspace = _build_fixture_workspace(tmp_path)
    service = RuntimeReadyRepairService(workspace)
    service.build_runtime_ready_subset(write=True)
    pool_payload = yaml.safe_load(
        (service.runtime_ready_repo_root / "datasets/pools/exams/curated-exam00-v1/pool.yml").read_text(encoding="utf-8")
    )

    retained_ids = [
        ref["exercise_id"]
        for level in pool_payload["levels"]
        for ref in level["exercise_refs"]
    ]
    assert "exams.exam00.manual_bad" not in retained_ids
    assert retained_ids == [
        "exams.exam00.good_start",
        "exams.exam00.fixable_name",
        "exams.exam00.harness_fix",
    ]


def test_runtime_ready_integration_rerun_uses_repaired_subset(tmp_path: Path) -> None:
    workspace = _build_fixture_workspace(tmp_path)
    service = RuntimeReadyRepairService(workspace)
    repair_report = service.build_runtime_ready_subset(write=True)
    integration_report = service.run_runtime_ready_exam_integration(write=True, repair_report=repair_report)

    assert integration_report.runnable_pool_count == 1
    assert integration_report.runnable_exercise_count == 3
    assert integration_report.total_curated_exercise_count == 3
    assert [item.pool_id for item in integration_report.pool_results] == ["exams.curated.exam00.v1"]
    assert all(item.fully_runnable for item in integration_report.pool_results)
    unrepaired = [item for item in integration_report.remaining_blockers if item["type"] == "unrepaired_bundle"]
    assert len(unrepaired) == 1
    assert unrepaired[0]["exercise_id"] == "exams.exam00.manual_bad"
