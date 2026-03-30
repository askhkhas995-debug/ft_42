from __future__ import annotations

import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "core/catalog/src",
    "core/scheduler/src",
    "core/grading/src",
    "core/storage/src",
    "core/sandbox/src",
    "core/sessions/src",
    "tooling/import_legacy",
):
    sys.path.insert(0, str(ROOT / relative))

from platform_sessions import PiscineSessionService, SUPPORTED_PISCINE_GROUPS  # noqa: E402
from platform_catalog import CatalogService  # noqa: E402
from piscine_import import PiscineDatasetImportService  # noqa: E402


class FakeGradingEngine:
    def __init__(self, outcomes: list[bool]) -> None:
        self.outcomes = list(outcomes)

    def grade_submission(self, context) -> dict:
        passed = self.outcomes.pop(0)
        failure_class = "none" if passed else "wrong_output"
        return {
            "schema_version": 1,
            "report_id": f"report.{context.attempt_id}",
            "attempt_id": context.attempt_id,
            "session_id": context.session_id,
            "user_id": context.user_id,
            "exercise_id": context.exercise_id,
            "variant_id": context.variant_id,
            "pool_id": context.pool_id,
            "mode": context.mode,
            "started_at": "2026-03-07T00:00:01Z",
            "finished_at": "2026-03-07T00:00:02Z",
            "duration_ms": 1000,
            "build_result": {
                "status": "success",
                "compiler": "gcc",
                "command": "",
                "exit_code": 0,
                "stdout_path": "",
                "stderr_path": "",
                "diagnostics": {"errors": 0, "warnings": 0},
            },
            "run_result": {
                "status": "success" if passed else "failure",
                "command": "",
                "exit_code": 0 if passed else 1,
                "signal": "",
                "timed_out": False,
                "memory_limit_hit": False,
                "stdout_path": "",
                "stderr_path": "",
                "trace_path": "",
            },
            "evaluation": {
                "comparator_id": "builtin.comparator.output_diff",
                "passed": passed,
                "raw_score": 1.0 if passed else 0.0,
                "normalized_score": 100.0 if passed else 0.0,
                "pass_policy": "all_tests",
                "failure_class": failure_class,
                "failed_test_ids": [] if passed else ["smoke"],
                "passed_test_ids": ["smoke"] if passed else [],
                "edge_case_summary": {
                    "total": 1,
                    "passed": 1 if passed else 0,
                    "failed": 0 if passed else 1,
                },
            },
            "rubric": {"rubric_id": "rubric.c.default", "items": []},
            "feedback": {
                "summary": "All tests passed." if passed else "Attempt failed.",
                "actionable_next_steps": [],
                "hint_ids": [],
                "concept_gaps": [],
            },
            "artifacts": {
                "workspace_snapshot_path": "",
                "report_path": "",
                "diff_path": "",
                "exported_trace_path": "",
            },
            "analytics": {
                "attempt_number_for_exercise": context.attempt_index_for_exercise,
                "cooldown_seconds_applied": 0,
                "mastery_delta": {"concepts": []},
                "productivity_tags": [],
            },
        }


