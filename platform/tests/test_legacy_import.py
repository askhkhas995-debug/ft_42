from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tooling"))
sys.path.insert(0, str(ROOT / "core/catalog/src"))

from import_legacy import LegacyImportService  # noqa: E402
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


def test_migrate_valid_function_and_standalone_bundles_and_pools(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    _write(
        workspace / "Exam00/subjects/ft_abs/subject.en.txt",
        """Assignment name  : ft_abs
Expected files   : ft_abs.c
Allowed functions:
Version          : 1
--------------------------------------------------------------------------------

Return the absolute value of the provided integer.
""",
    )
    _write(
        workspace / "Exam00/corrections/ft_abs/profile.yml",
        _profile(name="ft_abs", user_files=["ft_abs.c"], common_files=["main.c"]),
    )
    _write(workspace / "Exam00/corrections/ft_abs/generator.py", "print('ok')\n")
    _write(workspace / "Exam00/corrections/ft_abs/ft_abs.c", "int ft_abs(int n)\n{\n\treturn (n < 0 ? -n : n);\n}\n")
    _write(
        workspace / "Exam00/corrections/ft_abs/main.c",
        "#include <stdio.h>\nint ft_abs(int n);\nint main(void){printf(\"%d\\n\", ft_abs(-2));return 0;}\n",
    )

    _write(
        workspace / "Exam00/subjects/fix_a/subject.en.txt",
        """Assignment name  : fix_a
Expected files   : fix_a.c
Allowed functions:
Version          : 1
--------------------------------------------------------------------------------

Print the character a followed by a newline.
""",
    )
    _write(
        workspace / "Exam00/corrections/fix_a/profile.yml",
        _profile(name="fix_a", user_files=["fix_a.c"]),
    )
    _write(workspace / "Exam00/corrections/fix_a/generator.py", "print('ok')\n")
    _write(
        workspace / "Exam00/corrections/fix_a/fix_a.c",
        "#include <unistd.h>\nint main(void){write(1,\"a\\n\",2);return 0;}\n",
    )

    _write(
        workspace / "Exam00/pools/c-piscine-exam-00.yml",
        _pool_yaml([["fix_a"], ["ft_abs"]]),
    )

    service = LegacyImportService(workspace, source_order=("Exam00",), generated_at="2026-03-06T00:00:00Z")
    report = service.migrate(write=True)

    assert report.to_dict()["summary"]["error_count"] == 0
    assert service.report_path.exists()

    catalog = CatalogService(workspace / "platform")
    exercises = {entry.exercise_id: entry for entry in catalog.list_exercises(track="exams")}
    pools = {entry.pool_id: entry for entry in catalog.list_pools(track="exams")}

    assert set(exercises) == {"exams.exam00.ft_abs", "exams.exam00.fix_a"}
    assert set(pools) == {"exams.exam00.c-piscine-exam-00"}

    ft_abs = catalog.load_exercise("exams.exam00.ft_abs")
    fix_a = catalog.load_exercise("exams.exam00.fix_a")
    pool = catalog.load_pool("exams.exam00.c-piscine-exam-00")

    assert ft_abs.manifest["build"]["compile_mode"] == "function_with_harness"
    assert ft_abs.harness_path is not None
    assert fix_a.manifest["build"]["compile_mode"] == "standalone_program"
    assert fix_a.harness_path is None
    assert pool.levels[0].exercise_refs[0].exercise_id == "exams.exam00.fix_a"
    assert pool.levels[1].exercise_refs[0].exercise_id == "exams.exam00.ft_abs"


def test_migration_reports_naming_mismatch_and_bad_pool_reference(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    _write(
        workspace / "Exam01/subjects/lonely_subject/subject.en.txt",
        "Assignment name  : lonely_subject\n\nOnly a subject exists here.\n",
    )
    _write(
        workspace / "Exam01/corrections/lonely_correction/profile.yml",
        _profile(name="lonely_correction", user_files=["lonely_correction.c"]),
    )
    _write(workspace / "Exam01/corrections/lonely_correction/generator.py", "print('ok')\n")
    _write(workspace / "Exam01/corrections/lonely_correction/lonely_correction.c", "int main(void){return 0;}\n")
    _write(workspace / "Exam01/pools/c-piscine-exam-01.yml", _pool_yaml([["missing_assignment"]]))

    service = LegacyImportService(workspace, source_order=("Exam01",), generated_at="2026-03-06T00:00:00Z")
    report = service.migrate(write=True)

    issues = {(issue.code, issue.assignment) for issue in report.issues}
    assert ("naming_mismatch", "lonely_subject") in issues
    assert ("naming_mismatch", "lonely_correction") in issues
    assert ("bad_pool_reference", "missing_assignment") in issues

    catalog = CatalogService(workspace / "platform")
    assert catalog.list_exercises(track="exams") == []
    assert catalog.list_pools(track="exams") == []


def test_migration_reports_malformed_generator_and_correction_bundle(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    _write(
        workspace / "Exam02/subjects/bad_generator/subject.en.txt",
        "Assignment name  : bad_generator\n\nBad generator fixture.\n",
    )
    _write(
        workspace / "Exam02/corrections/bad_generator/profile.yml",
        _profile(name="bad_generator", user_files=["bad_generator.c"]),
    )
    _write(workspace / "Exam02/corrections/bad_generator/generator.py", "def broken(:\n")
    _write(workspace / "Exam02/corrections/bad_generator/bad_generator.c", "int main(void){return 0;}\n")

    _write(
        workspace / "Exam02/subjects/missing_user_file/subject.en.txt",
        "Assignment name  : missing_user_file\n\nMissing file fixture.\n",
    )
    _write(
        workspace / "Exam02/corrections/missing_user_file/profile.yml",
        _profile(name="missing_user_file", user_files=["missing_user_file.c"]),
    )
    _write(workspace / "Exam02/corrections/missing_user_file/generator.py", "print('ok')\n")

    service = LegacyImportService(workspace, source_order=("Exam02",), generated_at="2026-03-06T00:00:00Z")
    report = service.migrate(write=True)

    codes = [issue.code for issue in report.issues]
    assert "malformed_generator" in codes
    assert "malformed_correction_bundle" in codes
    assert "missing_file" in codes

    catalog = CatalogService(workspace / "platform")
    assert catalog.list_exercises(track="exams") == []


def test_stage_import_normalizes_common_legacy_filename_defects(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    _write(
        workspace / "Exam01/subjects/prev_charcter/subject.en.txt",
        "Assignment name  : prev_character\n\nReturn the previous character.\n",
    )
    _write(
        workspace / "Exam01/corrections/prev_charcter/profile.yml",
        _profile(name="prev_character", user_files=["prev_character.c"]),
    )
    _write(workspace / "Exam01/corrections/prev_charcter/generator.py", "print('ok')\n")
    _write(workspace / "Exam01/corrections/prev_charcter/prev_character.c", "char prev_character(char c){return c - 1;}\n")
    _write(
        workspace / "Exam01/corrections/prev_charcter/main.c",
        "#include <stdio.h>\nchar prev_character(char c);\nint main(void){printf(\"%c\\n\", prev_character('b'));return 0;}\n",
    )

    _write(
        workspace / "Exam02/subjects/binary_to_decimal/subject.en.txt",
        "Assignment name  : binary_to_decimal\n\nConvert binary text to decimal.\n",
    )
    _write(
        workspace / "Exam02/corrections/binary_to_decimal/profile.yml",
        _profile(name="binary_to_decimal", user_files=["binary_to_decimal.c"]),
    )
    _write(workspace / "Exam02/corrections/binary_to_decimal/genrator.py", "print('ok')\n")
    _write(
        workspace / "Exam02/corrections/binary_to_decimal/binary_to_decimal.c",
        "#include <stdio.h>\nint main(void){printf(\"2\\n\");return 0;}\n",
    )

    _write(
        workspace / "ExamFinal/subjects/add_complex/add_complex.en.txt",
        "Assignment name  : add_complex\n\nAdd two complex numbers.\n",
    )
    _write(
        workspace / "ExamFinal/corrections/add_complex/profile.yml",
        _profile(name="add_complex", user_files=["add_complex.c"]),
    )
    _write(workspace / "ExamFinal/corrections/add_complex/generator.py", "print('ok')\n")
    _write(
        workspace / "ExamFinal/corrections/add_complex/add_complex.c",
        "#include <stdio.h>\nint main(void){printf(\"ok\\n\");return 0;}\n",
    )

    _write(
        workspace / "ExamFinal/subjects/sub_complex/subject.en.txt",
        "Assignment name  : sub_complex\n\nSubtract two complex numbers.\n",
    )
    _write(
        workspace / "ExamFinal/corrections/sub_complex/profile.yml",
        _profile(name="sum_complex", user_files=["sum_complex.c"]),
    )
    _write(workspace / "ExamFinal/corrections/sub_complex/generator.py", "print('ok')\n")
    _write(
        workspace / "ExamFinal/corrections/sub_complex/sub_complex.c",
        "#include <stdio.h>\nint main(void){printf(\"ok\\n\");return 0;}\n",
    )

    service = LegacyImportService(workspace, source_order=("Exam01", "Exam02", "ExamFinal"), generated_at="2026-03-06T00:00:00Z")
    report = service.stage_import(write=True)

    summary = report.to_dict()["summary"]
    assert summary["accepted_exercise_count"] == 4
    assert summary["blocking_error_count"] == 0

    catalog = CatalogService(service.staging_accepted_root)
    exercises = {entry.exercise_id: entry for entry in catalog.list_exercises(track="exams")}

    assert set(exercises) == {
        "exams.exam01.prev_charcter",
        "exams.exam02.binary_to_decimal",
        "exams.examfinal.add_complex",
        "exams.examfinal.sub_complex",
    }

    prev_character = catalog.load_exercise("exams.exam01.prev_charcter")
    assert prev_character.manifest["build"]["compile_mode"] == "function_with_harness"
    assert prev_character.manifest["student_contract"]["expected_files"] == ["prev_character.c"]

    sub_complex = catalog.load_exercise("exams.examfinal.sub_complex")
    assert sub_complex.manifest["student_contract"]["expected_files"] == ["sub_complex.c"]


def test_duplicate_sources_report_conflict_and_keep_first_source(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    for base, text in (
        ("ExamPoolRevanced-main/Exam00", "Imported from the preferred source.\n"),
        ("Exam00", "Imported from the lower-priority source.\n"),
    ):
        _write(
            workspace / f"{base}/subjects/fix_a/subject.en.txt",
            f"Assignment name  : fix_a\n\n{text}",
        )
        _write(
            workspace / f"{base}/corrections/fix_a/profile.yml",
            _profile(name="fix_a", user_files=["fix_a.c"]),
        )
        _write(workspace / f"{base}/corrections/fix_a/generator.py", "print('ok')\n")
        _write(workspace / f"{base}/corrections/fix_a/fix_a.c", "int main(void){return 0;}\n")

    service = LegacyImportService(
        workspace,
        source_order=("ExamPoolRevanced-main", "Exam00"),
        generated_at="2026-03-06T00:00:00Z",
    )
    report = service.migrate(write=True)

    assert any(issue.code == "duplicate_source_conflict" for issue in report.issues)

    catalog = CatalogService(workspace / "platform")
    exercise = catalog.load_exercise("exams.exam00.fix_a")
    assert exercise.manifest["source"]["origin_path"].startswith("ExamPoolRevanced-main/Exam00/")


def test_stage_import_writes_staging_reports_and_validates_accepted_content(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    for base in ("Exam00", "ExamPoolRevanced-main/Exam00"):
        _write(
            workspace / f"{base}/subjects/fix_a/subject.en.txt",
            "Assignment name  : fix_a\n\nPrint the character a followed by a newline.\n",
        )
        _write(
            workspace / f"{base}/corrections/fix_a/profile.yml",
            _profile(name="fix_a", user_files=["fix_a.c"]),
        )
        _write(workspace / f"{base}/corrections/fix_a/generator.py", "print('ok')\n")
        _write(
            workspace / f"{base}/corrections/fix_a/fix_a.c",
            "#include <unistd.h>\nint main(void){write(1,\"a\\n\",2);return 0;}\n",
        )

    _write(workspace / "Exam00/pools/exam00-valid.yml", _pool_yaml([["fix_a"]]))
    _write(workspace / "Exam00/pools/exam00-bad.yml", _pool_yaml([["missing_assignment"]]))

    service = LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z")
    report = service.stage_import(write=True)
    summary = report.to_dict()["summary"]

    assert summary["accepted_exercise_count"] == 1
    assert summary["accepted_pool_count"] == 1
    assert summary["rejected_count"] >= 1
    assert summary["duplicate_count"] == 1
    assert summary["unresolved_reference_count"] == 1
    assert summary["validation_ok"] is True

    accepted_exercise = service.staging_accepted_root / "datasets/exercises/exams/exam00/fix_a/exercise.yml"
    accepted_pool = service.staging_accepted_root / "datasets/pools/exams/exam00-valid/pool.yml"
    rejected_pool = service.staging_rejected_root / "pools/exam00/exam00-bad.yml"
    duplicate_report = service.staging_reports_root / "duplicate_sources.latest.yml"
    unresolved_report = service.staging_reports_root / "unresolved_references.latest.yml"

    assert accepted_exercise.exists()
    assert accepted_pool.exists()
    assert rejected_pool.exists()
    assert duplicate_report.exists()
    assert unresolved_report.exists()
    assert service.staging_report_path.exists()
    assert service.staging_status_path.exists()

    catalog = CatalogService(service.staging_accepted_root)
    assert [entry.exercise_id for entry in catalog.list_exercises(track="exams")] == ["exams.exam00.fix_a"]
    assert [entry.pool_id for entry in catalog.list_pools(track="exams")] == ["exams.exam00.exam00-valid"]


def test_stage_import_reports_conflicting_duplicate_without_merging(tmp_path: Path) -> None:
    workspace = _create_workspace(tmp_path)

    _write(
        workspace / "Exam00/subjects/fix_a/subject.en.txt",
        "Assignment name  : fix_a\n\nPreferred direct source.\n",
    )
    _write(
        workspace / "Exam00/corrections/fix_a/profile.yml",
        _profile(name="fix_a", user_files=["fix_a.c"]),
    )
    _write(workspace / "Exam00/corrections/fix_a/generator.py", "print('ok')\n")
    _write(workspace / "Exam00/corrections/fix_a/fix_a.c", "int main(void){return 0;}\n")

    _write(
        workspace / "ExamPoolRevanced-main/Exam00/subjects/fix_a/subject.en.txt",
        "Assignment name  : fix_a\n\nConflicting alias source.\n",
    )
    _write(
        workspace / "ExamPoolRevanced-main/Exam00/corrections/fix_a/profile.yml",
        _profile(name="fix_a", user_files=["fix_a.c"]),
    )
    _write(workspace / "ExamPoolRevanced-main/Exam00/corrections/fix_a/generator.py", "print('ok')\n")
    _write(workspace / "ExamPoolRevanced-main/Exam00/corrections/fix_a/fix_a.c", "int main(void){return 42;}\n")

    service = LegacyImportService(workspace, generated_at="2026-03-06T00:00:00Z")
    report = service.stage_import(write=True)
    summary = report.to_dict()["summary"]

    assert summary["accepted_exercise_count"] == 1
    assert summary["duplicate_count"] == 1
    assert summary["blocking_error_count"] == 1
    assert any(issue.code == "duplicate_source_conflict" for issue in report.duplicate_sources)

    rejected_exercise = service.staging_rejected_root / "exercises/exam00/fix_a.yml"
    assert rejected_exercise.exists()
    payload = yaml.safe_load(rejected_exercise.read_text(encoding="utf-8"))
    assert "duplicate_source_conflict" in payload["reasons"]

    catalog = CatalogService(service.staging_accepted_root)
    exercise = catalog.load_exercise("exams.exam00.fix_a")
    assert exercise.manifest["source"]["origin_path"].startswith("Exam00/")
