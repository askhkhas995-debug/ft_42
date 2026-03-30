"""Prototype grading engine for C exercises."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import importlib.util
import itertools
from pathlib import Path
import shutil
import uuid

from platform_catalog import CatalogService, ExerciseDataset, ExerciseTestCase
from platform_grading.contracts import AttemptContext, BuildResult, ComparisonResult, RunResult
from platform_sandbox.service import SandboxService
from platform_storage.service import StorageService


class GradingEngine:
    """Grade C submissions from dataset manifests and isolated workspaces."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root
        self.catalog = CatalogService(repository_root)
        self.storage = StorageService(repository_root)
        self.sandbox = SandboxService(repository_root)

    def _builtin_module(self, category: str, name: str):
        builtins_root = self.repository_root / "core/grading/builtins"
        module_path = builtins_root / category / f"{name}.py"
        spec = importlib.util.spec_from_file_location(f"platform_builtin_{category}_{name}", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load builtin plugin from {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _load_language_plugin(self):
        return self._builtin_module("languages", "c_language").CLanguagePlugin()

    def _load_comparator(self, plugin_id: str):
        if plugin_id != "builtin.comparator.output_diff":
            raise ValueError(f"Unsupported comparator: {plugin_id}")
        return self._builtin_module("comparators", "output_diff").OutputDiffComparator()

    def _load_analyzer(self):
        return self._builtin_module("analyzers", "failure_classifier").FailureClassifier()

    def _load_reporter(self):
        return self._builtin_module("reporters", "local_reporter").LocalReporter()

    def _now(self) -> str:
        return (
            datetime.now(tz=timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _build_result_from_command(self, compiler: str, command_result, binary_path: Path) -> BuildResult:
        stderr_text = Path(command_result.stderr_path).read_text(encoding="utf-8")
        return BuildResult(
            status="success" if command_result.status == "success" else "failure",
            compiler=compiler,
            command=command_result.command,
            exit_code=command_result.exit_code,
            stdout_path=command_result.stdout_path,
            stderr_path=command_result.stderr_path,
            binary_path=str(binary_path) if binary_path.exists() else "",
            diagnostics={
                "errors": stderr_text.lower().count("error"),
                "warnings": stderr_text.lower().count("warning"),
            },
            duration_ms=command_result.duration_ms,
        )

    def _relative_path(self, path: str | Path | None) -> str:
        if not path:
            return ""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = (self.repository_root / candidate).resolve()
        try:
            return str(candidate.relative_to(self.repository_root))
        except ValueError:
            return str(candidate)

    def _attempt_submission_candidates(self, attempt_id: str, workspace_root: Path) -> list[Path]:
        cache_root = self.repository_root / "runtime/cache" / f"{attempt_id}.submission"
        return [
            workspace_root / "submission",
            workspace_root,
            cache_root / "submission",
            cache_root,
        ]

    def _resolve_attempt_submission_root(
        self,
        attempt_id: str,
        workspace_root: Path,
        submitted_files: list[str],
    ) -> Path:
        for candidate in self._attempt_submission_candidates(attempt_id, workspace_root):
            if not candidate.exists():
                continue
            if all((candidate / relative_name).exists() for relative_name in submitted_files):
                return candidate
        if workspace_root.exists():
            return workspace_root
        raise FileNotFoundError(f"Submission root does not exist: {workspace_root}")

    def _stage_submission_source(self, context: AttemptContext, target_workspace_root: Path) -> Path:
        source_root = context.submission_root
        if not source_root.is_absolute():
            source_root = (self.repository_root / source_root).resolve()
        else:
            source_root = source_root.resolve()
        if not source_root.exists():
            raise FileNotFoundError(f"Submission root does not exist: {source_root}")

        try:
            source_root.relative_to(target_workspace_root)
        except ValueError:
            return source_root

        staged_root = self.repository_root / "runtime/cache" / f"{context.attempt_id}.submission"
        if staged_root.exists():
            shutil.rmtree(staged_root)
        shutil.copytree(source_root, staged_root)
        return staged_root

    def _write_diff_artifact(self, sandbox_context, case: ExerciseTestCase, diff_text: str) -> str:
        if not diff_text:
            return ""
        diff_path = sandbox_context.artifact_root / f"{case.test_id}.diff.txt"
        diff_path.write_text(diff_text, encoding="utf-8")
        return self._relative_path(diff_path)

    def _pass_status(self, manifest: dict, raw_score: float, failed_test_ids: list[str]) -> bool:
        policy = manifest["grading"]["pass_policy"]
        threshold = float(policy.get("threshold", 1.0))
        if policy.get("mode") == "all_tests":
            return not failed_test_ids
        return raw_score >= threshold

    def _run_binary(
        self,
        binary_path: Path,
        case: ExerciseTestCase,
        sandbox_context,
        timeout_seconds: int,
        memory_limit_mb: int,
        label: str,
    ) -> RunResult:
        stdout_path = sandbox_context.artifact_root / f"{label}.{case.test_id}.stdout"
        stderr_path = sandbox_context.artifact_root / f"{label}.{case.test_id}.stderr"
        command_result = self.sandbox.run_command(
            [str(binary_path), *case.argv],
            cwd=sandbox_context.workspace_root,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            stdin_text=case.stdin,
        )
        status = command_result.status
        if command_result.status == "failure" and command_result.exit_code < 0:
            status = "crash"
        return RunResult(
            status=status,
            command=command_result.command,
            exit_code=command_result.exit_code,
            stdout_path=command_result.stdout_path,
            stderr_path=command_result.stderr_path,
            trace_path="",
            duration_ms=command_result.duration_ms,
            timed_out=command_result.timed_out,
            signal=command_result.signal,
            memory_limit_hit=command_result.memory_limit_hit,
            test_id=case.test_id,
        )

    def _compile_binary(
        self,
        plugin,
        exercise: ExerciseDataset,
        source_root: Path,
        sandbox_context,
        binary_name: str,
    ) -> BuildResult:
        harness_path = exercise.harness_path
        expected_files = exercise.expected_files
        source_files = plugin.source_paths(source_root, expected_files)
        binary_path = sandbox_context.build_root / binary_name
        command = plugin.compile_command(exercise.manifest, source_files, harness_path, binary_path)
        stdout_path = sandbox_context.artifact_root / f"{binary_name}.build.stdout"
        stderr_path = sandbox_context.artifact_root / f"{binary_name}.build.stderr"
        profile = self.sandbox.load_profile("c-default")
        command_result = self.sandbox.run_command(
            command=command,
            cwd=sandbox_context.workspace_root,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout_seconds=profile["compile"]["cpu_seconds"],
            memory_limit_mb=profile["compile"]["memory_mb"],
        )
        return self._build_result_from_command(exercise.manifest["build"]["compiler"], command_result, binary_path)

    def _report_path(self, report_id: str) -> Path:
        return self.repository_root / "runtime/reports" / f"{report_id}.yml"

    def _comparison_result(self, comparator, manifest: dict, comparisons: list[dict]) -> ComparisonResult:
        passed_test_ids = [item["test_id"] for item in comparisons if item["passed"]]
        failed_test_ids = [item["test_id"] for item in comparisons if not item["passed"]]
        raw_score = len(passed_test_ids) / len(comparisons) if comparisons else 0.0
        notes = [item["note"] for item in comparisons if item["note"]]
        diff_path = next((item["diff_path"] for item in comparisons if item.get("diff_path")), "")
        return ComparisonResult(
            passed=self._pass_status(manifest, raw_score, failed_test_ids),
            raw_score=raw_score,
            notes=notes,
            diff_path=diff_path or None,
            passed_test_ids=passed_test_ids,
            failed_test_ids=failed_test_ids,
        )

    def grade_attempt(self, attempt_id: str) -> dict:
        """Grade an existing attempt record from `storage/attempts/`."""
        records = self.storage.read_jsonl(f"storage/attempts/{attempt_id}.jsonl")
        if not records:
            raise FileNotFoundError(f"No attempt records found for {attempt_id}")
        record = records[-1]
        workspace_root = Path(record["workspace"]["root_path"])
        if not workspace_root.is_absolute():
            workspace_root = self.repository_root / workspace_root
        submitted_files = list(record.get("workspace", {}).get("submitted_files", []))
        submission_root = self._resolve_attempt_submission_root(attempt_id, workspace_root, submitted_files)
        context = AttemptContext(
            attempt_id=record["attempt_id"],
            session_id=record["session_id"],
            user_id=record["user_id"],
            exercise_id=record["exercise_id"],
            variant_id=record.get("variant_id", "normal"),
            mode=record["mode"],
            pool_id=record.get("pool_id"),
            submission_root=submission_root,
            attempt_index_for_exercise=record.get("attempt_index_for_exercise", 1),
        )
        return self.grade_submission(context)

    def grade_submission(self, context: AttemptContext) -> dict:
        """Grade one submission root against the declared C exercise dataset."""
        started_at = self._now()
        exercise = self.catalog.load_exercise(context.exercise_id)
        manifest = exercise.manifest
        tests = exercise.tests
        language = self._load_language_plugin()
        comparator = self._load_comparator(manifest["grading"]["comparator"])
        analyzer = self._load_analyzer()
        reporter = self._load_reporter()

        plugin_errors = list(
            itertools.chain(
                language.validate({}, manifest),
                comparator.validate({}, manifest),
                analyzer.validate({}, manifest),
                reporter.validate({}, manifest),
            )
        )
        if plugin_errors:
            raise ValueError("; ".join(plugin_errors))

        workspace_root = self.repository_root / "runtime/workspaces" / context.attempt_id
        source_root = self._stage_submission_source(context, workspace_root)
        sandbox_context = self.sandbox.prepare(context.attempt_id, "c-default")
        copied_files = self.sandbox.copy_submission(
            source_root,
            sandbox_context.submission_root,
            exercise.expected_files,
        )

        build_result = self._compile_binary(
            language,
            exercise,
            sandbox_context.submission_root,
            sandbox_context,
            "user.out",
        )

        if build_result.status != "success":
            failure_class = analyzer.classify(build_result.status, [], False)
            report = self._assemble_report(
                context=context,
                manifest=manifest,
                build_result=build_result,
                run_results=[],
                comparison_result=ComparisonResult(
                    passed=False,
                    raw_score=0.0,
                    failure_class=failure_class,
                ),
                workspace_root=sandbox_context.workspace_root,
                copied_files=copied_files,
                started_at=started_at,
            )
            report_path = self._report_path(report["report_id"])
            report["artifacts"]["report_path"] = self._relative_path(report_path)
            reporter.persist(report, report_path)
            return report

        reference_dir_name = manifest["files"].get("reference_dir")
        reference_build = None
        if reference_dir_name:
            reference_root = exercise.reference_dir
            reference_build = self._compile_binary(
                language,
                exercise,
                reference_root,
                sandbox_context,
                "reference.out",
            )

        run_results: list[RunResult] = []
        comparisons: list[dict] = []
        runtime = manifest["runtime"]
        for case in tests:
            user_binary_path = Path(build_result.binary_path or "")
            run_result = self._run_binary(
                user_binary_path,
                case,
                sandbox_context,
                timeout_seconds=runtime["timeout_seconds"],
                memory_limit_mb=runtime["memory_limit_mb"],
                label="user",
            )
            run_results.append(run_result)
            actual_stdout = Path(run_result.stdout_path or "").read_text(encoding="utf-8")
            actual_stderr = Path(run_result.stderr_path or "").read_text(encoding="utf-8")

            expected_stdout = case.expected_stdout
            expected_stderr = case.expected_stderr
            if expected_stdout is None:
                if reference_build is None or reference_build.status != "success":
                    raise ValueError("Expected stdout is missing and reference build is unavailable.")
                reference_run = self._run_binary(
                    Path(reference_build.binary_path or ""),
                    case,
                    sandbox_context,
                    timeout_seconds=runtime["timeout_seconds"],
                    memory_limit_mb=runtime["memory_limit_mb"],
                    label="reference",
                )
                expected_stdout = Path(reference_run.stdout_path or "").read_text(encoding="utf-8")
                if not expected_stderr:
                    expected_stderr = Path(reference_run.stderr_path or "").read_text(encoding="utf-8")

            stdout_comparison = comparator.compare(
                expected_stdout,
                actual_stdout,
                newline_policy=manifest["student_contract"]["output_contract"]["newline_policy"],
            )
            stderr_comparison = comparator.compare(expected_stderr, actual_stderr)
            exit_code_matches = run_result.exit_code == case.expected_exit_code
            passed = (
                stdout_comparison["passed"]
                and stderr_comparison["passed"]
                and exit_code_matches
                and run_result.status == "success"
            )
            notes: list[str] = []
            if stdout_comparison["diff"]:
                notes.append(f"[stdout]\n{stdout_comparison['diff']}")
            if stderr_comparison["diff"]:
                notes.append(f"[stderr]\n{stderr_comparison['diff']}")
            if not exit_code_matches:
                notes.append(f"[exit_code]\nexpected={case.expected_exit_code} actual={run_result.exit_code}")
            if run_result.status != "success":
                notes.append(f"[runtime]\nstatus={run_result.status}")
            note = "\n".join(notes)
            diff_path = self._write_diff_artifact(sandbox_context, case, note)
            comparisons.append(
                {
                    "test_id": case.test_id,
                    "passed": passed,
                    "note": note,
                    "diff_path": diff_path,
                }
            )

        comparison_result = self._comparison_result(comparator, manifest, comparisons)
        failure_class = analyzer.classify(
            build_result.status,
            [result.status for result in run_results],
            comparison_result.passed,
        )
        comparison_result.failure_class = failure_class

        report = self._assemble_report(
            context=context,
            manifest=manifest,
            build_result=build_result,
            run_results=run_results,
            comparison_result=comparison_result,
            workspace_root=sandbox_context.workspace_root,
            copied_files=copied_files,
            started_at=started_at,
        )
        report_path = self._report_path(report["report_id"])
        report["artifacts"]["report_path"] = self._relative_path(report_path)
        reporter.persist(report, report_path)
        return report

    def _assemble_report(
        self,
        *,
        context: AttemptContext,
        manifest: dict,
        build_result: BuildResult,
        run_results: list[RunResult],
        comparison_result: ComparisonResult,
        workspace_root: Path,
        copied_files: list[Path],
        started_at: str,
    ) -> dict:
        finished_at = self._now()
        total_duration_ms = build_result.duration_ms + sum(result.duration_ms for result in run_results)
        report_id = f"report.{context.attempt_id}.{uuid.uuid4().hex[:8]}"
        representative_run = run_results[-1] if run_results else RunResult(status="skipped")
        summary = "All tests passed." if comparison_result.passed else f"Attempt failed with {comparison_result.failure_class}."
        next_steps: list[str] = []
        if comparison_result.failure_class == "compile_error":
            next_steps.append("Fix compiler errors and rebuild with the declared flags.")
        elif comparison_result.failure_class == "wrong_output":
            next_steps.append("Compare expected and actual stdout for the failed test cases.")
        elif comparison_result.failure_class == "timeout":
            next_steps.append("Inspect loops and blocking calls; the program exceeded the runtime limit.")

        return {
            "schema_version": 1,
            "report_id": report_id,
            "attempt_id": context.attempt_id,
            "session_id": context.session_id,
            "user_id": context.user_id,
            "exercise_id": context.exercise_id,
            "variant_id": context.variant_id,
            "pool_id": context.pool_id,
            "mode": context.mode,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": total_duration_ms,
            "build_result": {
                "status": build_result.status,
                "compiler": build_result.compiler,
                "command": " ".join(build_result.command),
                "exit_code": build_result.exit_code,
                "stdout_path": self._relative_path(build_result.stdout_path),
                "stderr_path": self._relative_path(build_result.stderr_path),
                "diagnostics": build_result.diagnostics,
            },
            "run_result": {
                "status": representative_run.status,
                "command": " ".join(representative_run.command),
                "exit_code": representative_run.exit_code,
                "signal": representative_run.signal,
                "timed_out": representative_run.timed_out,
                "memory_limit_hit": representative_run.memory_limit_hit,
                "stdout_path": self._relative_path(representative_run.stdout_path),
                "stderr_path": self._relative_path(representative_run.stderr_path),
                "trace_path": self._relative_path(representative_run.trace_path),
            },
            "evaluation": {
                "comparator_id": manifest["grading"]["comparator"],
                "passed": comparison_result.passed,
                "raw_score": comparison_result.raw_score,
                "normalized_score": round(comparison_result.raw_score * 100, 2),
                "pass_policy": manifest["grading"]["pass_policy"]["mode"],
                "failure_class": comparison_result.failure_class,
                "failed_test_ids": comparison_result.failed_test_ids,
                "passed_test_ids": comparison_result.passed_test_ids,
                "edge_case_summary": {
                    "total": len(run_results),
                    "passed": len(comparison_result.passed_test_ids),
                    "failed": len(comparison_result.failed_test_ids),
                },
            },
            "rubric": {
                "rubric_id": manifest["grading"]["rubric_id"],
                "items": [
                    {
                        "id": "correctness",
                        "score": round(comparison_result.raw_score, 2),
                        "max_score": 1.0,
                        "verdict": "pass" if comparison_result.passed else "fail",
                        "note": summary,
                    }
                ],
            },
            "feedback": {
                "summary": summary,
                "actionable_next_steps": next_steps,
                "hint_ids": [],
                "concept_gaps": [] if comparison_result.passed else manifest["pedagogy"]["concepts"],
            },
            "artifacts": {
                "workspace_snapshot_path": self._relative_path(workspace_root),
                "report_path": "",
                "diff_path": self._relative_path(comparison_result.diff_path),
                "exported_trace_path": "",
            },
            "analytics": {
                "attempt_number_for_exercise": context.attempt_index_for_exercise,
                "cooldown_seconds_applied": 0,
                "mastery_delta": {
                    "concepts": [
                        {
                            "concept": concept,
                            "delta": 1.0 if comparison_result.passed else -0.2,
                        }
                        for concept in manifest["pedagogy"]["concepts"]
                    ]
                },
                "productivity_tags": manifest.get("tracking", {}).get("productivity_tags", []),
            },
            "prototype_debug": {
                "copied_files": [self._relative_path(path) for path in copied_files],
                "run_results": [asdict(result) for result in run_results],
                "comparison_notes": comparison_result.notes,
            },
        }
