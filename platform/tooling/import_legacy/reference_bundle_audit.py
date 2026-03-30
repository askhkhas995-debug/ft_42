"""Audit curated staged exam bundles for runtime viability."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil

import yaml

from platform_catalog.models import CatalogFile
from platform_catalog.validation import validate_bundle_assets, validate_manifest, validate_tests_payload
from platform_grading import GradingEngine
from platform_grading.contracts import AttemptContext

from .exam_integration import CuratedExamIntegrationService


SAFE_REPAIRABLE_FAILURES = {
    "broken_generator_path",
    "broken_harness_path",
    "missing_expected_user_file_mapping",
    "missing_reference_file",
}


@dataclass(slots=True)
class BundlePoolRef:
    """One pool/level reference for an audited bundle."""

    pool_id: str
    level: int

    def to_dict(self) -> dict[str, object]:
        return {"pool_id": self.pool_id, "level": self.level}


@dataclass(slots=True)
class RepairProposal:
    """One deterministic repair proposal for a bundle."""

    repair_class: str
    source_path: str
    target_path: str
    justification: str

    def to_dict(self) -> dict[str, object]:
        return {
            "repair_class": self.repair_class,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "justification": self.justification,
        }


@dataclass(slots=True)
class ReferenceBundleAuditResult:
    """Audit result for one curated staged exercise bundle."""

    exercise_id: str
    bundle_root: str
    pool_refs: list[BundlePoolRef]
    structural_valid: bool
    runtime_valid: bool
    required_files_present: bool
    reference_implementation_present: bool
    generator_path_valid: bool
    harness_path_valid: bool
    compile_command_resolvable: bool
    tests_runnable: bool
    grading_executable: bool
    primary_failure_class: str | None
    grading_failure_class: str | None
    repairability: str
    advisory_classes: list[str] = field(default_factory=list)
    proposed_repairs: list[RepairProposal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    grading_report_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "exercise_id": self.exercise_id,
            "bundle_root": self.bundle_root,
            "pool_refs": [item.to_dict() for item in self.pool_refs],
            "structural_valid": self.structural_valid,
            "runtime_valid": self.runtime_valid,
            "required_files_present": self.required_files_present,
            "reference_implementation_present": self.reference_implementation_present,
            "generator_path_valid": self.generator_path_valid,
            "harness_path_valid": self.harness_path_valid,
            "compile_command_resolvable": self.compile_command_resolvable,
            "tests_runnable": self.tests_runnable,
            "grading_executable": self.grading_executable,
            "primary_failure_class": self.primary_failure_class,
            "grading_failure_class": self.grading_failure_class,
            "repairability": self.repairability,
            "advisory_classes": self.advisory_classes,
            "proposed_repairs": [item.to_dict() for item in self.proposed_repairs],
            "notes": self.notes,
            "grading_report_id": self.grading_report_id,
        }


@dataclass(slots=True)
class ReferenceBundleAuditReport:
    """Aggregate audit report for curated staged exam exercise bundles."""

    generated_at: str
    staging_root: str
    audit_root: str
    results: list[ReferenceBundleAuditResult]

    def to_dict(self) -> dict[str, object]:
        failure_counts = Counter(
            item.primary_failure_class for item in self.results if item.primary_failure_class is not None
        )
        affected_pool_levels: dict[str, set[int]] = defaultdict(set)
        for item in self.results:
            if item.runtime_valid:
                continue
            for ref in item.pool_refs:
                affected_pool_levels[ref.pool_id].add(ref.level)
        return {
            "generated_at": self.generated_at,
            "staging_root": self.staging_root,
            "audit_root": self.audit_root,
            "summary": {
                "total_audited_bundles": len(self.results),
                "runnable_bundles": sum(1 for item in self.results if item.runtime_valid),
                "failing_bundles": sum(1 for item in self.results if not item.runtime_valid),
                "structurally_valid_bundles": sum(1 for item in self.results if item.structural_valid),
                "counts_by_failure_class": dict(sorted(failure_counts.items())),
                "affected_pools_and_levels": {
                    pool_id: sorted(levels) for pool_id, levels in sorted(affected_pool_levels.items())
                },
            },
            "results": [item.to_dict() for item in self.results],
        }


class ReferenceBundleAuditService(CuratedExamIntegrationService):
    """Audit curated staged exam bundles for runtime viability."""

    @property
    def audit_root(self) -> Path:
        return self.staging_root / "reference_bundle_audit" / "latest"

    @property
    def audit_repo_root(self) -> Path:
        return self.audit_root / "repository_root"

    @property
    def audit_reports_root(self) -> Path:
        return self.audit_root / "reports"

    @property
    def audit_report_path(self) -> Path:
        return self.audit_reports_root / "reference_bundle_audit.latest.yml"

    @property
    def audit_status_path(self) -> Path:
        return self.workspace_root / "REFERENCE_BUNDLE_AUDIT_STATUS.md"

    def audit_reference_bundles(
        self,
        *,
        write: bool = True,
        target_root: Path | None = None,
        exercises_source_root: Path | None = None,
        pools_source_root: Path | None = None,
    ) -> ReferenceBundleAuditReport:
        repo_root = (target_root or self.audit_repo_root).resolve()
        self._prepare_repository_view(
            repo_root,
            exercises_source_root=exercises_source_root or self.staging_accepted_root / "datasets/exercises",
            pools_source_root=pools_source_root or self.curated_datasets_root / "pools",
            reset=write,
        )

        pool_refs = self._collect_curated_pool_refs(repo_root / "datasets/pools")
        results = [
            self._audit_bundle(repo_root, exercise_id, refs)
            for exercise_id, refs in sorted(pool_refs.items())
        ]
        report = ReferenceBundleAuditReport(
            generated_at=self.generated_at,
            staging_root=str(self.staging_root),
            audit_root=str(repo_root),
            results=results,
        )
        if write:
            self._write_audit_reports(report)
            self._write_audit_status(report)
        return report

    def _prepare_repository_view(
        self,
        repo_root: Path,
        *,
        exercises_source_root: Path,
        pools_source_root: Path,
        reset: bool,
    ) -> None:
        if reset:
            self._reset_directory(repo_root)
        repo_root.mkdir(parents=True, exist_ok=True)

        copy_pairs = (
            (exercises_source_root, repo_root / "datasets/exercises"),
            (pools_source_root, repo_root / "datasets/pools"),
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

    def _collect_curated_pool_refs(self, pools_root: Path) -> dict[str, list[BundlePoolRef]]:
        refs: dict[str, list[BundlePoolRef]] = defaultdict(list)
        for pool_path in sorted(pools_root.glob("exams/*/pool.yml")):
            payload = yaml.safe_load(pool_path.read_text(encoding="utf-8")) or {}
            pool_id = str(payload.get("id", pool_path.parent.name))
            for level in payload.get("levels", []):
                level_number = int(level.get("level", 0))
                for ref in level.get("exercise_refs", []):
                    exercise_id = ref.get("exercise_id")
                    if isinstance(exercise_id, str) and exercise_id:
                        refs[exercise_id].append(BundlePoolRef(pool_id=pool_id, level=level_number))
        return refs

    def _audit_bundle(
        self,
        repo_root: Path,
        exercise_id: str,
        pool_refs: list[BundlePoolRef],
    ) -> ReferenceBundleAuditResult:
        bundle_root = self._bundle_root(repo_root, exercise_id)
        manifest_path = bundle_root / "exercise.yml"
        notes: list[str] = []
        advisory_classes: list[str] = []
        proposed_repairs: list[RepairProposal] = []

        required_files_present = False
        reference_present = False
        generator_path_valid = False
        harness_path_valid = False
        compile_command_resolvable = False
        tests_runnable = False
        grading_executable = False
        structural_valid = False
        runtime_valid = False
        primary_failure_class: str | None = None
        grading_failure_class: str | None = None
        grading_report_id: str | None = None

        if not manifest_path.exists():
            return ReferenceBundleAuditResult(
                exercise_id=exercise_id,
                bundle_root=str(bundle_root),
                pool_refs=pool_refs,
                structural_valid=False,
                runtime_valid=False,
                required_files_present=False,
                reference_implementation_present=False,
                generator_path_valid=False,
                harness_path_valid=False,
                compile_command_resolvable=False,
                tests_runnable=False,
                grading_executable=False,
                primary_failure_class="malformed_metadata",
                grading_failure_class=None,
                repairability="manual_content_repair",
                advisory_classes=[],
                proposed_repairs=[],
                notes=["missing exercise.yml"],
                grading_report_id=None,
            )

        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            return ReferenceBundleAuditResult(
                exercise_id=exercise_id,
                bundle_root=str(bundle_root),
                pool_refs=pool_refs,
                structural_valid=False,
                runtime_valid=False,
                required_files_present=False,
                reference_implementation_present=False,
                generator_path_valid=False,
                harness_path_valid=False,
                compile_command_resolvable=False,
                tests_runnable=False,
                grading_executable=False,
                primary_failure_class="malformed_metadata",
                grading_failure_class=None,
                repairability="manual_content_repair",
                notes=[f"invalid exercise.yml: {exc}"],
            )

        files = manifest.get("files", {})
        statement_path = bundle_root / files.get("statement", "statement.md")
        tests_dir = bundle_root / files.get("tests_dir", "tests")
        tests_path = tests_dir / "tests.yml"
        harness_path = tests_dir / "main.c"
        starter_dir = bundle_root / files.get("starter_dir", "starter")
        reference_dir = bundle_root / files.get("reference_dir", "reference")
        expected_files = list(manifest.get("student_contract", {}).get("expected_files", []))
        compile_mode = str(manifest.get("build", {}).get("compile_mode", ""))

        manifest_failures = validate_manifest(manifest, manifest_path, "exams")
        tests_payload = {}
        tests = []
        tests_failures = []
        if tests_path.exists():
            try:
                tests_payload = yaml.safe_load(tests_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                tests_failures = [f"invalid tests.yml: {exc}"]
            else:
                payload_failures, tests = validate_tests_payload(tests_payload)
                tests_failures = [failure.render() for failure in payload_failures]
        else:
            tests_failures = ["missing tests.yml"]

        starter_files = self._directory_inventory(starter_dir)
        reference_files = self._directory_inventory(reference_dir)
        statement_markdown = statement_path.read_text(encoding="utf-8") if statement_path.exists() else ""
        asset_failures = [
            failure.render()
            for failure in validate_bundle_assets(
                manifest,
                statement_markdown=statement_markdown,
                harness_path=harness_path if harness_path.exists() else None,
                starter_files=starter_files,
                reference_files=reference_files,
            )
        ]

        required_files_present = all(
            (
                statement_path.exists(),
                starter_dir.exists(),
                reference_dir.exists(),
                tests_path.exists(),
            )
        )
        reference_index = {item.relative_path for item in reference_files}
        starter_index = {item.relative_path for item in starter_files}
        reference_present = all(filename in reference_index for filename in expected_files)

        origin_root, origin_repair = self._resolve_origin_root(manifest)
        if origin_repair is not None:
            proposed_repairs.append(origin_repair)
            advisory_classes.append("legacy_path_normalization")
        generator_result = self._resolve_generator_path(origin_root)
        if generator_result["resolved"]:
            generator_path_valid = True
            if generator_result["proposal"] is not None:
                proposed_repairs.append(generator_result["proposal"])
                advisory_classes.append("broken_generator_path")
        else:
            generator_path_valid = False
            advisory_classes.append("broken_generator_path")
            notes.append("generator.py was not found in the legacy correction root")

        harness_result = self._resolve_harness_path(bundle_root, tests_dir, origin_root, compile_mode)
        harness_path_valid = bool(harness_result["resolved"])
        if harness_result["proposal"] is not None:
            proposed_repairs.append(harness_result["proposal"])

        filename_repairs, filename_notes = self._resolve_expected_filename_repairs(
            bundle_root=bundle_root,
            expected_files=expected_files,
            reference_files=reference_files,
            starter_files=starter_files,
        )
        proposed_repairs.extend(filename_repairs)
        notes.extend(filename_notes)
        if any(
            item.repair_class in {"alternate_filename_normalization", "declared_filename_normalization"}
            for item in filename_repairs
        ):
            primary_failure_class = primary_failure_class or "missing_expected_user_file_mapping"

        has_main_in_reference = self._reference_sources_have_main(reference_dir)
        if compile_mode == "function_with_harness" and has_main_in_reference:
            primary_failure_class = primary_failure_class or "unsupported_bundle_shape"
            notes.append("reference sources declare main() while compile_mode=function_with_harness")
        if compile_mode == "standalone_program" and not has_main_in_reference:
            primary_failure_class = primary_failure_class or "unsupported_bundle_shape"
            notes.append("reference sources do not declare main() while compile_mode=standalone_program")

        if any(item.startswith("reference/") for item in asset_failures):
            primary_failure_class = primary_failure_class or "missing_reference_file"
        if any(item.startswith("tests/main.c") for item in asset_failures) or (
            compile_mode == "function_with_harness" and not harness_path_valid
        ):
            primary_failure_class = primary_failure_class or "broken_harness_path"
        if manifest_failures and primary_failure_class is None:
            if any("compile_mode" in item for item in (failure.render() for failure in manifest_failures)):
                primary_failure_class = "unsupported_bundle_shape"
            else:
                primary_failure_class = "malformed_metadata"
        if tests_failures and primary_failure_class is None:
            primary_failure_class = "malformed_test_fixture"

        structural_valid = not manifest_failures and not asset_failures and primary_failure_class not in {
            "unsupported_bundle_shape",
            "malformed_metadata",
            "missing_reference_file",
            "missing_expected_user_file_mapping",
            "broken_harness_path",
        }
        tests_runnable = not tests_failures and bool(tests)

        if manifest_failures:
            notes.extend(failure.render() for failure in manifest_failures)
        notes.extend(asset_failures)
        notes.extend(tests_failures)

        if primary_failure_class is None:
            try:
                compile_command_resolvable = self._compile_command_resolvable(
                    manifest=manifest,
                    reference_dir=reference_dir,
                    expected_files=expected_files,
                    harness_path=harness_path if harness_path.exists() else None,
                )
            except FileNotFoundError as exc:
                compile_command_resolvable = False
                primary_failure_class = "missing_expected_user_file_mapping"
                notes.append(str(exc))
            except ValueError as exc:
                compile_command_resolvable = False
                primary_failure_class = "malformed_metadata"
                notes.append(str(exc))
            else:
                if not compile_command_resolvable:
                    primary_failure_class = "compile_command_unresolvable"
                    notes.append("compiler binary was not resolvable from PATH")

        if primary_failure_class is None and tests_runnable and compile_command_resolvable:
            try:
                report = self._grade_reference_bundle(repo_root, exercise_id)
            except ValueError as exc:
                primary_failure_class = "malformed_test_fixture"
                notes.append(str(exc))
            else:
                grading_executable = True
                grading_report_id = report["report_id"]
                grading_failure_class = report["evaluation"]["failure_class"]
                runtime_valid = bool(report["evaluation"]["passed"])
                if not runtime_valid:
                    primary_failure_class = self._classify_runtime_failure(
                        manifest=manifest,
                        tests=tests,
                        harness_path=harness_path if harness_path.exists() else None,
                        report=report,
                    )

        repairability = "none"
        if runtime_valid:
            structural_valid = True
            if proposed_repairs or advisory_classes:
                repairability = "advisory_only"
        elif primary_failure_class in SAFE_REPAIRABLE_FAILURES and proposed_repairs:
            repairability = "auto_repairable"
        else:
            repairability = "manual_content_repair"

        return ReferenceBundleAuditResult(
            exercise_id=exercise_id,
            bundle_root=str(bundle_root),
            pool_refs=pool_refs,
            structural_valid=structural_valid,
            runtime_valid=runtime_valid,
            required_files_present=required_files_present,
            reference_implementation_present=reference_present,
            generator_path_valid=generator_path_valid,
            harness_path_valid=harness_path_valid,
            compile_command_resolvable=compile_command_resolvable,
            tests_runnable=tests_runnable,
            grading_executable=grading_executable,
            primary_failure_class=primary_failure_class,
            grading_failure_class=grading_failure_class,
            repairability=repairability,
            advisory_classes=sorted(set(advisory_classes)),
            proposed_repairs=proposed_repairs,
            notes=notes,
            grading_report_id=grading_report_id,
        )

    def _bundle_root(self, repo_root: Path, exercise_id: str) -> Path:
        _, group, slug = exercise_id.split(".", 2)
        return repo_root / "datasets/exercises/exams" / group / slug

    def _directory_inventory(self, directory: Path) -> list[CatalogFile]:
        if not directory.exists() or not directory.is_dir():
            return []
        files: list[CatalogFile] = []
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            files.append(CatalogFile(relative_path=str(path.relative_to(directory)), absolute_path=path))
        return files

    def _resolve_origin_root(self, manifest: dict) -> tuple[Path | None, RepairProposal | None]:
        origin_path_value = str(manifest.get("source", {}).get("origin_path", ""))
        if not origin_path_value:
            return (None, None)
        exact = (self.workspace_root / origin_path_value).resolve()
        if exact.exists():
            return (exact, None)

        relative = Path(origin_path_value)
        parent = (self.workspace_root / relative.parent).resolve()
        if not parent.exists():
            return (None, None)
        target_key = self._normalize_slug(relative.name)
        candidates = [
            path
            for path in parent.iterdir()
            if path.is_dir() and self._normalize_slug(path.name) == target_key
        ]
        if len(candidates) != 1:
            return (None, None)
        resolved = candidates[0]
        proposal = RepairProposal(
            repair_class="legacy_path_normalization",
            source_path=str(relative),
            target_path=str(resolved.relative_to(self.workspace_root)),
            justification="resolved source.origin_path via unique normalized legacy directory match",
        )
        return (resolved, proposal)

    def _resolve_generator_path(self, origin_root: Path | None) -> dict[str, object]:
        if origin_root is None:
            return {"resolved": None, "proposal": None}
        exact = origin_root / "generator.py"
        if exact.exists():
            return {"resolved": exact, "proposal": None}
        fallback = origin_root / "genrator.py"
        if fallback.exists():
            return {
                "resolved": fallback,
                "proposal": RepairProposal(
                    repair_class="generator_filename_typo",
                    source_path=str(fallback),
                    target_path=str(exact),
                    justification="resolved generator.py via known legacy genrator.py typo",
                ),
            }
        candidates = sorted(
            path for path in origin_root.glob("*.py") if "generator" in self._normalize_slug(path.stem)
        )
        if len(candidates) == 1:
            return {
                "resolved": candidates[0],
                "proposal": RepairProposal(
                    repair_class="generator_filename_typo",
                    source_path=str(candidates[0]),
                    target_path=str(exact),
                    justification="resolved generator.py via unique normalized generator filename match",
                ),
            }
        return {"resolved": None, "proposal": None}

    def _resolve_harness_path(
        self,
        bundle_root: Path,
        tests_dir: Path,
        origin_root: Path | None,
        compile_mode: str,
    ) -> dict[str, object]:
        if compile_mode != "function_with_harness":
            return {"resolved": tests_dir / "main.c", "proposal": None}

        exact = tests_dir / "main.c"
        if exact.exists():
            return {"resolved": exact, "proposal": None}
        candidates = sorted(path for path in tests_dir.glob("*.c") if path.is_file())
        if len(candidates) == 1:
            return {
                "resolved": candidates[0],
                "proposal": RepairProposal(
                    repair_class="harness_main_discovery",
                    source_path=str(candidates[0]),
                    target_path=str(exact),
                    justification="resolved harness main.c via unique C source in tests directory",
                ),
            }
        if origin_root is not None:
            legacy_main = origin_root / "main.c"
            if legacy_main.exists():
                return {
                    "resolved": legacy_main,
                    "proposal": RepairProposal(
                        repair_class="harness_main_discovery",
                        source_path=str(legacy_main),
                        target_path=str(bundle_root / "tests/main.c"),
                        justification="resolved harness main.c from the legacy correction bundle",
                    ),
                }
        return {"resolved": None, "proposal": None}

    def _resolve_expected_filename_repairs(
        self,
        *,
        bundle_root: Path,
        expected_files: list[str],
        reference_files: list[CatalogFile],
        starter_files: list[CatalogFile],
    ) -> tuple[list[RepairProposal], list[str]]:
        repairs: list[RepairProposal] = []
        notes: list[str] = []
        reference_index = {item.relative_path: item.absolute_path for item in reference_files}
        starter_index = {item.relative_path: item.absolute_path for item in starter_files}
        for filename in expected_files:
            if filename not in reference_index:
                candidate = self._unique_filename_candidate(reference_files, filename)
                if candidate is not None:
                    repairs.append(
                        RepairProposal(
                            repair_class="alternate_filename_normalization",
                            source_path=str(candidate.absolute_path),
                            target_path=str(bundle_root / "reference" / filename),
                            justification="resolved expected reference filename via unique alternate C file",
                        )
                    )
                else:
                    notes.append(f"missing expected reference file: {filename}")
            if filename not in starter_index:
                candidate = self._unique_filename_candidate(starter_files, filename)
                if candidate is not None:
                    repairs.append(
                        RepairProposal(
                            repair_class="declared_filename_normalization",
                            source_path=str(candidate.absolute_path),
                            target_path=str(bundle_root / "starter" / filename),
                            justification="resolved expected starter filename via unique alternate starter file",
                        )
                    )
        return (repairs, notes)

    def _unique_filename_candidate(self, files: list[CatalogFile], expected_name: str) -> CatalogFile | None:
        c_files = [item for item in files if item.absolute_path.suffix == Path(expected_name).suffix]
        if len(c_files) == 1:
            return c_files[0]
        expected_key = self._normalize_slug(Path(expected_name).stem)
        normalized = [item for item in c_files if self._normalize_slug(Path(item.relative_path).stem) == expected_key]
        if len(normalized) == 1:
            return normalized[0]
        return None

    def _reference_sources_have_main(self, reference_dir: Path) -> bool:
        for path in reference_dir.glob("*.c"):
            if not path.is_file():
                continue
            if re.search(r"\bmain\s*\(", path.read_text(encoding="utf-8")):
                return True
        return False

    def _compile_command_resolvable(
        self,
        *,
        manifest: dict,
        reference_dir: Path,
        expected_files: list[str],
        harness_path: Path | None,
    ) -> bool:
        engine = GradingEngine(self.platform_root)
        language = engine._load_language_plugin()
        if language.validate({}, manifest):
            raise ValueError("; ".join(language.validate({}, manifest)))
        source_files = language.source_paths(reference_dir, expected_files)
        command = language.compile_command(
            manifest,
            source_files,
            harness_path if manifest.get("build", {}).get("compile_mode") == "function_with_harness" else None,
            self.platform_root / "runtime/reports/reference_bundle_audit.tmp.out",
        )
        return shutil.which(command[0]) is not None

    def _grade_reference_bundle(self, repo_root: Path, exercise_id: str) -> dict:
        isolated_root = repo_root / "runtime/cache" / "bundle_audit" / exercise_id.replace(".", "-")
        self._reset_directory(isolated_root)
        bundle_root = self._bundle_root(repo_root, exercise_id)
        target_bundle_root = self._bundle_root(isolated_root, exercise_id)
        target_bundle_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(bundle_root, target_bundle_root)
        shutil.copytree(
            self.platform_root / "core/grading/builtins",
            isolated_root / "core/grading/builtins",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            self.platform_root / "core/sandbox/profiles",
            isolated_root / "core/sandbox/profiles",
            dirs_exist_ok=True,
        )
        for relative in (
            "storage/sessions",
            "storage/attempts",
            "runtime/reports",
            "runtime/workspaces",
            "runtime/traces",
            "runtime/cache",
            "runtime/manual_submissions",
        ):
            (isolated_root / relative).mkdir(parents=True, exist_ok=True)

        engine = GradingEngine(isolated_root)
        context = AttemptContext(
            attempt_id=f"bundle-audit.{exercise_id.replace('.', '-')}",
            session_id=f"bundle-audit.{exercise_id.split('.')[1]}",
            user_id="reference.bundle.audit",
            exercise_id=exercise_id,
            variant_id="normal",
            mode="exam",
            pool_id=None,
            submission_root=self._bundle_root(isolated_root, exercise_id) / "reference",
            attempt_index_for_exercise=1,
        )
        return engine.grade_submission(context)

    def _classify_runtime_failure(self, *, manifest: dict, tests: list, harness_path: Path | None, report: dict) -> str:
        raw_failure = str(report["evaluation"]["failure_class"])
        compile_mode = str(manifest.get("build", {}).get("compile_mode", ""))
        if raw_failure == "compile_error":
            return "reference_compile_failure"
        if self._looks_like_fixture_mismatch(compile_mode=compile_mode, tests=tests, harness_path=harness_path):
            return "malformed_test_fixture"
        if raw_failure == "crash":
            return "runtime_crash"
        if raw_failure == "wrong_output":
            return "runtime_wrong_output"
        if raw_failure in {"timeout", "memory_limit"}:
            return "unknown_runtime_failure"
        return "unknown_runtime_failure"

    def _looks_like_fixture_mismatch(self, *, compile_mode: str, tests: list, harness_path: Path | None) -> bool:
        if not tests:
            return False
        if not all(not case.argv for case in tests):
            return False
        if compile_mode == "function_with_harness" and harness_path is not None and harness_path.exists():
            source = harness_path.read_text(encoding="utf-8")
            return bool(re.search(r"\b(ac|argc)\s*!=\s*[2-9]\d*", source))
        return False

    def _write_audit_reports(self, report: ReferenceBundleAuditReport) -> None:
        payload = report.to_dict()
        self.audit_reports_root.mkdir(parents=True, exist_ok=True)
        self._write_yaml(self.audit_report_path, payload)
        self._write_yaml(
            self.audit_reports_root / "failure_classification.latest.yml",
            {
                "counts_by_failure_class": payload["summary"]["counts_by_failure_class"],
                "results": [
                    {
                        "exercise_id": item.exercise_id,
                        "primary_failure_class": item.primary_failure_class,
                        "repairability": item.repairability,
                    }
                    for item in report.results
                    if item.primary_failure_class is not None
                ],
            },
        )
        self._write_yaml(
            self.audit_reports_root / "affected_pools.latest.yml",
            {
                "affected_pools_and_levels": payload["summary"]["affected_pools_and_levels"],
            },
        )

    def _write_audit_status(self, report: ReferenceBundleAuditReport) -> None:
        payload = report.to_dict()
        summary = payload["summary"]
        lines = [
            "# REFERENCE_BUNDLE_AUDIT_STATUS",
            "",
            f"- Generated at: `{report.generated_at}`",
            f"- Audit root: `{report.audit_root}`",
            f"- Total audited bundles: `{summary['total_audited_bundles']}`",
            f"- Runnable bundles: `{summary['runnable_bundles']}`",
            f"- Failing bundles: `{summary['failing_bundles']}`",
            "",
            "## Counts By Failure Class",
            "",
        ]
        if summary["counts_by_failure_class"]:
            for failure_class, count in summary["counts_by_failure_class"].items():
                lines.append(f"- `{failure_class}`: `{count}`")
        else:
            lines.append("- None")
        lines.extend(["", "## Affected Pools And Levels", ""])
        if summary["affected_pools_and_levels"]:
            for pool_id, levels in summary["affected_pools_and_levels"].items():
                levels_rendered = ", ".join(str(level) for level in levels)
                lines.append(f"- `{pool_id}`: levels `{levels_rendered}`")
        else:
            lines.append("- None")
        lines.extend(["", "## Failing Bundle Samples", ""])
        failing = [item for item in report.results if not item.runtime_valid]
        for item in failing[:20]:
            lines.append(
                f"- `{item.exercise_id}`: `{item.primary_failure_class}` "
                f"(repairability=`{item.repairability}`)"
            )
        if not failing:
            lines.append("- None")
        self.audit_status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
