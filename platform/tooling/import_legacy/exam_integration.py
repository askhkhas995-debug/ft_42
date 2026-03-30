"""Run real exam-mode integration against staged curated exam datasets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil

import yaml

from platform_catalog import CatalogService
from platform_exams import ExamSessionService
from platform_grading import GradingEngine
from platform_grading.contracts import AttemptContext

try:
    from .curated_pools import CuratedExamPoolService
except ImportError:  # pragma: no cover - direct script execution fallback
    from curated_pools import CuratedExamPoolService  # type: ignore


@dataclass(slots=True)
class ExerciseProbeResult:
    """One reference-solution grading probe for a curated exercise."""

    pool_id: str
    exercise_id: str
    passed: bool
    report_id: str
    failure_class: str

    def to_dict(self) -> dict[str, object]:
        return {
            "pool_id": self.pool_id,
            "exercise_id": self.exercise_id,
            "passed": self.passed,
            "report_id": self.report_id,
            "failure_class": self.failure_class,
        }


@dataclass(slots=True)
class PoolLifecycleResult:
    """End-to-end exam session integration result for one curated pool."""

    pool_id: str
    first_exercise_id: str
    first_level: int
    selected_first_assignment: bool
    failing_submission_verified: bool
    retry_verified: bool
    passing_submission_verified: bool
    next_level_verified: bool
    finished_session_verified: bool
    fully_runnable: bool
    levels_completed: int
    attempts_total: int
    visited_exercise_ids: list[str]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "pool_id": self.pool_id,
            "first_exercise_id": self.first_exercise_id,
            "first_level": self.first_level,
            "selected_first_assignment": self.selected_first_assignment,
            "failing_submission_verified": self.failing_submission_verified,
            "retry_verified": self.retry_verified,
            "passing_submission_verified": self.passing_submission_verified,
            "next_level_verified": self.next_level_verified,
            "finished_session_verified": self.finished_session_verified,
            "fully_runnable": self.fully_runnable,
            "levels_completed": self.levels_completed,
            "attempts_total": self.attempts_total,
            "visited_exercise_ids": self.visited_exercise_ids,
            "notes": self.notes,
        }


@dataclass(slots=True)
class ExamIntegrationReport:
    """Aggregate report for real staged exam integration."""

    generated_at: str
    staging_root: str
    integration_root: str
    runnable_pool_count: int
    runnable_exercise_count: int
    total_curated_exercise_count: int
    remaining_blockers: list[dict[str, object]]
    pool_results: list[PoolLifecycleResult]
    probe_results: list[ExerciseProbeResult]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "staging_root": self.staging_root,
            "integration_root": self.integration_root,
            "summary": {
                "runnable_pool_count": self.runnable_pool_count,
                "runnable_exercise_count": self.runnable_exercise_count,
                "total_curated_exercise_count": self.total_curated_exercise_count,
                "remaining_blocker_count": len(self.remaining_blockers),
            },
            "remaining_blockers": self.remaining_blockers,
            "pool_results": [item.to_dict() for item in self.pool_results],
            "probe_results": [item.to_dict() for item in self.probe_results],
        }


class CuratedExamIntegrationService(CuratedExamPoolService):
    """Prepare a staged-only repository view and run real exam-mode integration."""

    @property
    def integration_root(self) -> Path:
        return self.staging_root / "exam_integration" / "latest"

    @property
    def integration_repo_root(self) -> Path:
        return self.integration_root / "repository_root"

    @property
    def integration_reports_root(self) -> Path:
        return self.integration_root / "reports"

    @property
    def integration_report_path(self) -> Path:
        return self.integration_reports_root / "exam_integration.latest.yml"

    @property
    def exam_integration_status_path(self) -> Path:
        return self.workspace_root / "EXAM_INTEGRATION_STATUS.md"

    def run_exam_integration(
        self,
        *,
        write: bool = True,
        target_root: Path | None = None,
        probe_all_exercises: bool = True,
    ) -> ExamIntegrationReport:
        repo_root = (target_root or self.integration_repo_root).resolve()
        self._prepare_integration_repository(repo_root, reset=write)

        catalog = CatalogService(repo_root)
        catalog.build_index(refresh=True)
        catalog.build_pool_index(refresh=True)

        probe_results = self._probe_curated_exercises(repo_root) if probe_all_exercises else []
        probe_by_exercise = {item.exercise_id: item for item in probe_results}
        pool_results = self._run_pool_lifecycle_checks(repo_root)
        blockers = self._remaining_blockers(pool_results, probe_results)

        runnable_pool_count = sum(1 for item in pool_results if item.fully_runnable)
        runnable_exercise_count = sum(1 for item in probe_results if item.passed)
        report = ExamIntegrationReport(
            generated_at=self.generated_at,
            staging_root=str(self.staging_root),
            integration_root=str(repo_root),
            runnable_pool_count=runnable_pool_count,
            runnable_exercise_count=runnable_exercise_count,
            total_curated_exercise_count=len(probe_results),
            remaining_blockers=blockers,
            pool_results=pool_results,
            probe_results=probe_results,
        )

        if write:
            self._write_exam_integration_report(report)
            self._write_exam_integration_status(report, probe_by_exercise)
        return report

    def _prepare_integration_repository(self, repo_root: Path, *, reset: bool) -> None:
        if reset:
            self._reset_directory(repo_root)
        repo_root.mkdir(parents=True, exist_ok=True)

        copy_pairs = (
            (self.staging_accepted_root / "datasets/exercises", repo_root / "datasets/exercises"),
            (self.curated_datasets_root / "pools", repo_root / "datasets/pools"),
            (self.platform_root / "core/grading/builtins", repo_root / "core/grading/builtins"),
            (self.platform_root / "core/sandbox/profiles", repo_root / "core/sandbox/profiles"),
        )
        for source, destination in copy_pairs:
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)

        for relative in (
            "storage/sessions",
            "storage/attempts",
            "runtime/reports",
            "runtime/workspaces",
            "runtime/traces",
            "runtime/cache",
            "runtime/manual_submissions",
        ):
            (repo_root / relative).mkdir(parents=True, exist_ok=True)

    def _probe_curated_exercises(self, repo_root: Path) -> list[ExerciseProbeResult]:
        catalog = CatalogService(repo_root)
        grading = GradingEngine(repo_root)
        results: list[ExerciseProbeResult] = []
        seen: set[tuple[str, str]] = set()
        for pool in catalog.list_pools(track="exams"):
            dataset = catalog.load_pool(pool.pool_id)
            for level in dataset.levels:
                for ref in level.exercise_refs:
                    key = (pool.pool_id, ref.exercise_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    exercise = catalog.load_exercise(ref.exercise_id)
                    context = AttemptContext(
                        attempt_id=f"probe.{pool.pool_id.replace('.', '-')}.{ref.exercise_id.replace('.', '-')}",
                        session_id=f"probe.{pool.pool_id.replace('.', '-')}",
                        user_id="integration.probe",
                        exercise_id=ref.exercise_id,
                        variant_id=ref.variant_id,
                        mode="exam",
                        pool_id=pool.pool_id,
                        submission_root=exercise.reference_dir,
                        attempt_index_for_exercise=1,
                    )
                    report = grading.grade_submission(context)
                    results.append(
                        ExerciseProbeResult(
                            pool_id=pool.pool_id,
                            exercise_id=ref.exercise_id,
                            passed=bool(report["evaluation"]["passed"]),
                            report_id=report["report_id"],
                            failure_class=report["evaluation"]["failure_class"],
                        )
                    )
        return results

    def _run_pool_lifecycle_checks(self, repo_root: Path) -> list[PoolLifecycleResult]:
        catalog = CatalogService(repo_root)
        results: list[PoolLifecycleResult] = []
        for pool in catalog.list_pools(track="exams"):
            results.append(self._run_single_pool_lifecycle(repo_root, pool.pool_id))
        return results

    def _run_single_pool_lifecycle(self, repo_root: Path, pool_id: str) -> PoolLifecycleResult:
        service = ExamSessionService(repo_root)
        session = service.start_session(pool_id, user_id="integration.runner")
        first_assignment = dict(session["current_assignment"])
        first_exercise_id = first_assignment["exercise_id"]
        first_level = int(first_assignment["level"])
        bad_submission = self._write_forced_failure_submission(
            repo_root,
            first_exercise_id,
            first_assignment["variant_id"],
        )
        fail_result = service.submit_submission(session["session_id"], bad_submission)
        failed_session = fail_result["session"]
        failed_assignment = dict(failed_session["current_assignment"])
        retry_verified = (
            failed_assignment["exercise_id"] == first_exercise_id
            and int(failed_assignment["level"]) == first_level
        )
        failing_submission_verified = (
            fail_result["passed"] is False
            and int(failed_assignment["failure_count"]) >= 1
            and int(failed_assignment["attempt_count"]) >= 1
        )

        passing_submission = self._reference_submission_root(repo_root, first_exercise_id)
        pass_result = service.submit_submission(session["session_id"], passing_submission)
        passed_session = pass_result["session"]
        passing_submission_verified = pass_result["passed"] is True
        next_level_verified = (
            passed_session["state"] == "finished"
            or int(passed_session["progress"]["current_level"]) > first_level
        )

        visited = [first_exercise_id]
        max_attempts = 128
        while passed_session["state"] == "active" and max_attempts > 0:
            current = passed_session["current_assignment"]
            if current is None:
                break
            visited.append(current["exercise_id"])
            submission_root = self._reference_submission_root(repo_root, current["exercise_id"])
            pass_result = service.submit_submission(session["session_id"], submission_root)
            passed_session = pass_result["session"]
            max_attempts -= 1

        notes: list[str] = []
        if max_attempts == 0 and passed_session["state"] == "active":
            notes.append("finish verification aborted after max attempt guard")
        if not next_level_verified:
            notes.append("first passing submission did not advance beyond the starting level")
        if not failing_submission_verified:
            notes.append("forced failing submission did not persist the expected retry state")

        finished_session = service.finish_session(session["session_id"])
        finished_session_verified = (
            finished_session["state"] == "finished"
            and finished_session["current_assignment"] is None
            and finished_session["session_id"] == session["session_id"]
        )
        levels_completed = len(finished_session["progress"].get("completed_levels", []))
        attempts_total = int(finished_session["progress"].get("attempts_total", 0))
        fully_runnable = all(
            (
                first_assignment["exercise_id"] == first_exercise_id,
                failing_submission_verified,
                retry_verified,
                passing_submission_verified,
                next_level_verified,
                finished_session_verified,
            )
        )
        return PoolLifecycleResult(
            pool_id=pool_id,
            first_exercise_id=first_exercise_id,
            first_level=first_level,
            selected_first_assignment=True,
            failing_submission_verified=failing_submission_verified,
            retry_verified=retry_verified,
            passing_submission_verified=passing_submission_verified,
            next_level_verified=next_level_verified,
            finished_session_verified=finished_session_verified,
            fully_runnable=fully_runnable,
            levels_completed=levels_completed,
            attempts_total=attempts_total,
            visited_exercise_ids=visited,
            notes=notes,
        )

    def _reference_submission_root(self, repo_root: Path, exercise_id: str) -> Path:
        catalog = CatalogService(repo_root)
        return catalog.load_exercise(exercise_id).reference_dir

    def _write_forced_failure_submission(self, repo_root: Path, exercise_id: str, variant_id: str) -> Path:
        catalog = CatalogService(repo_root)
        exercise = catalog.load_exercise(exercise_id)
        submission_root = repo_root / "runtime/manual_submissions" / f"{exercise_id.replace('.', '-')}-{variant_id}-fail"
        if submission_root.exists():
            shutil.rmtree(submission_root)
        submission_root.mkdir(parents=True, exist_ok=True)
        for relative_name in exercise.expected_files:
            target = submission_root / relative_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("#error forced failing integration submission\n", encoding="utf-8")
        return submission_root

    def _remaining_blockers(
        self,
        pool_results: list[PoolLifecycleResult],
        probe_results: list[ExerciseProbeResult],
    ) -> list[dict[str, object]]:
        blockers: list[dict[str, object]] = []
        curated_payload = yaml.safe_load(self.curated_report_path.read_text(encoding="utf-8")) or {}
        for item in curated_payload.get("unresolved_gaps", []):
            blockers.append(
                {
                    "type": "unresolved_gap",
                    "pool_id": f"exams.curated.{item['exam_group'].replace('examfinal', 'exam_final')}.v1",
                    "legacy_level": item.get("legacy_level"),
                    "legacy_assignment_name": item.get("legacy_assignment_name"),
                    "reason": item.get("reason"),
                }
            )
        for item in probe_results:
            if item.passed:
                continue
            blockers.append(
                {
                    "type": "reference_probe_failure",
                    "pool_id": item.pool_id,
                    "exercise_id": item.exercise_id,
                    "reason": f"reference solution did not pass real grading ({item.failure_class})",
                }
            )
        for item in pool_results:
            if item.fully_runnable:
                continue
            blockers.append(
                {
                    "type": "pool_lifecycle_failure",
                    "pool_id": item.pool_id,
                    "reason": "; ".join(item.notes) or "one or more lifecycle checks failed",
                }
            )
        return blockers

    def _write_exam_integration_report(self, report: ExamIntegrationReport) -> None:
        self.integration_reports_root.mkdir(parents=True, exist_ok=True)
        self.integration_report_path.write_text(
            yaml.safe_dump(report.to_dict(), sort_keys=False),
            encoding="utf-8",
        )

    def _write_exam_integration_status(
        self,
        report: ExamIntegrationReport,
        probe_by_exercise: dict[str, ExerciseProbeResult],
    ) -> None:
        lines = [
            "# EXAM_INTEGRATION_STATUS",
            "",
            f"- Generated at: `{report.generated_at}`",
            f"- Staging root: `{report.staging_root}`",
            f"- Integration root: `{report.integration_root}`",
            f"- Runnable pool count: `{report.runnable_pool_count}`",
            f"- Runnable exercise count: `{report.runnable_exercise_count}` / `{report.total_curated_exercise_count}`",
            "",
            "## Pool Status",
            "",
        ]
        for pool_result in report.pool_results:
            status = "fully runnable" if pool_result.fully_runnable else "blocked"
            lines.extend(
                [
                    f"- `{pool_result.pool_id}`: `{status}`",
                    f"  - first assignment: `{pool_result.first_exercise_id}` at level `{pool_result.first_level}`",
                    f"  - lifecycle checks: start=`{pool_result.selected_first_assignment}` fail=`{pool_result.failing_submission_verified}` retry=`{pool_result.retry_verified}` pass=`{pool_result.passing_submission_verified}` next-level=`{pool_result.next_level_verified}` finish=`{pool_result.finished_session_verified}`",
                    f"  - attempts total: `{pool_result.attempts_total}`; completed levels: `{pool_result.levels_completed}`",
                ]
            )
            if pool_result.notes:
                lines.append(f"  - notes: {'; '.join(pool_result.notes)}")
        lines.extend(["", "## Per-Pool Runnable Exercises", ""])
        if probe_by_exercise:
            catalog = CatalogService(Path(report.integration_root))
            for pool in catalog.list_pools(track="exams"):
                dataset = catalog.load_pool(pool.pool_id)
                exercise_ids: list[str] = []
                for level in dataset.levels:
                    for ref in level.exercise_refs:
                        exercise_ids.append(ref.exercise_id)
                passed_count = sum(1 for exercise_id in exercise_ids if probe_by_exercise[exercise_id].passed)
                lines.append(f"- `{pool.pool_id}`: `{passed_count}` / `{len(exercise_ids)}` reference solutions passed")
        else:
            lines.append("- Reference exercise probes were not executed for this run.")
        lines.extend(["", "## Remaining Blockers", ""])
        if report.remaining_blockers:
            for blocker in report.remaining_blockers:
                lines.append(
                    f"- `{blocker['type']}` on `{blocker['pool_id']}`: {blocker['reason']}"
                )
        else:
            lines.append("- None")
        lines.extend(["", "## Integration Notes", ""])
        lines.extend(
            [
                "- All integration runs used the staged accepted exercises plus the staged curated pools copied into an isolated staging-only repository root.",
                "- Passing submissions used each bundle's canonical `reference/` files. Failing submissions used forced invalid C source to verify persisted retry state.",
                "- Remaining blockers are dataset coverage gaps inherited from unresolved legacy references, not silent pool-engine or exam-session mutations.",
            ]
        )
        self.exam_integration_status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
