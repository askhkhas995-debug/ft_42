"""CLI entrypoints for the local-first platform."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import uuid

import yaml

from platform_catalog import CatalogService
from platform_curriculum import CurriculumService
from platform_exams import ExamSessionService
from platform_progression import ProgressionService
from platform_scheduler import SchedulerService


SESSION_FILE_NAME = ".nexus42-session.yml"


def _platform_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _now() -> str:
    from datetime import datetime, timezone

    return (
        datetime.now(tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _new_cli_session_id() -> str:
    return f"cli.{uuid.uuid4().hex[:8]}"


def _workspace_session_path(workspace_root: Path) -> Path:
    return workspace_root / SESSION_FILE_NAME


def _default_workspace_root(
    platform_root: Path, exercise_id: str, session_id: str
) -> Path:
    slug = exercise_id.split(".")[-1]
    return (
        platform_root
        / "runtime/manual_submissions"
        / f"{slug}-{session_id.replace('.', '-')}"
    )


def _copy_catalog_files(files, destination_root: Path) -> None:
    for item in files:
        destination = destination_root / item.relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.absolute_path, destination)


def _remove_expected_files(workspace_root: Path, expected_files: list[str]) -> None:
    for file_name in expected_files:
        path = workspace_root / file_name
        if path.exists():
            path.unlink()


def _sync_workspace_for_exercise(exercise, workspace_root: Path) -> Path:
    workspace_root.mkdir(parents=True, exist_ok=True)
    statement_destination = workspace_root / "statement.md"
    shutil.copy2(exercise.statement_path, statement_destination)
    _copy_catalog_files(exercise.starter_files, workspace_root)
    return statement_destination


def _write_workspace_session(workspace_root: Path, payload: dict[str, object]) -> None:
    _workspace_session_path(workspace_root).write_text(
        yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
    )


def _load_workspace_session(workspace_root: Path) -> dict[str, object]:
    session_path = _workspace_session_path(workspace_root)
    if not session_path.exists():
        raise FileNotFoundError(f"Workspace session file not found: {session_path}")
    return yaml.safe_load(session_path.read_text(encoding="utf-8")) or {}


def _new_workspace_payload(
    *,
    platform_root: Path,
    workspace_root: Path,
    session_id: str,
    mode: str,
    user_id: str,
    exercise_id: str,
    variant_id: str,
    expected_files: list[str],
    statement_path: Path,
    pool_id: str | None = None,
    level: int | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "session_id": session_id,
        "mode": mode,
        "user_id": user_id,
        "pool_id": pool_id,
        "exercise_id": exercise_id,
        "variant_id": variant_id,
        "level": level,
        "platform_root": str(platform_root),
        "workspace_root": str(workspace_root),
        "statement_path": str(statement_path),
        "expected_files": list(expected_files),
        "submission_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
        "last_report_id": None,
        "last_result": None,
    }


def _prepare_practice_workspace(
    exercise,
    workspace_root: Path,
    platform_root: Path,
    *,
    session_id: str,
    user_id: str = "local.user",
) -> dict[str, object]:
    session_path = _workspace_session_path(workspace_root)
    if session_path.exists():
        raise FileExistsError(
            f"Workspace already contains a session file: {session_path}"
        )
    conflicts = [
        name for name in exercise.expected_files if (workspace_root / name).exists()
    ]
    if conflicts:
        raise FileExistsError(
            f"Workspace already contains expected submission files: {', '.join(conflicts)}"
        )
    statement_destination = _sync_workspace_for_exercise(exercise, workspace_root)
    payload = _new_workspace_payload(
        platform_root=platform_root,
        workspace_root=workspace_root,
        session_id=session_id,
        mode="practice",
        user_id=user_id,
        exercise_id=exercise.exercise_id,
        variant_id="normal",
        expected_files=exercise.expected_files,
        statement_path=statement_destination,
    )
    _write_workspace_session(workspace_root, payload)
    return payload


def _render_yaml(payload: object) -> None:
    print(yaml.safe_dump(payload, sort_keys=False).rstrip())


def _print_lines(lines: list[str]) -> None:
    print("\n".join(lines))


def _exercise_payload(entry) -> dict[str, object]:
    return {
        "exercise_id": entry.exercise_id,
        "track": entry.track,
        "group": entry.group,
        "slug": entry.slug,
        "title": entry.title,
        "language": entry.language,
        "difficulty_level": entry.difficulty_level,
    }


def _pool_payload(entry) -> dict[str, object]:
    return {
        "pool_id": entry.pool_id,
        "track": entry.track,
        "slug": entry.slug,
        "title": entry.title,
        "mode": entry.mode,
    }


def _pool_dataset_payload(pool) -> dict[str, object]:
    return {
        "pool_id": pool.pool_id,
        "track": pool.entry.track,
        "title": pool.entry.title,
        "mode": pool.entry.mode,
        "selection": {
            "strategy": pool.selection.strategy,
            "repeat_policy": pool.selection.repeat_policy,
            "recent_window": pool.selection.recent_window,
            "seed_policy": pool.selection.seed_policy,
        },
        "timing": {
            "total_time_seconds": pool.timing.total_time_seconds,
            "per_level_time_seconds": pool.timing.per_level_time_seconds,
            "cooldown": {
                "enabled": pool.timing.cooldown_enabled,
                "seconds": pool.timing.cooldown_seconds,
                "scope": pool.timing.cooldown_scope,
            },
        },
        "levels": [
            {
                "level": level.level,
                "title": level.title,
                "min_picks": level.min_picks,
                "max_picks": level.max_picks,
                "time_limit_seconds": level.time_limit_seconds,
                "unlock_if": {
                    "all_of": level.unlock_if.all_of,
                    "any_of": level.unlock_if.any_of,
                },
                "exercise_refs": [
                    {
                        "exercise_id": ref.exercise_id,
                        "variant_id": ref.variant_id,
                        "weight": ref.weight,
                        "order": ref.order,
                    }
                    for ref in level.exercise_refs
                ],
            }
            for level in pool.levels
        ],
    }


def _candidate_payload(candidate) -> dict[str, object]:
    return {
        "exercise_id": candidate.exercise_id,
        "variant_id": candidate.variant_id,
        "level": candidate.level,
        "title": candidate.title,
        "weight": candidate.weight,
        "order": candidate.order,
        "declaration_index": candidate.declaration_index,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grademe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("home", help="Show the learner home view.")
    subparsers.add_parser("curriculum", help="Browse the curriculum tree.")

    module = subparsers.add_parser("module", help="Inspect curriculum modules.")
    module_subparsers = module.add_subparsers(dest="module_command", required=True)
    module_show = module_subparsers.add_parser("show", help="Show one curriculum node.")
    module_show.add_argument("node_id", help="Curriculum node id.")

    exercise = subparsers.add_parser("exercise", help="Exercise workspace actions.")
    exercise_subparsers = exercise.add_subparsers(
        dest="exercise_command", required=True
    )
    exercise_start = exercise_subparsers.add_parser(
        "start", help="Prepare one exercise workspace."
    )
    exercise_start.add_argument("exercise_id", help="Canonical exercise id to prepare.")
    exercise_start.add_argument(
        "--workspace", help="Optional target workspace directory."
    )

    progress = subparsers.add_parser("progress", help="Show learner progress summary.")
    progress.add_argument("--user-id", default="local.user", help="Learner id.")

    history = subparsers.add_parser(
        "history", help="Show learner attempt and report history."
    )
    history.add_argument("--user-id", default="local.user", help="Learner id.")
    history.add_argument(
        "--limit", type=int, default=10, help="Maximum recent items to show."
    )
    examples = subparsers.add_parser(
        "examples", help="Print copy/paste command examples."
    )
    examples.add_argument(
        "--workspace-root",
        default="/tmp/nexus42-examples",
        help="Root folder used to render example workspace paths.",
    )

    exam = subparsers.add_parser("exam", help="Exam simulation commands.")
    exam_subparsers = exam.add_subparsers(dest="exam_command", required=True)
    exam_start = exam_subparsers.add_parser(
        "start", help="Start an exam session and prepare a workspace."
    )
    exam_start.add_argument(
        "--pool-id", default="exams.exam00.starter", help="Canonical exam pool id."
    )
    exam_start.add_argument("--workspace", help="Optional target workspace directory.")
    exam_start.add_argument("--user-id", default="local.user", help="Learner id.")
    exam_submit = exam_subparsers.add_parser(
        "submit", help="Submit the active exam workspace."
    )
    exam_submit.add_argument(
        "workspace", nargs="?", default=".", help="Exam workspace directory."
    )
    exam_shell = exam_subparsers.add_parser(
        "shell", help="Show a local 42-style exam workspace helper."
    )
    exam_shell.add_argument(
        "workspace", nargs="?", default=".", help="Exam workspace directory."
    )

    list_exercises = subparsers.add_parser(
        "list-exercises", help="List canonical exercise bundles."
    )
    list_exercises.add_argument("--track", help="Optional track filter.")

    list_pools = subparsers.add_parser(
        "list-pools", help="List canonical pool bundles."
    )
    list_pools.add_argument("--track", help="Optional track filter.")

    show_pool = subparsers.add_parser(
        "show-pool", help="Show a validated pool dataset."
    )
    show_pool.add_argument("pool_id", help="Canonical pool identifier.")

    resolve_candidates = subparsers.add_parser(
        "resolve-candidates",
        help="Resolve eligible candidate exercises for a pool and session.",
    )
    resolve_candidates.add_argument("pool_id", help="Canonical pool identifier.")
    resolve_candidates.add_argument(
        "--session-id", default="manual.session", help="Session identifier to inspect."
    )
    resolve_candidates.add_argument(
        "--level", type=int, help="Optional explicit pool level."
    )

    select_next = subparsers.add_parser(
        "select-next", help="Select the next exercise for a pool session."
    )
    select_next.add_argument("pool_id", help="Canonical pool identifier.")
    select_next.add_argument(
        "--session-id", required=True, help="Session identifier to advance."
    )

    start = subparsers.add_parser("start", help="Prepare one local exercise workspace.")
    start.add_argument(
        "--exercise-id",
        default="exams.exam00.ft_putchar",
        help="Canonical exercise id to prepare.",
    )
    start.add_argument("--workspace", help="Optional target workspace directory.")

    submit = subparsers.add_parser(
        "submit", help="Grade a prepared local exercise workspace."
    )
    submit.add_argument(
        "workspace",
        nargs="?",
        default=".",
        help="Workspace directory created by the start command.",
    )

    grade_attempt = subparsers.add_parser(
        "grade-attempt", help="Grade an attempt record from storage/attempts."
    )
    grade_attempt.add_argument(
        "attempt_id", help="Attempt identifier, e.g. attempt.example"
    )

    grade_submission = subparsers.add_parser(
        "grade-submission", help="Grade a submission directory directly."
    )
    grade_submission.add_argument(
        "--exercise-id", required=True, help="Canonical exercise id."
    )
    grade_submission.add_argument(
        "--submission",
        required=True,
        help="Submission directory containing expected files.",
    )
    grade_submission.add_argument(
        "--attempt-id", default="manual.attempt", help="Attempt identifier to use."
    )
    grade_submission.add_argument(
        "--session-id", default="manual.session", help="Session identifier to use."
    )
    grade_submission.add_argument(
        "--user-id", default="local.user", help="User identifier to use."
    )
    grade_submission.add_argument(
        "--mode", default="practice", help="Mode label for the report."
    )
    grade_submission.add_argument(
        "--variant-id", default="normal", help="Exercise variant id."
    )
    grade_submission.add_argument("--pool-id", default="", help="Optional pool id.")
    return parser


def _render_home(
    curriculum: CurriculumService,
    progression: ProgressionService,
    user_id: str = "local.user",
) -> None:
    snapshot = progression.build_snapshot(user_id)
    current = snapshot.get("current_module") or {}
    lines = [
        "Nexus42 Home",
        "===========",
        f"Current module: {current.get('title', 'none')} ({current.get('id', 'n/a')})",
        f"Completed nodes: {len(snapshot['completed_nodes'])}",
        f"Active sessions: {len(snapshot['active_sessions'])}",
        "",
        "Unlocked next steps:",
    ]
    if snapshot["unlocked_next_nodes"]:
        for node in snapshot["unlocked_next_nodes"]:
            lines.append(f"- {node['id']} [{node['status']}] {node['title']}")
    else:
        lines.append("- none")
    lines.extend(["", "Exam readiness:"])
    for item in snapshot["exam_readiness_summary"]:
        verdict = "ready" if item["ready"] else "blocked"
        lines.append(f"- {item['node_id']}: {verdict}")
    lines.extend(["", "Canonical source of truth:"])
    for key, value in curriculum.source_of_truth_summary().items():
        lines.append(f"- {key}: {value}")
    _print_lines(lines)


def _render_curriculum(curriculum: CurriculumService) -> None:
    grouped = curriculum.grouped_nodes()
    lines = ["Curriculum", "=========="]
    for label in ("piscine", "rushes", "exams"):
        lines.extend(["", label.title()])
        for node in grouped[label]:
            lines.append(
                f"- {node.node_id} | {node.status} | {node.grading_mode} | {node.title}"
            )
    _print_lines(lines)


def _render_module(curriculum: CurriculumService, node_id: str) -> None:
    node = curriculum.get_node(node_id)
    lines = [
        node.title,
        "=" * len(node.title),
        f"ID: {node.node_id}",
        f"Type: {node.node_type}",
        f"Track: {node.track}",
        f"Status: {node.status}",
        f"Grading mode: {node.grading_mode}",
        f"Difficulty: {node.difficulty}",
        f"Estimated effort: {node.estimated_effort} minutes",
        f"Summary: {node.summary}",
        "",
        f"Prerequisites: {', '.join(node.prerequisites) if node.prerequisites else 'none'}",
        f"Concepts: {', '.join(node.concepts) if node.concepts else 'none'}",
        f"Objectives: {', '.join(node.learning_objectives) if node.learning_objectives else 'none'}",
        f"Exercises: {', '.join(node.exercise_ids) if node.exercise_ids else 'none'}",
        f"Pools: {', '.join(node.pool_ids) if node.pool_ids else 'none'}",
        f"Expected files: {', '.join(node.expected_files) if node.expected_files else 'none'}",
        f"Starter files: {', '.join(node.starter_files) if node.starter_files else 'none'}",
        f"Reference available: {node.reference_available}",
        f"Tests available: {node.tests_available}",
    ]
    if node.notices:
        lines.extend(["", "Notices:"])
        lines.extend(f"- {item}" for item in node.notices)
    _print_lines(lines)


def _render_progress(progression: ProgressionService, user_id: str) -> None:
    snapshot = progression.build_snapshot(user_id)
    lines = [
        "Learner Progress",
        "================",
        f"User: {user_id}",
        f"Completed nodes: {len(snapshot['completed_nodes'])}",
        f"Active sessions: {len(snapshot['active_sessions'])}",
        "",
        "Completed:",
    ]
    if snapshot["completed_nodes"]:
        lines.extend(
            f"- {item['id']} | {item['title']}" for item in snapshot["completed_nodes"]
        )
    else:
        lines.append("- none")
    lines.extend(["", "Unlocked next:"])
    if snapshot["unlocked_next_nodes"]:
        lines.extend(
            f"- {item['id']} | {item['status']} | {item['title']}"
            for item in snapshot["unlocked_next_nodes"]
        )
    else:
        lines.append("- none")
    if snapshot["missing_content_notices"]:
        lines.extend(["", "Missing content notices:"])
        lines.extend(f"- {item}" for item in snapshot["missing_content_notices"])
    _print_lines(lines)


def _render_history(progression: ProgressionService, user_id: str, limit: int) -> None:
    attempts = progression.attempt_history(user_id, limit=limit)
    reports = progression.report_history(user_id, limit=limit)
    lines = ["History", "=======", f"User: {user_id}", "", "Attempts:"]
    if attempts:
        for item in attempts:
            verdict = "PASS" if item["passed"] else "FAIL"
            lines.append(
                f"- {item['created_at']} | {verdict} | {item['exercise_id']} | {item['score']}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "Reports:"])
    if reports:
        for item in reports:
            verdict = "PASS" if item["passed"] else "FAIL"
            lines.append(
                f"- {item['finished_at']} | {verdict} | {item['exercise_id']} | {item['summary']}"
            )
    else:
        lines.append("- none")
    _print_lines(lines)


def _render_examples(workspace_root: str) -> None:
    workspace = Path(workspace_root).resolve()
    practice_workspace = workspace / "practice-ft-putchar"
    exam_workspace = workspace / "exam00-session"
    lines = [
        "CLI Examples",
        "============",
        "Copy/paste starter commands for local practice and exam simulation.",
        "",
        "Practice example:",
        f"- python3 -m platform_cli.main start --exercise-id piscine.c00.ft_putchar --workspace {practice_workspace}",
        f"- python3 -m platform_cli.main submit {practice_workspace}",
        "",
        "Exam example:",
        f"- python3 -m platform_cli.main exam start --pool-id exams.exam00.starter --workspace {exam_workspace}",
        f"- python3 -m platform_cli.main exam shell {exam_workspace}",
        f"- python3 -m platform_cli.main exam submit {exam_workspace}",
        "",
        "Catalog discovery:",
        "- python3 -m platform_cli.main list-exercises --track piscine",
        "- python3 -m platform_cli.main list-pools --track exams",
    ]
    _print_lines(lines)


def _start_practice_flow(
    platform_root: Path, exercise_id: str, workspace: str | None
) -> int:
    catalog = CatalogService(platform_root)
    exercise = catalog.load_exercise(exercise_id)
    session_id = _new_cli_session_id()
    workspace_root = (
        Path(workspace).resolve()
        if workspace
        else _default_workspace_root(platform_root, exercise.exercise_id, session_id)
    )
    payload = _prepare_practice_workspace(
        exercise, workspace_root, platform_root, session_id=session_id
    )
    _print_lines(
        [
            "Exercise Ready",
            "==============",
            f"Session: {payload['session_id']}",
            f"Exercise: {payload['exercise_id']}",
            f"Workspace: {workspace_root}",
            f"Statement: {payload['statement_path']}",
            f"Expected files: {', '.join(payload['expected_files'])}",
        ]
    )
    return 0


def _submit_practice_flow(platform_root: Path, workspace: str) -> int:
    from platform_grading import GradingEngine
    from platform_grading.contracts import AttemptContext

    workspace_root = Path(workspace).resolve()
    session = _load_workspace_session(workspace_root)
    submission_count = int(session.get("submission_count", 0)) + 1
    session_id = str(session["session_id"])
    attempt_id = f"{session_id}.submit.{submission_count:03d}"
    engine = GradingEngine(
        Path(str(session.get("platform_root") or platform_root)).resolve()
    )
    report = engine.grade_submission(
        AttemptContext(
            attempt_id=attempt_id,
            session_id=session_id,
            user_id=str(session.get("user_id") or "local.user"),
            exercise_id=str(session["exercise_id"]),
            variant_id=str(session.get("variant_id") or "normal"),
            mode=str(session.get("mode") or "practice"),
            pool_id=None,
            submission_root=workspace_root,
            attempt_index_for_exercise=submission_count,
        )
    )
    session["submission_count"] = submission_count
    session["updated_at"] = report["finished_at"]
    session["last_report_id"] = report["report_id"]
    session["last_result"] = {
        "passed": bool(report["evaluation"]["passed"]),
        "failure_class": report["evaluation"]["failure_class"],
        "normalized_score": report["evaluation"]["normalized_score"],
        "submitted_at": report["finished_at"],
    }
    _write_workspace_session(workspace_root, session)
    _print_lines(
        [
            "Submission Result",
            "=================",
            f"Status: {'PASS' if report['evaluation']['passed'] else 'FAIL'}",
            f"Exercise: {session['exercise_id']}",
            f"Attempt: {attempt_id}",
            f"Score: {report['evaluation']['normalized_score']}",
            f"Failure class: {report['evaluation']['failure_class']}",
            f"Summary: {report['feedback']['summary']}",
            f"Report: {report['artifacts']['report_path']}",
        ]
    )
    return 0


def _start_exam_flow(
    platform_root: Path, pool_id: str, workspace: str | None, user_id: str
) -> int:
    exams = ExamSessionService(platform_root)
    catalog = CatalogService(platform_root)
    session = exams.start_session(pool_id, user_id=user_id)
    assignment = dict(session["current_assignment"])
    exercise = catalog.load_exercise(assignment["exercise_id"])
    workspace_root = (
        Path(workspace).resolve()
        if workspace
        else _default_workspace_root(
            platform_root, exercise.exercise_id, session["session_id"]
        )
    )
    if _workspace_session_path(workspace_root).exists():
        raise FileExistsError(
            f"Workspace already contains a session file: {_workspace_session_path(workspace_root)}"
        )
    statement_path = _sync_workspace_for_exercise(exercise, workspace_root)
    payload = _new_workspace_payload(
        platform_root=platform_root,
        workspace_root=workspace_root,
        session_id=str(session["session_id"]),
        mode="exam",
        user_id=str(session["user_id"]),
        exercise_id=exercise.exercise_id,
        variant_id=str(assignment["variant_id"]),
        expected_files=exercise.expected_files,
        statement_path=statement_path,
        pool_id=str(session["pool_id"]),
        level=int(assignment["level"]),
    )
    _write_workspace_session(workspace_root, payload)
    _print_lines(
        [
            "Exam Started",
            "============",
            f"Session: {session['session_id']}",
            f"Pool: {session['pool_id']}",
            f"Exercise: {exercise.exercise_id}",
            f"Level: {assignment['level']}",
            f"Workspace: {workspace_root}",
            f"Time limit: {session['timing']['effective_level_time_seconds']} seconds",
        ]
    )
    return 0


def _submit_exam_flow(platform_root: Path, workspace: str) -> int:
    workspace_root = Path(workspace).resolve()
    local_session = _load_workspace_session(workspace_root)
    exams = ExamSessionService(platform_root)
    catalog = CatalogService(platform_root)
    previous_expected_files = [
        str(item) for item in local_session.get("expected_files", [])
    ]
    previous_exercise_id = str(local_session.get("exercise_id") or "")
    result = exams.submit_submission(str(local_session["session_id"]), workspace_root)
    session = dict(result["session"])
    local_session["submission_count"] = (
        int(local_session.get("submission_count", 0)) + 1
    )
    local_session["updated_at"] = _now()
    local_session["last_report_id"] = result["report_id"]
    local_session["last_result"] = {
        "passed": bool(result["passed"]),
        "report_id": result["report_id"],
    }
    next_assignment = session.get("current_assignment")
    lines = [
        "Exam Submission",
        "===============",
        f"Status: {'PASS' if result['passed'] else 'FAIL'}",
        f"Session: {session['session_id']}",
        f"Report: {result['report_id']}",
        f"State: {session['state']}",
    ]
    if next_assignment is not None:
        next_exercise = catalog.load_exercise(next_assignment["exercise_id"])
        if result["passed"] and next_exercise.exercise_id != previous_exercise_id:
            _remove_expected_files(workspace_root, previous_expected_files)
            statement_path = _sync_workspace_for_exercise(next_exercise, workspace_root)
            local_session["statement_path"] = str(statement_path)
        local_session["exercise_id"] = next_exercise.exercise_id
        local_session["variant_id"] = next_assignment["variant_id"]
        local_session["level"] = next_assignment["level"]
        local_session["expected_files"] = list(next_exercise.expected_files)
        lines.extend(
            [
                f"Current exercise: {next_exercise.exercise_id}",
                f"Current level: {next_assignment['level']}",
                f"Workspace: {workspace_root}",
            ]
        )
    else:
        lines.append("Exam session is complete.")
    _write_workspace_session(workspace_root, local_session)
    _print_lines(lines)
    return 0


def _render_exam_shell(workspace: str) -> int:
    workspace_root = Path(workspace).resolve()
    local_session = _load_workspace_session(workspace_root)
    if str(local_session.get("mode") or "") != "exam":
        raise ValueError(
            f"Workspace is not an exam session: {_workspace_session_path(workspace_root)}"
        )
    expected_files = [str(item) for item in local_session.get("expected_files", [])]
    statement_path = Path(str(local_session.get("statement_path") or "")).resolve()
    lines = [
        "Exam Shell",
        "==========",
        f"Session: {local_session.get('session_id', 'n/a')}",
        f"Pool: {local_session.get('pool_id', 'n/a')}",
        f"Exercise: {local_session.get('exercise_id', 'n/a')}",
        f"Level: {local_session.get('level', 'n/a')}",
        f"Workspace: {workspace_root}",
        f"Statement: {statement_path}",
        "",
        "Expected files:",
    ]
    if expected_files:
        lines.extend(f"- {name}" for name in expected_files)
    else:
        lines.append("- none")
    lines.extend(["", "Workspace check:"])
    for name in expected_files:
        file_status = "ready" if (workspace_root / name).exists() else "missing"
        lines.append(f"- {name}: {file_status}")
    lines.extend(
        [
            "",
            "Suggested commands:",
            f"- cat {statement_path}",
            f"- python3 -m platform_cli.main exam submit {workspace_root}",
        ]
    )
    _print_lines(lines)
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    platform_root = _platform_root()
    curriculum = CurriculumService(platform_root)
    progression = ProgressionService(platform_root, curriculum=curriculum)

    if args.command == "home":
        _render_home(curriculum, progression)
        return 0

    if args.command == "curriculum":
        _render_curriculum(curriculum)
        return 0

    if args.command == "module":
        _render_module(curriculum, args.node_id)
        return 0

    if args.command == "exercise":
        return _start_practice_flow(platform_root, args.exercise_id, args.workspace)

    if args.command == "progress":
        _render_progress(progression, args.user_id)
        return 0

    if args.command == "history":
        _render_history(progression, args.user_id, args.limit)
        return 0

    if args.command == "examples":
        _render_examples(args.workspace_root)
        return 0

    if args.command == "exam":
        if args.exam_command == "start":
            return _start_exam_flow(
                platform_root, args.pool_id, args.workspace, args.user_id
            )
        if args.exam_command == "shell":
            return _render_exam_shell(args.workspace)
        return _submit_exam_flow(platform_root, args.workspace)

    if args.command == "list-exercises":
        catalog = CatalogService(platform_root)
        _render_yaml(
            [
                _exercise_payload(entry)
                for entry in catalog.list_exercises(track=args.track)
            ]
        )
        return 0

    if args.command == "list-pools":
        catalog = CatalogService(platform_root)
        _render_yaml(
            [_pool_payload(entry) for entry in catalog.list_pools(track=args.track)]
        )
        return 0

    if args.command == "show-pool":
        scheduler = SchedulerService(platform_root)
        _render_yaml(_pool_dataset_payload(scheduler.load_pool(args.pool_id)))
        return 0

    if args.command == "resolve-candidates":
        scheduler = SchedulerService(platform_root)
        history = scheduler.load_session_history(args.session_id, args.pool_id)
        _render_yaml(
            {
                "pool_id": args.pool_id,
                "session_id": args.session_id,
                "history_count": len(history),
                "candidates": [
                    _candidate_payload(candidate)
                    for candidate in scheduler.resolve_candidate_exercises(
                        args.pool_id,
                        session_history=history,
                        level=args.level,
                        session_id=args.session_id,
                    )
                ],
            }
        )
        return 0

    if args.command == "select-next":
        scheduler = SchedulerService(platform_root)
        _render_yaml(scheduler.select_next(args.pool_id, args.session_id))
        return 0

    if args.command == "start":
        return _start_practice_flow(platform_root, args.exercise_id, args.workspace)

    if args.command == "submit":
        return _submit_practice_flow(platform_root, args.workspace)

    if args.command == "grade-attempt":
        from platform_grading import GradingEngine

        engine = GradingEngine(platform_root)
        report = engine.grade_attempt(args.attempt_id)
    else:
        from platform_grading import GradingEngine
        from platform_grading.contracts import AttemptContext

        engine = GradingEngine(platform_root)
        context = AttemptContext(
            attempt_id=args.attempt_id,
            session_id=args.session_id,
            user_id=args.user_id,
            exercise_id=args.exercise_id,
            variant_id=args.variant_id,
            mode=args.mode,
            pool_id=args.pool_id or None,
            submission_root=Path(args.submission).resolve(),
        )
        report = engine.grade_submission(context)

    print(report["report_id"])
    print(report["evaluation"]["failure_class"])
    print(report["evaluation"]["normalized_score"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
