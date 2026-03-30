"""Reusable migration service for legacy exam repositories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import ast
import hashlib
import re
import shutil
from pathlib import Path
from typing import Iterable

import yaml

from platform_catalog import CatalogService, CatalogValidationError


DIRECT_SOURCE_ORDER = (
    "Exam00",
    "Exam01",
    "Exam02",
    "ExamFinal",
)

ALIAS_SOURCE_ORDER = ("ExamPoolRevanced-main",)

DEFAULT_SOURCE_ORDER = DIRECT_SOURCE_ORDER + ALIAS_SOURCE_ORDER

EXAM_DIFFICULTY_LEVELS = {
    "exam00": 1,
    "exam01": 2,
    "exam02": 3,
    "examfinal": 4,
}

SUMMARY_SKIP_PREFIXES = (
    "Assignment name",
    "Expected files",
    "Allowed functions",
    "Version",
)


@dataclass(slots=True)
class MigrationIssue:
    """One migration anomaly or failure."""

    code: str
    severity: str
    source_id: str
    location: str
    message: str
    exam_group: str | None = None
    assignment: str | None = None
    pool_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "source_id": self.source_id,
            "location": self.location,
            "message": self.message,
            "exam_group": self.exam_group,
            "assignment": self.assignment,
            "pool_name": self.pool_name,
        }


@dataclass(slots=True)
class SourceInventory:
    """Legacy source inventory counts."""

    source_id: str
    root_path: str
    exam_group: str
    subject_count: int
    correction_count: int
    pool_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "root_path": self.root_path,
            "exam_group": self.exam_group,
            "subject_count": self.subject_count,
            "correction_count": self.correction_count,
            "pool_count": self.pool_count,
        }


@dataclass(slots=True)
class MigrationReport:
    """Full migration report."""

    generated_at: str
    workspace_root: str
    sources: list[SourceInventory]
    imported_exercises: list[dict[str, object]]
    imported_pools: list[dict[str, object]]
    issues: list[MigrationIssue]

    def to_dict(self) -> dict[str, object]:
        error_count = sum(1 for issue in self.issues if issue.severity == "error")
        warning_count = sum(1 for issue in self.issues if issue.severity == "warning")
        return {
            "generated_at": self.generated_at,
            "workspace_root": self.workspace_root,
            "summary": {
                "source_count": len(self.sources),
                "exercise_count": len(self.imported_exercises),
                "pool_count": len(self.imported_pools),
                "issue_count": len(self.issues),
                "error_count": error_count,
                "warning_count": warning_count,
            },
            "sources": [item.to_dict() for item in self.sources],
            "imported_exercises": self.imported_exercises,
            "imported_pools": self.imported_pools,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class RejectedEntry:
    """One rejected exercise or pool candidate for staged import."""

    kind: str
    identifier: str
    source_id: str
    location: str
    exam_group: str | None
    reasons: list[str]
    messages: list[str]
    assignment: str | None = None
    pool_name: str | None = None

    def output_path(self, rejected_root: Path) -> Path:
        group = self.exam_group or "unknown"
        safe_identifier = re.sub(r"[^a-zA-Z0-9._-]+", "-", self.identifier).strip("-") or "unknown"
        if safe_identifier.endswith(".yml"):
            safe_identifier = safe_identifier[:-4]
        return rejected_root / f"{self.kind}s" / group / f"{safe_identifier}.yml"

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "identifier": self.identifier,
            "source_id": self.source_id,
            "location": self.location,
            "exam_group": self.exam_group,
            "assignment": self.assignment,
            "pool_name": self.pool_name,
            "reasons": self.reasons,
            "messages": self.messages,
        }


@dataclass(slots=True)
class StagingValidationReport:
    """Validation result for one staged accepted dataset root."""

    ok: bool
    exercise_count: int
    pool_count: int
    failures: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "exercise_count": self.exercise_count,
            "pool_count": self.pool_count,
            "failure_count": len(self.failures),
            "failures": self.failures,
        }


@dataclass(slots=True)
class StagingImportReport:
    """Full staging import report with accepted, rejected, and validation output."""

    generated_at: str
    workspace_root: str
    staging_root: str
    canonical_source_precedence: dict[str, object]
    sources: list[SourceInventory]
    accepted_exercises: list[dict[str, object]]
    accepted_pools: list[dict[str, object]]
    rejected_entries: list[RejectedEntry]
    duplicate_sources: list[MigrationIssue]
    unresolved_references: list[MigrationIssue]
    blocking_errors: list[MigrationIssue]
    validation: StagingValidationReport
    issues: list[MigrationIssue]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "workspace_root": self.workspace_root,
            "staging_root": self.staging_root,
            "summary": {
                "source_count": len(self.sources),
                "accepted_exercise_count": len(self.accepted_exercises),
                "accepted_pool_count": len(self.accepted_pools),
                "rejected_count": len(self.rejected_entries),
                "duplicate_count": len(self.duplicate_sources),
                "unresolved_reference_count": len(self.unresolved_references),
                "blocking_error_count": len(self.blocking_errors) + len(self.validation.failures),
                "validation_ok": self.validation.ok,
            },
            "canonical_source_precedence": self.canonical_source_precedence,
            "sources": [item.to_dict() for item in self.sources],
            "accepted_exercises": self.accepted_exercises,
            "accepted_pools": self.accepted_pools,
            "rejected_entries": [item.to_dict() for item in self.rejected_entries],
            "duplicate_sources": [issue.to_dict() for issue in self.duplicate_sources],
            "unresolved_references": [issue.to_dict() for issue in self.unresolved_references],
            "blocking_errors": [issue.to_dict() for issue in self.blocking_errors],
            "validation": self.validation.to_dict(),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class LegacyExamSource:
    """One discovered legacy exam root."""

    source_id: str
    root_path: Path
    exam_group: str
    precedence: int

    @property
    def subjects_root(self) -> Path:
        return self.root_path / "subjects"

    @property
    def corrections_root(self) -> Path:
        return self.root_path / "corrections"

    @property
    def pools_root(self) -> Path:
        return self.root_path / "pools"


@dataclass(slots=True)
class NormalizedExerciseCandidate:
    """One normalized canonical exercise bundle ready to write."""

    exercise_id: str
    exam_group: str
    slug: str
    source_id: str
    manifest: dict[str, object]
    statement_markdown: str
    starter_files: dict[str, str]
    reference_files: dict[str, str]
    tests_manifest: dict[str, object]
    harness_source: str | None
    fingerprint: str

    def output_root(self, repository_root: Path) -> Path:
        return repository_root / "datasets/exercises/exams" / self.exam_group / self.slug

    def summary(self) -> dict[str, object]:
        return {
            "exercise_id": self.exercise_id,
            "exam_group": self.exam_group,
            "slug": self.slug,
            "source_id": self.source_id,
        }


@dataclass(slots=True)
class NormalizedPoolCandidate:
    """One normalized canonical pool bundle ready to write."""

    pool_id: str
    slug: str
    exam_group: str
    source_id: str
    manifest: dict[str, object]
    fingerprint: str

    def output_root(self, repository_root: Path) -> Path:
        return repository_root / "datasets/pools/exams" / self.slug

    def summary(self) -> dict[str, object]:
        return {
            "pool_id": self.pool_id,
            "exam_group": self.exam_group,
            "slug": self.slug,
            "source_id": self.source_id,
        }


@dataclass(slots=True)
class LegacyImportService:
    """Import legacy exam repositories into the canonical dataset layout."""

    workspace_root: Path
    source_order: tuple[str, ...] = DEFAULT_SOURCE_ORDER
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"))
    per_level_time_seconds: int = 900
    cooldown_seconds: int = 0

    def __post_init__(self) -> None:
        self.workspace_root = self.workspace_root.resolve()

    @property
    def platform_root(self) -> Path:
        return self.workspace_root / "platform"

    @property
    def report_path(self) -> Path:
        return self.platform_root / "runtime/reports/import_legacy/import_legacy.latest.yml"

    @property
    def staging_root(self) -> Path:
        return self.platform_root / "runtime/staging/import_legacy/latest"

    @property
    def staging_accepted_root(self) -> Path:
        return self.staging_root / "accepted"

    @property
    def staging_rejected_root(self) -> Path:
        return self.staging_root / "rejected"

    @property
    def staging_reports_root(self) -> Path:
        return self.staging_root / "reports"

    @property
    def staging_report_path(self) -> Path:
        return self.staging_reports_root / "staging_import.latest.yml"

    @property
    def staging_status_path(self) -> Path:
        return self.workspace_root / "STAGING_IMPORT_STATUS.md"

    def migrate(self, *, write: bool = True) -> MigrationReport:
        issues: list[MigrationIssue] = []
        sources = self.discover_sources(issues)
        inventories = [self._inventory_for_source(source) for source in sources]

        chosen_exercises = self._collect_exercises(sources, issues)
        chosen_pools = self._collect_pools(sources, chosen_exercises, issues)

        if write:
            self._write_exercises(chosen_exercises.values())
            self._write_pools(chosen_pools.values())

        report = MigrationReport(
            generated_at=self.generated_at,
            workspace_root=str(self.workspace_root),
            sources=inventories,
            imported_exercises=[candidate.summary() for candidate in chosen_exercises.values()],
            imported_pools=[candidate.summary() for candidate in chosen_pools.values()],
            issues=issues,
        )
        if write:
            self._write_report(report)
        return report

    def stage_import(self, *, write: bool = True) -> StagingImportReport:
        """Import legacy content into an isolated staging dataset root."""
        issues: list[MigrationIssue] = []
        sources = self.discover_sources(issues, source_order=DEFAULT_SOURCE_ORDER)
        inventories = [self._inventory_for_source(source) for source in sources]

        chosen_exercises = self._collect_exercises(sources, issues)
        chosen_pools = self._collect_pools(sources, chosen_exercises, issues)
        rejected_entries = self._build_rejected_entries(issues)
        duplicate_sources = [issue for issue in issues if issue.code.startswith("duplicate_source_")]
        unresolved_references = [issue for issue in issues if issue.code == "bad_pool_reference"]
        blocking_errors = [issue for issue in issues if issue.severity == "error"]
        validation = StagingValidationReport(ok=False, exercise_count=0, pool_count=0, failures=[])

        if write:
            self._reset_directory(self.staging_root)
            self._write_exercises(chosen_exercises.values(), self.staging_accepted_root)
            self._write_pools(chosen_pools.values(), self.staging_accepted_root)
            self._write_rejected_entries(rejected_entries)
            validation = self._validate_staged_catalog()

        report = StagingImportReport(
            generated_at=self.generated_at,
            workspace_root=str(self.workspace_root),
            staging_root=str(self.staging_root),
            canonical_source_precedence={
                "canonical_source_of_truth": list(DIRECT_SOURCE_ORDER),
                "alias_duplicate_source": "ExamPoolRevanced-main/<ExamXX>",
                "import_rule": "prefer direct Exam00/Exam01/Exam02/ExamFinal trees; use ExamPoolRevanced-main copies only as fallback when the direct tree is absent",
                "conflict_rule": "never merge conflicting duplicates; keep the higher-precedence source and report the lower-precedence entry as a blocking conflict",
            },
            sources=inventories,
            accepted_exercises=[candidate.summary() for candidate in chosen_exercises.values()],
            accepted_pools=[candidate.summary() for candidate in chosen_pools.values()],
            rejected_entries=rejected_entries,
            duplicate_sources=duplicate_sources,
            unresolved_references=unresolved_references,
            blocking_errors=blocking_errors,
            validation=validation,
            issues=issues,
        )
        if write:
            self._write_stage_reports(report)
            self._write_staging_status(report)
        return report

    def discover_sources(
        self,
        issues: list[MigrationIssue] | None = None,
        *,
        source_order: tuple[str, ...] | None = None,
    ) -> list[LegacyExamSource]:
        issues = issues if issues is not None else []
        discovered: list[LegacyExamSource] = []
        precedence = 0
        order = source_order or self.source_order
        for source_name in order:
            root = self.workspace_root / source_name
            if not root.exists():
                issues.append(
                    MigrationIssue(
                        code="missing_source_root",
                        severity="warning",
                        source_id=source_name,
                        location=str(root),
                        message="configured legacy source root is missing",
                    )
                )
                precedence += 1
                continue
            if self._is_exam_root(root):
                exam_group = self._normalize_exam_group(root.name)
                if exam_group is not None:
                    discovered.append(
                        LegacyExamSource(
                            source_id=source_name,
                            root_path=root,
                            exam_group=exam_group,
                            precedence=precedence,
                        )
                    )
            else:
                for child in sorted(item for item in root.iterdir() if item.is_dir()):
                    exam_group = self._normalize_exam_group(child.name)
                    if exam_group is None or not self._is_exam_root(child):
                        continue
                    discovered.append(
                        LegacyExamSource(
                            source_id=f"{source_name}/{child.name}",
                            root_path=child,
                            exam_group=exam_group,
                            precedence=precedence,
                        )
                    )
            precedence += 1
        return discovered

    def _collect_exercises(
        self,
        sources: list[LegacyExamSource],
        issues: list[MigrationIssue],
    ) -> dict[str, NormalizedExerciseCandidate]:
        chosen: dict[str, NormalizedExerciseCandidate] = {}
        for source in sources:
            subject_names = self._directory_names(source.subjects_root)
            correction_names = self._directory_names(source.corrections_root)
            for assignment in sorted(subject_names - correction_names):
                subject_path = source.subjects_root / assignment / "subject.en.txt"
                issues.extend(
                    [
                        MigrationIssue(
                            code="naming_mismatch",
                            severity="error",
                            source_id=source.source_id,
                            location=str(subject_path),
                            message="subject exists without matching correction bundle",
                            exam_group=source.exam_group,
                            assignment=assignment,
                        ),
                        MigrationIssue(
                            code="missing_file",
                            severity="error",
                            source_id=source.source_id,
                            location=str(source.corrections_root / assignment),
                            message="missing correction bundle for subject",
                            exam_group=source.exam_group,
                            assignment=assignment,
                        ),
                    ]
                )
            for assignment in sorted(correction_names - subject_names):
                correction_path = source.corrections_root / assignment
                issues.extend(
                    [
                        MigrationIssue(
                            code="naming_mismatch",
                            severity="error",
                            source_id=source.source_id,
                            location=str(correction_path),
                            message="correction bundle exists without matching subject",
                            exam_group=source.exam_group,
                            assignment=assignment,
                        ),
                        MigrationIssue(
                            code="missing_file",
                            severity="error",
                            source_id=source.source_id,
                            location=str(source.subjects_root / assignment / "subject.en.txt"),
                            message="missing subject file for correction bundle",
                            exam_group=source.exam_group,
                            assignment=assignment,
                        ),
                    ]
                )

            for assignment in sorted(subject_names & correction_names):
                candidate = self._build_exercise_candidate(source, assignment, issues)
                if candidate is None:
                    continue
                existing = chosen.get(candidate.exercise_id)
                if existing is None:
                    chosen[candidate.exercise_id] = candidate
                    continue
                if existing.fingerprint != candidate.fingerprint:
                    issues.append(
                        MigrationIssue(
                            code="duplicate_source_conflict",
                            severity="error",
                            source_id=source.source_id,
                            location=str(source.corrections_root / assignment),
                            message=f"duplicate assignment conflicts with earlier source {existing.source_id!r}",
                            exam_group=source.exam_group,
                            assignment=assignment,
                        )
                    )
                else:
                    issues.append(
                        MigrationIssue(
                            code="duplicate_source_duplicate",
                            severity="warning",
                            source_id=source.source_id,
                            location=str(source.corrections_root / assignment),
                            message=f"duplicate assignment matches earlier source {existing.source_id!r}",
                            exam_group=source.exam_group,
                            assignment=assignment,
                        )
                    )
        return chosen

    def _collect_pools(
        self,
        sources: list[LegacyExamSource],
        exercises: dict[str, NormalizedExerciseCandidate],
        issues: list[MigrationIssue],
    ) -> dict[str, NormalizedPoolCandidate]:
        valid_exercise_ids = set(exercises)
        chosen: dict[str, NormalizedPoolCandidate] = {}
        for source in sources:
            for pool_path in sorted(source.pools_root.glob("*.yml")):
                candidate = self._build_pool_candidate(source, pool_path, valid_exercise_ids, issues)
                if candidate is None:
                    continue
                existing = chosen.get(candidate.pool_id)
                if existing is None:
                    chosen[candidate.pool_id] = candidate
                    continue
                if existing.fingerprint != candidate.fingerprint:
                    issues.append(
                        MigrationIssue(
                            code="duplicate_source_conflict",
                            severity="error",
                            source_id=source.source_id,
                            location=str(pool_path),
                            message=f"duplicate pool conflicts with earlier source {existing.source_id!r}",
                            exam_group=source.exam_group,
                            pool_name=pool_path.name,
                        )
                    )
                else:
                    issues.append(
                        MigrationIssue(
                            code="duplicate_source_duplicate",
                            severity="warning",
                            source_id=source.source_id,
                            location=str(pool_path),
                            message=f"duplicate pool matches earlier source {existing.source_id!r}",
                            exam_group=source.exam_group,
                            pool_name=pool_path.name,
                        )
                    )
        return chosen

    def _inventory_for_source(self, source: LegacyExamSource) -> SourceInventory:
        return SourceInventory(
            source_id=source.source_id,
            root_path=str(source.root_path),
            exam_group=source.exam_group,
            subject_count=len(self._directory_names(source.subjects_root)),
            correction_count=len(self._directory_names(source.corrections_root)),
            pool_count=len(list(source.pools_root.glob("*.yml"))),
        )

    def _build_exercise_candidate(
        self,
        source: LegacyExamSource,
        assignment: str,
        issues: list[MigrationIssue],
    ) -> NormalizedExerciseCandidate | None:
        subject_path = self._resolve_subject_path(source.subjects_root / assignment)
        correction_root = source.corrections_root / assignment
        profile_path = correction_root / "profile.yml"
        generator_path = self._resolve_generator_path(correction_root)

        subject_text = self._read_text(subject_path, issues, source, assignment, code="missing_file", message="missing subject file")
        if subject_text is None:
            return None

        profile = self._read_yaml(profile_path, issues, source, assignment)
        if profile is None:
            issues.append(
                MigrationIssue(
                    code="malformed_correction_bundle",
                    severity="error",
                    source_id=source.source_id,
                    location=str(profile_path),
                    message="unable to load correction profile",
                    exam_group=source.exam_group,
                    assignment=assignment,
                )
            )
            return None

        generator_text = self._read_text(generator_path, issues, source, assignment, code="missing_file", message="missing generator.py")
        if generator_text is None:
            issues.append(
                MigrationIssue(
                    code="malformed_generator",
                    severity="error",
                    source_id=source.source_id,
                    location=str(generator_path),
                    message="generator.py is required for legacy correction bundles",
                    exam_group=source.exam_group,
                    assignment=assignment,
                )
            )
            return None
        try:
            ast.parse(generator_text)
        except SyntaxError as exc:
            issues.append(
                MigrationIssue(
                    code="malformed_generator",
                    severity="error",
                    source_id=source.source_id,
                    location=str(generator_path),
                    message=f"generator.py is not valid Python: {exc.msg}",
                    exam_group=source.exam_group,
                    assignment=assignment,
                )
            )
            return None

        user_files = self._normalize_string_list(profile.get("user_files"))
        common_files = self._normalize_string_list(profile.get("common_files"))
        allowed_functions = self._normalize_string_list(profile.get("white_list"))
        if not user_files:
            issues.append(
                MigrationIssue(
                    code="malformed_correction_bundle",
                    severity="error",
                    source_id=source.source_id,
                    location=str(profile_path),
                    message="profile.yml must declare at least one user file",
                    exam_group=source.exam_group,
                    assignment=assignment,
                )
            )
            return None

        if any(name != "main.c" for name in common_files):
            issues.append(
                MigrationIssue(
                    code="malformed_correction_bundle",
                    severity="error",
                    source_id=source.source_id,
                    location=str(profile_path),
                    message="common_files currently only supports main.c during migration",
                    exam_group=source.exam_group,
                    assignment=assignment,
                )
            )
            return None

        reference_files: dict[str, str] = {}
        resolved_user_files: list[str] = []
        for filename in user_files:
            resolved_name, path = self._resolve_reference_file_path(correction_root, assignment, filename)
            content = self._read_text(
                path,
                issues,
                source,
                assignment,
                code="missing_file",
                message="declared legacy user file is missing",
            )
            if content is None:
                issues.append(
                    MigrationIssue(
                        code="malformed_correction_bundle",
                        severity="error",
                        source_id=source.source_id,
                        location=str(path),
                        message="correction bundle is missing a declared user file",
                        exam_group=source.exam_group,
                        assignment=assignment,
                    )
                )
                return None
            reference_files[resolved_name] = content
            resolved_user_files.append(resolved_name)

        if not common_files and (correction_root / "main.c").exists():
            if not any(re.search(r"\bmain\s*\(", content) for content in reference_files.values()):
                common_files = ["main.c"]

        harness_source: str | None = None
        if common_files:
            harness_path = correction_root / "main.c"
            harness_source = self._read_text(
                harness_path,
                issues,
                source,
                assignment,
                code="missing_file",
                message="declared legacy common main.c is missing",
            )
            if harness_source is None:
                issues.append(
                    MigrationIssue(
                        code="malformed_correction_bundle",
                        severity="error",
                        source_id=source.source_id,
                        location=str(harness_path),
                        message="correction bundle declares main.c but the file is missing",
                        exam_group=source.exam_group,
                        assignment=assignment,
                    )
                )
                return None

        compile_mode = self._resolve_compile_mode(reference_files.values(), harness_source)
        if compile_mode is None:
            issues.append(
                MigrationIssue(
                    code="malformed_correction_bundle",
                    severity="error",
                    source_id=source.source_id,
                    location=str(correction_root),
                    message="unable to determine whether bundle is function_with_harness or standalone_program",
                    exam_group=source.exam_group,
                    assignment=assignment,
                )
            )
            return None

        required_headers = sorted(
            self._extract_headers(list(reference_files.values()) + ([harness_source] if harness_source is not None else []))
        )
        starter_files = {
            filename: f"/* Legacy import placeholder starter for {filename}. */\n"
            for filename in resolved_user_files
        }
        slug = self._normalize_slug(assignment)
        exercise_id = f"exams.{source.exam_group}.{slug}"
        summary = self._extract_summary(subject_text) or f"Migrated legacy exam assignment {slug}."
        statement_markdown = self._statement_markdown(slug, subject_text)

        manifest: dict[str, object] = {
            "schema_version": 1,
            "id": exercise_id,
            "slug": slug,
            "title": profile.get("name", assignment),
            "summary": summary,
            "track": "exams",
            "group": source.exam_group,
            "source": {
                "kind": "legacy_import",
                "origin_id": f"{source.exam_group}.{assignment}",
                "origin_path": str(correction_root.relative_to(self.workspace_root)),
                "copyright_status": "legacy_migrated",
            },
            "language": "c",
            "difficulty": {
                "level": EXAM_DIFFICULTY_LEVELS.get(source.exam_group, 1),
                "category": "exam",
            },
            "pedagogy": {
                "modes": ["practice", "exam"],
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
                "expected_files": resolved_user_files,
                "allowed_functions": allowed_functions,
                "forbidden_functions": [],
                "required_headers": required_headers,
                "output_contract": {
                    "channel": "stdout",
                    "newline_policy": "ignore",
                },
                "norm": {
                    "enabled": False,
                },
            },
            "build": {
                "compiler": "gcc",
                "standard": "c11",
                "flags": ["-Wall", "-Wextra", "-Werror"],
                "link_flags": [],
                "compile_mode": compile_mode,
                "entry_files": resolved_user_files,
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
                "pass_policy": {
                    "mode": "all_tests",
                    "threshold": 1.0,
                },
                "edge_case_suite_id": f"legacy.{source.exam_group}.{slug}",
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
                        "description": "Migrated legacy baseline variant.",
                    }
                ],
            },
            "metadata": {
                "author": "platform.import_legacy",
                "reviewers": [],
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "migrated",
            },
        }
        tests_manifest = {
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
        fingerprint = self._fingerprint(
            subject_text,
            yaml.safe_dump(profile, sort_keys=True),
            generator_text,
            yaml.safe_dump(manifest, sort_keys=True),
            *(f"{name}:{content}" for name, content in sorted(reference_files.items())),
            harness_source or "",
        )
        return NormalizedExerciseCandidate(
            exercise_id=exercise_id,
            exam_group=source.exam_group,
            slug=slug,
            source_id=source.source_id,
            manifest=manifest,
            statement_markdown=statement_markdown,
            starter_files=starter_files,
            reference_files=reference_files,
            tests_manifest=tests_manifest,
            harness_source=harness_source,
            fingerprint=fingerprint,
        )

    def _build_pool_candidate(
        self,
        source: LegacyExamSource,
        pool_path: Path,
        valid_exercise_ids: set[str],
        issues: list[MigrationIssue],
    ) -> NormalizedPoolCandidate | None:
        payload = self._read_yaml(pool_path, issues, source, assignment=None, pool_name=pool_path.name)
        if payload is None:
            return None
        raw_levels = payload.get("levels")
        if not isinstance(raw_levels, list) or not raw_levels:
            issues.append(
                MigrationIssue(
                    code="malformed_pool",
                    severity="error",
                    source_id=source.source_id,
                    location=str(pool_path),
                    message="legacy pool must contain a non-empty levels list",
                    exam_group=source.exam_group,
                    pool_name=pool_path.name,
                )
            )
            return None

        pool_slug = self._normalize_slug(pool_path.stem)
        levels: list[dict[str, object]] = []
        invalid = False
        for level_index, item in enumerate(raw_levels):
            assignments = item.get("assignments") if isinstance(item, dict) else None
            if not isinstance(assignments, list) or not assignments:
                issues.append(
                    MigrationIssue(
                        code="malformed_pool",
                        severity="error",
                        source_id=source.source_id,
                        location=str(pool_path),
                        message=f"legacy level {level_index} must declare a non-empty assignments list",
                        exam_group=source.exam_group,
                        pool_name=pool_path.name,
                    )
                )
                invalid = True
                continue
            exercise_refs: list[dict[str, object]] = []
            for assignment_name in assignments:
                if not isinstance(assignment_name, str) or not assignment_name.strip():
                    issues.append(
                        MigrationIssue(
                            code="malformed_pool",
                            severity="error",
                            source_id=source.source_id,
                            location=str(pool_path),
                            message=f"legacy level {level_index} contains an invalid assignment reference",
                            exam_group=source.exam_group,
                            pool_name=pool_path.name,
                        )
                    )
                    invalid = True
                    continue
                exercise_id = f"exams.{source.exam_group}.{self._normalize_slug(assignment_name)}"
                if exercise_id not in valid_exercise_ids:
                    issues.append(
                        MigrationIssue(
                            code="bad_pool_reference",
                            severity="error",
                            source_id=source.source_id,
                            location=str(pool_path),
                            message=f"pool references unknown or rejected assignment {assignment_name!r}",
                            exam_group=source.exam_group,
                            assignment=assignment_name,
                            pool_name=pool_path.name,
                        )
                    )
                    invalid = True
                    continue
                exercise_refs.append({"exercise_id": exercise_id, "variant": "normal", "weight": 1})
            levels.append(
                {
                    "level": level_index,
                    "title": f"Legacy Level {level_index}",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": self.per_level_time_seconds,
                    "unlock_if": {
                        "all_of": [] if level_index == 0 else [level_index - 1],
                        "any_of": [],
                    },
                    "exercise_refs": exercise_refs,
                }
            )
        if invalid:
            return None

        total_time_seconds = self.per_level_time_seconds * len(levels)
        manifest: dict[str, object] = {
            "schema_version": 1,
            "id": f"exams.{source.exam_group}.{pool_slug}",
            "title": f"{source.exam_group.upper()} {pool_path.stem}",
            "track": "exams",
            "mode": "practice" if bool(payload.get("practice")) else "exam",
            "description": f"Migrated legacy pool from {source.source_id}.",
            "selection": {
                "strategy": "random",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": total_time_seconds,
                "per_level_time_seconds": self.per_level_time_seconds,
                "cooldown": {
                    "enabled": self.cooldown_seconds > 0,
                    "seconds": self.cooldown_seconds,
                    "scope": "pool",
                },
            },
            "levels": levels,
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "migrated",
            },
        }
        return NormalizedPoolCandidate(
            pool_id=str(manifest["id"]),
            slug=pool_slug,
            exam_group=source.exam_group,
            source_id=source.source_id,
            manifest=manifest,
            fingerprint=self._fingerprint(yaml.safe_dump(payload, sort_keys=True), yaml.safe_dump(manifest, sort_keys=True)),
        )

    def _write_exercises(
        self,
        exercises: Iterable[NormalizedExerciseCandidate],
        repository_root: Path | None = None,
    ) -> None:
        target_root = repository_root or self.platform_root
        for candidate in exercises:
            root = candidate.output_root(target_root)
            starter_root = root / "starter"
            reference_root = root / "reference"
            tests_root = root / "tests"
            starter_root.mkdir(parents=True, exist_ok=True)
            reference_root.mkdir(parents=True, exist_ok=True)
            tests_root.mkdir(parents=True, exist_ok=True)
            self._write_yaml(root / "exercise.yml", candidate.manifest)
            (root / "statement.md").write_text(candidate.statement_markdown, encoding="utf-8")
            self._write_files(starter_root, candidate.starter_files)
            self._write_files(reference_root, candidate.reference_files)
            self._write_yaml(tests_root / "tests.yml", candidate.tests_manifest)
            harness_path = tests_root / "main.c"
            if candidate.harness_source is not None:
                harness_path.write_text(candidate.harness_source, encoding="utf-8")
            elif harness_path.exists():
                harness_path.unlink()

    def _write_pools(
        self,
        pools: Iterable[NormalizedPoolCandidate],
        repository_root: Path | None = None,
    ) -> None:
        target_root = repository_root or self.platform_root
        for candidate in pools:
            root = candidate.output_root(target_root)
            root.mkdir(parents=True, exist_ok=True)
            self._write_yaml(root / "pool.yml", candidate.manifest)

    def _write_report(self, report: MigrationReport) -> None:
        report_path = self.report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_yaml(report_path, report.to_dict())

    def _write_rejected_entries(self, entries: Iterable[RejectedEntry]) -> None:
        for entry in entries:
            path = entry.output_path(self.staging_rejected_root)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._write_yaml(path, entry.to_dict())

    def _write_stage_reports(self, report: StagingImportReport) -> None:
        self.staging_reports_root.mkdir(parents=True, exist_ok=True)
        self._write_yaml(self.staging_report_path, report.to_dict())
        self._write_yaml(
            self.staging_reports_root / "accepted_exercises.latest.yml",
            {"accepted_exercises": report.accepted_exercises},
        )
        self._write_yaml(
            self.staging_reports_root / "accepted_pools.latest.yml",
            {"accepted_pools": report.accepted_pools},
        )
        self._write_yaml(
            self.staging_reports_root / "rejected_entries.latest.yml",
            {"rejected_entries": [entry.to_dict() for entry in report.rejected_entries]},
        )
        self._write_yaml(
            self.staging_reports_root / "duplicate_sources.latest.yml",
            {
                "precedence": report.canonical_source_precedence,
                "duplicates": [issue.to_dict() for issue in report.duplicate_sources],
            },
        )
        self._write_yaml(
            self.staging_reports_root / "unresolved_references.latest.yml",
            {"unresolved_references": [issue.to_dict() for issue in report.unresolved_references]},
        )
        self._write_yaml(
            self.staging_reports_root / "validation.latest.yml",
            report.validation.to_dict(),
        )

    def _write_staging_status(self, report: StagingImportReport) -> None:
        summary = report.to_dict()["summary"]
        validation = report.validation
        lines = [
            "# Staging Import Status",
            "",
            f"- Generated at: `{report.generated_at}`",
            f"- Staging root: `{report.staging_root}`",
            "- Canonical source of truth: direct `Exam00`, `Exam01`, `Exam02`, and `ExamFinal` trees",
            "- Alias source layer: `ExamPoolRevanced-main/<ExamXX>` fallback only",
            "",
            "## Summary",
            "",
            f"- imported exercise count: {summary['accepted_exercise_count']}",
            f"- imported pool count: {summary['accepted_pool_count']}",
            f"- rejected count: {summary['rejected_count']}",
            f"- duplicate count: {summary['duplicate_count']}",
            f"- unresolved references: {summary['unresolved_reference_count']}",
            f"- blocking errors: {summary['blocking_error_count']}",
            "",
            "## Validation",
            "",
            f"- catalog validation: {'passed' if validation.ok else 'failed'}",
            f"- validated exercise count: {validation.exercise_count}",
            f"- validated pool count: {validation.pool_count}",
            f"- validation failures: {len(validation.failures)}",
        ]
        if report.blocking_errors:
            lines.extend(
                [
                    "",
                    "## Blocking Error Samples",
                    "",
                ]
            )
            for issue in report.blocking_errors[:10]:
                lines.append(f"- `{issue.code}` in `{issue.source_id}` at `{issue.location}`")
        if validation.failures:
            lines.extend(
                [
                    "",
                    "## Validation Failure Samples",
                    "",
                ]
            )
            for failure in validation.failures[:10]:
                lines.append(f"- `{failure['location']}`: {failure['message']}")
        self.staging_status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _validate_staged_catalog(self) -> StagingValidationReport:
        catalog = CatalogService(self.staging_accepted_root)
        try:
            exercises = catalog.list_exercises()
            pools = catalog.list_pools()
        except CatalogValidationError as exc:
            return StagingValidationReport(
                ok=False,
                exercise_count=0,
                pool_count=0,
                failures=[{"location": failure.location, "message": failure.message} for failure in exc.failures],
            )
        return StagingValidationReport(
            ok=True,
            exercise_count=len(exercises),
            pool_count=len(pools),
            failures=[],
        )

    def _build_rejected_entries(self, issues: list[MigrationIssue]) -> list[RejectedEntry]:
        grouped: dict[tuple[str, str, str | None, str], RejectedEntry] = {}
        for issue in issues:
            if issue.severity != "error":
                continue
            kind = "pool" if issue.pool_name else "exercise" if issue.assignment else "source"
            identifier = issue.pool_name or issue.assignment or Path(issue.location).name
            key = (kind, issue.source_id, issue.exam_group, identifier)
            existing = grouped.get(key)
            if existing is None:
                grouped[key] = RejectedEntry(
                    kind=kind,
                    identifier=identifier,
                    source_id=issue.source_id,
                    location=issue.location,
                    exam_group=issue.exam_group,
                    reasons=[issue.code],
                    messages=[issue.message],
                    assignment=issue.assignment,
                    pool_name=issue.pool_name,
                )
                continue
            if issue.code not in existing.reasons:
                existing.reasons.append(issue.code)
            if issue.message not in existing.messages:
                existing.messages.append(issue.message)
        return sorted(grouped.values(), key=lambda item: (item.kind, item.exam_group or "", item.identifier, item.source_id))

    def _reset_directory(self, path: Path) -> None:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)

    def _write_files(self, root: Path, files: dict[str, str]) -> None:
        for relative_path, content in files.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _write_yaml(self, path: Path, payload: object) -> None:
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _read_text(
        self,
        path: Path,
        issues: list[MigrationIssue],
        source: LegacyExamSource,
        assignment: str | None,
        *,
        code: str,
        message: str,
    ) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            issues.append(
                MigrationIssue(
                    code=code,
                    severity="error",
                    source_id=source.source_id,
                    location=str(path),
                    message=message,
                    exam_group=source.exam_group,
                    assignment=assignment,
                )
            )
            return None

    def _read_yaml(
        self,
        path: Path,
        issues: list[MigrationIssue],
        source: LegacyExamSource,
        assignment: str | None,
        pool_name: str | None = None,
    ) -> dict[str, object] | None:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except FileNotFoundError:
            issues.append(
                MigrationIssue(
                    code="missing_file",
                    severity="error",
                    source_id=source.source_id,
                    location=str(path),
                    message="missing YAML file",
                    exam_group=source.exam_group,
                    assignment=assignment,
                    pool_name=pool_name,
                )
            )
            return None
        except yaml.YAMLError as exc:
            issues.append(
                MigrationIssue(
                    code="malformed_yaml",
                    severity="error",
                    source_id=source.source_id,
                    location=str(path),
                    message=f"invalid YAML: {exc}",
                    exam_group=source.exam_group,
                    assignment=assignment,
                    pool_name=pool_name,
                )
            )
            return None
        if not isinstance(payload, dict):
            issues.append(
                MigrationIssue(
                    code="malformed_yaml",
                    severity="error",
                    source_id=source.source_id,
                    location=str(path),
                    message="YAML root must be a mapping",
                    exam_group=source.exam_group,
                    assignment=assignment,
                    pool_name=pool_name,
                )
            )
            return None
        return payload

    def _resolve_subject_path(self, subject_root: Path) -> Path:
        primary = subject_root / "subject.en.txt"
        if primary.exists():
            return primary
        assignment = subject_root.name
        for candidate in (
            subject_root / f"{assignment}.en.txt",
            subject_root / f"{assignment}.txt",
        ):
            if candidate.exists():
                return candidate
        for pattern in ("*.en.txt", "*.txt"):
            matches = sorted(path for path in subject_root.glob(pattern) if path.is_file())
            if len(matches) == 1:
                return matches[0]
        return primary

    def _resolve_generator_path(self, correction_root: Path) -> Path:
        primary = correction_root / "generator.py"
        if primary.exists():
            return primary
        fallback = correction_root / "genrator.py"
        if fallback.exists():
            return fallback
        return primary

    def _resolve_reference_file_path(
        self,
        correction_root: Path,
        assignment: str,
        declared_filename: str,
    ) -> tuple[str, Path]:
        primary = correction_root / declared_filename
        if primary.exists():
            return (declared_filename, primary)

        assignment_candidate = correction_root / f"{assignment}.c"
        if assignment_candidate.exists():
            return (assignment_candidate.name, assignment_candidate)

        candidates = sorted(
            path
            for path in correction_root.glob("*.c")
            if path.is_file() and path.name != "main.c"
        )
        if len(candidates) == 1:
            return (candidates[0].name, candidates[0])
        return (declared_filename, primary)

    def _resolve_compile_mode(self, reference_sources: Iterable[str], harness_source: str | None) -> str | None:
        has_main = any(re.search(r"\bmain\s*\(", content) for content in reference_sources)
        if harness_source is not None and not has_main:
            return "function_with_harness"
        if harness_source is None and has_main:
            return "standalone_program"
        return None

    def _statement_markdown(self, slug: str, subject_text: str) -> str:
        title = slug.replace("_", " ")
        return f"# {title}\n\n```text\n{subject_text.rstrip()}\n```\n"

    def _extract_summary(self, subject_text: str) -> str:
        for raw_line in subject_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if any(line.startswith(prefix) for prefix in SUMMARY_SKIP_PREFIXES):
                continue
            if set(line) == {"-"}:
                continue
            return line
        return ""

    def _extract_headers(self, contents: Iterable[str]) -> set[str]:
        headers: set[str] = set()
        for content in contents:
            for match in re.findall(r'#include\s*[<"]([^">]+)[">]', content):
                headers.add(match)
        return headers

    def _normalize_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _normalize_slug(self, value: str) -> str:
        lowered = value.strip().lower()
        lowered = re.sub(r"[^a-z0-9._-]+", "-", lowered)
        return lowered.strip("-")

    def _normalize_exam_group(self, value: str) -> str | None:
        lowered = value.strip().lower()
        if lowered in EXAM_DIFFICULTY_LEVELS:
            return lowered
        return None

    def _directory_names(self, root: Path) -> set[str]:
        if not root.exists():
            return set()
        return {item.name for item in root.iterdir() if item.is_dir()}

    def _is_exam_root(self, path: Path) -> bool:
        return (path / "subjects").is_dir() and (path / "corrections").is_dir()

    def _fingerprint(self, *parts: str) -> str:
        digest = hashlib.sha256()
        for part in parts:
            digest.update(part.encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()
