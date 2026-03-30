from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
for relative in (
    "core/catalog/src",
    "core/scheduler/src",
    "core/grading/src",
    "core/storage/src",
    "core/sandbox/src",
    "core/exams/src",
):
    sys.path.insert(0, str(ROOT / relative))

from platform_exams import ExamSessionService  # noqa: E402


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
            "started_at": "2026-03-06T00:00:01Z",
            "finished_at": "2026-03-06T00:00:02Z",
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


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _copy_exam_bundle(temp_root: Path, slug: str) -> None:
    source = ROOT / f"datasets/exercises/exams/exam00/{slug}"
    destination = temp_root / f"datasets/exercises/exams/exam00/{slug}"
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _build_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _copy_exam_bundle(repo, "ft_putchar")
    _copy_exam_bundle(repo, "ft_putstr")
    (repo / "storage/sessions").mkdir(parents=True, exist_ok=True)
    (repo / "storage/attempts").mkdir(parents=True, exist_ok=True)
    (repo / "runtime/reports").mkdir(parents=True, exist_ok=True)
    return repo


def _single_level_pool() -> dict:
    return {
        "schema_version": 1,
        "id": "exams.exam00.single-step",
        "title": "Exam00 Single Step",
        "track": "exams",
        "mode": "exam",
        "description": "Single-level exam pool for lifecycle tests.",
        "selection": {
            "strategy": "ordered",
            "repeat_policy": "allow_review",
            "seed_policy": "deterministic_per_session",
        },
        "timing": {
            "total_time_seconds": 600,
            "per_level_time_seconds": 600,
            "cooldown": {"enabled": True, "seconds": 30, "scope": "pool"},
        },
        "levels": [
            {
                "level": 0,
                "title": "Level 0",
                "min_picks": 1,
                "max_picks": 1,
                "time_limit_seconds": 600,
                "unlock_if": {"all_of": [], "any_of": []},
                "exercise_refs": [
                    {"exercise_id": "exams.exam00.ft_putchar", "variant": "normal", "order": 10}
                ],
            }
        ],
        "metadata": {
            "created_at": "2026-03-06T00:00:00Z",
            "updated_at": "2026-03-06T00:00:00Z",
            "status": "draft",
        },
    }


def _progression_pool() -> dict:
    return {
        "schema_version": 1,
        "id": "exams.exam00.progression",
        "title": "Exam00 Progression",
        "track": "exams",
        "mode": "exam",
        "description": "Two-level exam pool for progression tests.",
        "selection": {
            "strategy": "ordered",
            "repeat_policy": "allow_review",
            "seed_policy": "deterministic_per_session",
        },
        "timing": {
            "total_time_seconds": 1200,
            "per_level_time_seconds": 600,
            "cooldown": {"enabled": True, "seconds": 15, "scope": "level"},
        },
        "levels": [
            {
                "level": 0,
                "title": "Level 0",
                "min_picks": 1,
                "max_picks": 1,
                "time_limit_seconds": 600,
                "unlock_if": {"all_of": [], "any_of": []},
                "exercise_refs": [
                    {"exercise_id": "exams.exam00.ft_putchar", "variant": "normal", "order": 10}
                ],
            },
            {
                "level": 1,
                "title": "Level 1",
                "min_picks": 1,
                "max_picks": 1,
                "time_limit_seconds": 600,
                "unlock_if": {"all_of": [0], "any_of": []},
                "exercise_refs": [
                    {"exercise_id": "exams.exam00.ft_putstr", "variant": "normal", "order": 20}
                ],
            },
        ],
        "metadata": {
            "created_at": "2026-03-06T00:00:00Z",
            "updated_at": "2026-03-06T00:00:00Z",
            "status": "draft",
        },
    }


def _submission(root: Path, filename: str) -> Path:
    path = root / filename.replace(".c", "")
    path.mkdir(parents=True, exist_ok=True)
    (path / filename).write_text("int main(void){return 0;}\n", encoding="utf-8")
    return path


def _build_service(repo: Path, outcomes: list[bool]) -> ExamSessionService:
    return ExamSessionService(repo, grading_engine=FakeGradingEngine(outcomes))