def _copy_bundle(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _build_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    for track in ("c00", "c01", "c02", "c03", "c04", "c05", "c06"):
        src = ROOT / f"datasets/exercises/piscine/{track}"
        if src.exists():
            _copy_bundle(src, repo / f"datasets/exercises/piscine/{track}")
    for pool in ("c00-foundations", "c01-core", "c02-core", "c03-core", "c04-core", "c05-core", "c06-core"):
        src = ROOT / f"datasets/pools/piscine/{pool}"
        if src.exists():
            _copy_bundle(src, repo / f"datasets/pools/piscine/{pool}")
            
    _copy_bundle(
        ROOT / "core/grading/builtins",
        repo / "core/grading/builtins",
    )
    _copy_bundle(
        ROOT / "core/sandbox/profiles",
        repo / "core/sandbox/profiles",
    )
    (repo / "storage/sessions").mkdir(parents=True, exist_ok=True)
    (repo / "storage/attempts").mkdir(parents=True, exist_ok=True)
    (repo / "runtime/reports").mkdir(parents=True, exist_ok=True)
    return repo


def _submission(root: Path, filename: str) -> Path:
    path = root / filename.replace(".c", "")
    path.mkdir(parents=True, exist_ok=True)
    (path / filename).write_text("void stub(void) {}\n", encoding="utf-8")
    return path


def _build_service(repo: Path, outcomes: list[bool]) -> PiscineSessionService:
    return PiscineSessionService(repo, grading_engine=FakeGradingEngine(outcomes))


def test_start_session_and_select_next_exercise(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    monkeypatch.setattr(PiscineSessionService, "_new_session_id", lambda self, pool_id: "session.piscine.start")
    monkeypatch.setattr(PiscineSessionService, "_now", lambda self: "2026-03-07T00:00:00Z")

    service = _build_service(repo, [True])
    session = service.start_session("piscine.c00.foundations")
    selection = service.select_next("session.piscine.start")

    assert session["session_id"] == "session.piscine.start"
    assert session["mode"] == "piscine"
    assert session["current_assignment"]["exercise_id"] == "piscine.c00.ft_putchar"
    assert selection["exercise_id"] == "piscine.c00.ft_putchar"
    assert session["progress"]["available_exercise_ids"] == ["piscine.c00.ft_putchar"]


def test_progression_after_pass_unlocks_next_exercise(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    monkeypatch.setattr(PiscineSessionService, "_new_session_id", lambda self, pool_id: "session.piscine.progress")
    monkeypatch.setattr(
        PiscineSessionService,
        "_new_attempt_id",
        lambda self, session_id, index: f"attempt.piscine.progress.{index:03d}",
    )
    monkeypatch.setattr(PiscineSessionService, "_now", lambda self: "2026-03-07T00:00:00Z")

    service = _build_service(repo, [True])
    service.start_session("piscine.c00.foundations")
    result = service.submit_submission("session.piscine.progress", _submission(tmp_path, "ft_putchar.c"))
    session = result["session"]

    assert result["passed"] is True
    assert session["state"] == "active"
    assert session["progress"]["completed_exercise_ids"] == ["piscine.c00.ft_putchar"]
    assert session["progress"]["passed_exercise_ids"] == ["piscine.c00.ft_putchar"]
    assert session["progress"]["completed_levels"] == [0]
    assert session["progress"]["highest_unlocked_level"] == 1
    assert session["progress"]["available_exercise_ids"] == ["piscine.c00.ft_print_numbers"]
    assert session["current_assignment"]["exercise_id"] == "piscine.c00.ft_print_numbers"
    assert session["current_assignment"]["status"] == "active"


def test_completion_remains_distinct_from_explicit_finish(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    monkeypatch.setattr(PiscineSessionService, "_new_session_id", lambda self, pool_id: "session.piscine.complete")
    monkeypatch.setattr(
        PiscineSessionService,
        "_new_attempt_id",
        lambda self, session_id, index: f"attempt.piscine.complete.{index:03d}",
    )
    monkeypatch.setattr(PiscineSessionService, "_now", lambda self: "2026-03-07T00:00:00Z")

    service = _build_service(repo, [True, True, True, True])
    service.start_session("piscine.c00.foundations")
    service.submit_submission("session.piscine.complete", _submission(tmp_path, "ft_putchar.c"))
    service.submit_submission("session.piscine.complete", _submission(tmp_path, "ft_print_numbers.c"))
    service.submit_submission("session.piscine.complete", _submission(tmp_path, "ft_countdown.c"))
    result = service.submit_submission("session.piscine.complete", _submission(tmp_path, "ft_putstr.c"))
    completed = result["session"]

    assert completed["state"] == "completed"
    assert completed["current_assignment"] is None
    assert completed["finished_at"] is None
    assert completed["progress"]["finished_at"] == "2026-03-07T00:00:02Z"
    assert completed["progress"]["completion_ratio"] == 1.0

    monkeypatch.setattr(PiscineSessionService, "_now", lambda self: "2026-03-07T00:00:03Z")
    finished = service.finish_session("session.piscine.complete")

    assert finished["state"] == "finished"
    assert finished["finished_at"] == "2026-03-07T00:00:03Z"
    assert finished["progress"]["finished_at"] == "2026-03-07T00:00:02Z"


def test_load_or_start_resumes_existing_session_state(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    monkeypatch.setattr(PiscineSessionService, "_new_session_id", lambda self, pool_id: "session.piscine.resume")
    monkeypatch.setattr(
        PiscineSessionService,
        "_new_attempt_id",
        lambda self, session_id, index: f"attempt.piscine.resume.{index:03d}",
    )
    monkeypatch.setattr(PiscineSessionService, "_now", lambda self: "2026-03-07T00:00:00Z")

    service = _build_service(repo, [True])
    service.start_session("piscine.c00.foundations", user_id="learner.one")
    service.submit_submission("session.piscine.resume", _submission(tmp_path, "ft_putchar.c"))

    persisted = service.load_session("session.piscine.resume")
    persisted["current_assignment"] = None
    service.storage.write_yaml("storage/sessions/session.piscine.resume.yml", persisted)

    resumed = service.load_or_start("piscine.c00.foundations", user_id="learner.one")

    assert resumed["session_id"] == "session.piscine.resume"
    assert resumed["state"] == "active"
    assert resumed["current_assignment"]["exercise_id"] == "piscine.c00.ft_print_numbers"
    assert resumed["progress"]["completed_exercise_ids"] == ["piscine.c00.ft_putchar"]


def test_learning_hooks_and_supported_groups_are_exposed(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = _build_service(repo, [True])

    hooks = service.exercise_learning_hooks("piscine.c00.ft_putchar")

    assert "shell00" in service.supported_groups()
    assert "shell01" in service.supported_groups()
    assert "c13" in service.supported_groups()
    assert service.supported_groups() == SUPPORTED_PISCINE_GROUPS
    assert hooks["visible_edge_cases"][0]["id"] == "printable-character"
    assert hooks["hints"][0]["unlock_after_attempts"] == 1
    assert hooks["observation"]["enabled"] is True


def test_real_grading_progresses_through_imported_c00_pool(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = PiscineSessionService(repo)
    catalog = CatalogService(repo)

    session = service.start_session("piscine.c00.foundations", user_id="real.grader")
    seen: list[str] = []
    while session["state"] == "active":
        exercise_id = session["current_assignment"]["exercise_id"]
        seen.append(exercise_id)
        exercise = catalog.load_exercise(exercise_id)
        result = service.submit_submission(session["session_id"], exercise.reference_dir)
        assert result["passed"] is True
        session = result["session"]

    assert seen == [
        "piscine.c00.ft_putchar",
        "piscine.c00.ft_print_numbers",
        "piscine.c00.ft_countdown",
        "piscine.c00.ft_putstr",
    ]
    assert session["state"] == "completed"

def test_piscine_additional_tracks_dataset_loading(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    catalog = CatalogService(repo)
    exercises = catalog.build_index()
    assert len(exercises) >= 23

def test_piscine_additional_tracks_pool_validation(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    catalog = CatalogService(repo)
    pools = catalog.build_pool_index()
    for pool in ("piscine.c00.foundations", "piscine.c01.core", "piscine.c02.core", "piscine.c03.core", "piscine.c04.core", "piscine.c05.core", "piscine.c06.core"):
        assert pool in pools

def test_piscine_c01_progression(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = PiscineSessionService(repo)
    catalog = CatalogService(repo)
    session = service.start_session("piscine.c01.core", user_id="test.runner")
    seen: list[str] = []
    while session["state"] == "active":
        exercise_id = session["current_assignment"]["exercise_id"]
        seen.append(exercise_id)
        exercise = catalog.load_exercise(exercise_id)
        result = service.submit_submission(session["session_id"], exercise.reference_dir)
        session = result["session"]
    assert seen == ["piscine.c01.ft_strlen", "piscine.c01.ft_strcpy"]
    assert session["state"] == "completed"

def test_piscine_c02_progression(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = PiscineSessionService(repo)
    catalog = CatalogService(repo)
    session = service.start_session("piscine.c02.core", user_id="test.runner")
    seen: list[str] = []
    while session["state"] == "active":
        exercise_id = session["current_assignment"]["exercise_id"]
        seen.append(exercise_id)
        exercise = catalog.load_exercise(exercise_id)
        result = service.submit_submission(session["session_id"], exercise.reference_dir)
        session = result["session"]
    assert seen == ["piscine.c02.ulstr", "piscine.c02.search_and_replace", "piscine.c02.repeat_alpha"]
    assert session["state"] == "completed"

def test_piscine_c03_progression(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = PiscineSessionService(repo)
    catalog = CatalogService(repo)
    session = service.start_session("piscine.c03.core", user_id="test.runner")
    seen: list[str] = []
    while session["state"] == "active":
        exercise_id = session["current_assignment"]["exercise_id"]
        seen.append(exercise_id)
        exercise = catalog.load_exercise(exercise_id)
        result = service.submit_submission(session["session_id"], exercise.reference_dir)
        session = result["session"]
    assert seen == ["piscine.c03.first_word", "piscine.c03.rev_print", "piscine.c03.rotone", "piscine.c03.rot_13"]
    assert session["state"] == "completed"

def test_piscine_c04_progression(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = PiscineSessionService(repo)
    catalog = CatalogService(repo)
    session = service.start_session("piscine.c04.core", user_id="test.runner")
    seen: list[str] = []
    while session["state"] == "active":
        exercise_id = session["current_assignment"]["exercise_id"]
        seen.append(exercise_id)
        exercise = catalog.load_exercise(exercise_id)
        result = service.submit_submission(session["session_id"], exercise.reference_dir)
        session = result["session"]
    assert seen == ["piscine.c04.ft_atoi", "piscine.c04.ft_itoa", "piscine.c04.ft_atoi_base"]
    assert session["state"] == "completed"

def test_piscine_c05_progression(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = PiscineSessionService(repo)
    catalog = CatalogService(repo)
    session = service.start_session("piscine.c05.core", user_id="test.runner")
    seen: list[str] = []
    while session["state"] == "active":
        exercise_id = session["current_assignment"]["exercise_id"]
        seen.append(exercise_id)
        exercise = catalog.load_exercise(exercise_id)
        result = service.submit_submission(session["session_id"], exercise.reference_dir)
        session = result["session"]
    assert seen == ["piscine.c05.is_power_of_2", "piscine.c05.pgcd", "piscine.c05.lcm", "piscine.c05.add_prime_sum"]
    assert session["state"] == "completed"

def test_piscine_c06_progression(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = PiscineSessionService(repo)
    catalog = CatalogService(repo)
    session = service.start_session("piscine.c06.core", user_id="test.runner")
    seen: list[str] = []
    while session["state"] == "active":
        exercise_id = session["current_assignment"]["exercise_id"]
        seen.append(exercise_id)
        exercise = catalog.load_exercise(exercise_id)
        result = service.submit_submission(session["session_id"], exercise.reference_dir)
        session = result["session"]
    assert seen == ["piscine.c06.aff_first_param", "piscine.c06.aff_last_param", "piscine.c06.paramsum"]
    assert session["state"] == "completed"

def test_real_grading_additional_tracks(tmp_path: Path) -> None:
    repo = _build_repo(tmp_path)
    service = PiscineSessionService(repo)
    catalog = CatalogService(repo)
    for pool in ("piscine.c01.core", "piscine.c02.core", "piscine.c03.core", "piscine.c04.core", "piscine.c05.core", "piscine.c06.core"):
        session = service.start_session(pool, user_id="real.grader.add-tracks")
        while session["state"] == "active":
            exercise_id = session["current_assignment"]["exercise_id"]
            exercise = catalog.load_exercise(exercise_id)
            result = service.submit_submission(session["session_id"], exercise.reference_dir)
            assert result["passed"] is True
            session = result["session"]
        assert session["state"] == "completed"



def test_piscine_import_service_additional_tracks(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    platform_root = workspace / "platform"
    for relative in (
        "core/catalog",
        "core/grading",
        "core/sandbox",
        "core/scheduler",
        "core/storage",
        "core/sessions",
    ):
        _copy_bundle(ROOT / relative, platform_root / relative)
    for track in ("c00", "c01", "c02", "c03", "c04", "c05", "c06"):
        src = ROOT / f"datasets/exercises/piscine/{track}"
        if src.exists():
            _copy_bundle(src, platform_root / f"datasets/exercises/piscine/{track}")
    for pool in ("c00-foundations", "c01-core", "c02-core", "c03-core", "c04-core", "c05-core", "c06-core"):
        src = ROOT / f"datasets/pools/piscine/{pool}"
        if src.exists():
            _copy_bundle(src, platform_root / f"datasets/pools/piscine/{pool}")

    for relative in [
        "grademe 42 exam/n/success/ft_print_numbers",
        "grademe 42 exam/n/success/ft_countdown",
        "grademe-main/.subjects/PISCINE_PART/exam_01/2",
        "grademe-main/.subjects/PISCINE_PART/exam_01/4",
        "grademe-main/.subjects/PISCINE_PART/exam_01/5",
        "grademe-main/.subjects/PISCINE_PART/exam_01/6",
        "grademe-main/.subjects/PISCINE_PART/exam_01/7",
        "grademe-main/.subjects/PISCINE_PART/exam_02",
        "grademe-main/.subjects/PISCINE_PART/exam_03",
        "grademe-main/.subjects/PISCINE_PART/exam_04",
    ]:
        if (ROOT.parent / relative).exists():
            _copy_bundle(ROOT.parent / relative, workspace / relative)

    (workspace / "ecosystem/piscine/shell00").mkdir(parents=True, exist_ok=True)
    (workspace / "ecosystem/piscine/shell01").mkdir(parents=True, exist_ok=True)
    (workspace / "ecosystem/piscine/c00").mkdir(parents=True, exist_ok=True)

    service = PiscineDatasetImportService(workspace)
    report = service.build_first_pass(write=True)
    payload = report.to_dict()["summary"]

    assert payload["imported_canonical_exercise_counts"]["c00"] == 4
    assert payload["imported_canonical_exercise_counts"]["c01"] == 2
    assert payload["imported_canonical_exercise_counts"]["c02"] == 3
    assert payload["imported_canonical_exercise_counts"]["c03"] == 4
    assert payload["imported_canonical_exercise_counts"]["c04"] == 3
    assert payload["imported_canonical_exercise_counts"]["c05"] == 4
    assert payload["imported_canonical_exercise_counts"]["c06"] == 3
    assert payload["imported_pool_counts"]["c00"] == 1
    assert payload["imported_pool_counts"]["c01"] == 1
    assert payload["imported_pool_counts"]["c02"] == 1
    assert payload["imported_pool_counts"]["c03"] == 1
    assert payload["imported_pool_counts"]["c04"] == 1
    assert payload["imported_pool_counts"]["c05"] == 1
    assert payload["imported_pool_counts"]["c06"] == 1
    
    assert payload["catalog_valid"] is True
    assert payload["pool_valid"] is True
    assert payload["session_progression_valid"] is True
    assert any(item["identifier"] == "piscine.shell00.foundations" for item in report.missing_or_incomplete)
    assert any("C-only" in gap for gap in report.unresolved_migration_gaps)
    assert (service.repository_root / "datasets/exercises/piscine/c00/ft_print_numbers/exercise.yml").exists()
    assert (service.report_path).exists()
    assert (service.status_path).exists()