def test_start_session(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    _write_yaml(repo / "datasets/pools/exams/exam00-single-step/pool.yml", _single_level_pool())
    monkeypatch.setattr(ExamSessionService, "_new_session_id", lambda self, pool_id: "session.exam.start")
    monkeypatch.setattr(ExamSessionService, "_now", lambda self: "2026-03-06T00:00:00Z")

    service = _build_service(repo, [True])
    session = service.start_session("exams.exam00.single-step")

    assert session["session_id"] == "session.exam.start"
    assert session["state"] == "active"
    assert session["current_assignment"]["exercise_id"] == "exams.exam00.ft_putchar"
    assert (repo / "storage/sessions/session.exam.start.yml").exists()


def test_submit_submission_persists_attempt_and_report(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    _write_yaml(repo / "datasets/pools/exams/exam00-single-step/pool.yml", _single_level_pool())
    monkeypatch.setattr(ExamSessionService, "_new_session_id", lambda self, pool_id: "session.exam.submit")
    monkeypatch.setattr(ExamSessionService, "_new_attempt_id", lambda self, session_id, index: "attempt.exam.submit.001")
    monkeypatch.setattr(ExamSessionService, "_now", lambda self: "2026-03-06T00:00:00Z")

    service = _build_service(repo, [True])
    service.start_session("exams.exam00.single-step")
    result = service.submit_submission("session.exam.submit", _submission(tmp_path, "ft_putchar.c"))

    assert result["passed"] is True
    attempt_log = repo / "storage/attempts/attempt.exam.submit.001.jsonl"
    report_path = repo / "runtime/reports/report.attempt.exam.submit.001.yml"
    assert attempt_log.exists()
    assert report_path.exists()
    assert len(attempt_log.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_next_level_after_success(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    _write_yaml(repo / "datasets/pools/exams/exam00-progression/pool.yml", _progression_pool())
    monkeypatch.setattr(ExamSessionService, "_new_session_id", lambda self, pool_id: "session.exam.progress")
    monkeypatch.setattr(ExamSessionService, "_new_attempt_id", lambda self, session_id, index: f"attempt.exam.progress.{index:03d}")
    monkeypatch.setattr(ExamSessionService, "_now", lambda self: "2026-03-06T00:00:00Z")

    service = _build_service(repo, [True])
    service.start_session("exams.exam00.progression")
    result = service.submit_submission("session.exam.progress", _submission(tmp_path, "ft_putchar.c"))

    session = result["session"]
    assert session["state"] == "active"
    assert session["current_assignment"]["exercise_id"] == "exams.exam00.ft_putstr"
    assert session["progress"]["current_level"] == 1
    assert session["progress"]["completed_levels"] == [0]


def test_retry_after_failure(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    _write_yaml(repo / "datasets/pools/exams/exam00-progression/pool.yml", _progression_pool())
    monkeypatch.setattr(ExamSessionService, "_new_session_id", lambda self, pool_id: "session.exam.retry")
    monkeypatch.setattr(ExamSessionService, "_new_attempt_id", lambda self, session_id, index: f"attempt.exam.retry.{index:03d}")
    monkeypatch.setattr(ExamSessionService, "_now", lambda self: "2026-03-06T00:00:00Z")

    service = _build_service(repo, [False])
    service.start_session("exams.exam00.progression")
    result = service.submit_submission("session.exam.retry", _submission(tmp_path, "ft_putchar.c"))

    session = result["session"]
    assert session["state"] == "active"
    assert session["current_assignment"]["exercise_id"] == "exams.exam00.ft_putchar"
    assert session["current_assignment"]["failure_count"] == 1
    assert session["current_assignment"]["attempt_count"] == 1
    assert session["progress"]["failed_attempts_total"] == 1


def test_finish_session_after_last_success(tmp_path: Path, monkeypatch) -> None:
    repo = _build_repo(tmp_path)
    _write_yaml(repo / "datasets/pools/exams/exam00-progression/pool.yml", _progression_pool())
    monkeypatch.setattr(ExamSessionService, "_new_session_id", lambda self, pool_id: "session.exam.finish")
    monkeypatch.setattr(ExamSessionService, "_new_attempt_id", lambda self, session_id, index: f"attempt.exam.finish.{index:03d}")
    monkeypatch.setattr(ExamSessionService, "_now", lambda self: "2026-03-06T00:00:00Z")

    service = _build_service(repo, [True, True])
    service.start_session("exams.exam00.progression")
    service.submit_submission("session.exam.finish", _submission(tmp_path, "ft_putchar.c"))
    result = service.submit_submission("session.exam.finish", _submission(tmp_path, "ft_putstr.c"))

    session = result["session"]
    assert session["state"] == "finished"
    assert session["current_assignment"] is None
    assert session["progress"]["finished_at"] == "2026-03-06T00:00:02Z"
