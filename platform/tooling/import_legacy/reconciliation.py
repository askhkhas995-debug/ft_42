"""Second-pass reconciliation and pool repair for staged legacy exam imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil

import yaml

from platform_catalog import CatalogService, CatalogValidationError

try:
    from .service import (
        DEFAULT_SOURCE_ORDER,
        LegacyExamSource,
        LegacyImportService,
        MigrationIssue,
        NormalizedPoolCandidate,
        StagingValidationReport,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from service import (  # type: ignore
        DEFAULT_SOURCE_ORDER,
        LegacyExamSource,
        LegacyImportService,
        MigrationIssue,
        NormalizedPoolCandidate,
        StagingValidationReport,
    )


@dataclass(slots=True)
class AliasMapping:
    """One explicit legacy-name to canonical-exercise mapping."""

    exam_group: str
    legacy_assignment_name: str
    canonical_exercise_id: str
    canonical_slug: str
    reason: str
    source_issue_codes: list[str] = field(default_factory=list)
    source_locations: list[str] = field(default_factory=list)

    def key(self) -> tuple[str, str]:
        return (self.exam_group, self.legacy_assignment_name)

    def to_dict(self) -> dict[str, object]:
        return {
            "exam_group": self.exam_group,
            "legacy_assignment_name": self.legacy_assignment_name,
            "canonical_exercise_id": self.canonical_exercise_id,
            "canonical_slug": self.canonical_slug,
            "reason": self.reason,
            "source_issue_codes": self.source_issue_codes,
            "source_locations": self.source_locations,
        }


@dataclass(slots=True)
class AmbiguousMapping:
    """A legacy name that matched multiple possible canonical targets."""

    exam_group: str
    legacy_assignment_name: str
    candidate_exercise_ids: list[str]
    reason: str
    source_issue_codes: list[str] = field(default_factory=list)
    source_locations: list[str] = field(default_factory=list)

    def key(self) -> tuple[str, str]:
        return (self.exam_group, self.legacy_assignment_name)

    def to_dict(self) -> dict[str, object]:
        return {
            "exam_group": self.exam_group,
            "legacy_assignment_name": self.legacy_assignment_name,
            "candidate_exercise_ids": self.candidate_exercise_ids,
            "reason": self.reason,
            "source_issue_codes": self.source_issue_codes,
            "source_locations": self.source_locations,
        }


@dataclass(slots=True)
class AutoRepairedReference:
    """One pool reference repaired through an explicit alias mapping."""

    source_id: str
    exam_group: str
    pool_name: str
    level: int
    original_assignment_name: str
    canonical_exercise_id: str
    mapping_reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "exam_group": self.exam_group,
            "pool_name": self.pool_name,
            "level": self.level,
            "original_assignment_name": self.original_assignment_name,
            "canonical_exercise_id": self.canonical_exercise_id,
            "mapping_reason": self.mapping_reason,
        }


@dataclass(slots=True)
class RepairedPoolSummary:
    """One repaired pool candidate written during reconciliation."""

    pool_id: str
    source_id: str
    exam_group: str
    slug: str
    repaired_reference_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "pool_id": self.pool_id,
            "source_id": self.source_id,
            "exam_group": self.exam_group,
            "slug": self.slug,
            "repaired_reference_count": self.repaired_reference_count,
        }


@dataclass(slots=True)
class ReconciliationReport:
    """Aggregate reconciliation report for staged imports."""

    generated_at: str
    staging_root: str
    canonical_sources: dict[str, str]
    issue_classification: list[dict[str, object]]
    alias_mappings: list[AliasMapping]
    auto_repaired_references: list[AutoRepairedReference]
    unresolved_references_remaining: list[MigrationIssue]
    ambiguous_mappings: list[AmbiguousMapping]
    repaired_pools: list[RepairedPoolSummary]
    validation: StagingValidationReport

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "staging_root": self.staging_root,
            "summary": {
                "alias_mapping_count": len(self.alias_mappings),
                "auto_repaired_reference_count": len(self.auto_repaired_references),
                "unresolved_reference_count": len(self.unresolved_references_remaining),
                "ambiguous_mapping_count": len(self.ambiguous_mappings),
                "repaired_pool_count": len(self.repaired_pools),
                "validation_ok": self.validation.ok,
            },
            "canonical_sources": self.canonical_sources,
            "issue_classification": self.issue_classification,
            "alias_mappings": [item.to_dict() for item in self.alias_mappings],
            "auto_repaired_references": [item.to_dict() for item in self.auto_repaired_references],
            "unresolved_references_remaining": [item.to_dict() for item in self.unresolved_references_remaining],
            "ambiguous_mappings": [item.to_dict() for item in self.ambiguous_mappings],
            "repaired_pools": [item.to_dict() for item in self.repaired_pools],
            "validation": self.validation.to_dict(),
        }


class LegacyReconciliationService(LegacyImportService):
    """Repair staged rejected pools with explicit alias mappings."""

    @property
    def reconciliation_root(self) -> Path:
        return self.staging_root / "reconciliation"

    @property
    def reconciliation_reports_root(self) -> Path:
        return self.reconciliation_root / "reports"

    @property
    def reconciliation_repaired_root(self) -> Path:
        return self.reconciliation_root / "repaired"

    @property
    def reconciliation_validation_root(self) -> Path:
        return self.reconciliation_root / "validation_view"

    @property
    def reconciliation_report_path(self) -> Path:
        return self.reconciliation_reports_root / "reconciliation.latest.yml"

    def reconcile_staging(self, *, write: bool = True) -> ReconciliationReport:
        staging_report = self._load_staging_report()
        accepted_catalog = CatalogService(self.staging_accepted_root)
        accepted_entries = accepted_catalog.list_exercises(track="exams")
        accepted_by_group = self._accepted_by_group(accepted_entries)
        canonical_sources = self._canonical_sources_by_group()
        canonical_source_ids = {item.source_id for item in canonical_sources.values()}
        issues = [MigrationIssue(**item) for item in staging_report.get("issues", [])]

        alias_mappings, ambiguous_mappings = self._build_alias_mappings(
            issues,
            accepted_by_group=accepted_by_group,
            canonical_source_ids=canonical_source_ids,
        )
        unresolved_remaining: list[MigrationIssue] = []
        auto_repaired: list[AutoRepairedReference] = []
        repaired_candidates: list[NormalizedPoolCandidate] = []
        repaired_pool_summaries: list[RepairedPoolSummary] = []

        for source_id, pool_name in self._canonical_unresolved_pool_keys(issues, canonical_source_ids):
            source = canonical_sources[self._source_exam_group(source_id)]
            pool_path = source.pools_root / pool_name
            repaired_candidate = self._repair_pool_candidate(
                source,
                pool_path,
                accepted_exercise_ids={entry.exercise_id for entry in accepted_entries},
                alias_mappings={item.key(): item for item in alias_mappings},
                ambiguous_map={item.key(): item for item in ambiguous_mappings},
                auto_repaired=auto_repaired,
                unresolved_remaining=unresolved_remaining,
            )
            if repaired_candidate is None:
                continue
            repaired_candidates.append(repaired_candidate)
            repaired_pool_summaries.append(
                RepairedPoolSummary(
                    pool_id=repaired_candidate.pool_id,
                    source_id=source.source_id,
                    exam_group=source.exam_group,
                    slug=repaired_candidate.slug,
                    repaired_reference_count=sum(
                        1
                        for item in auto_repaired
                        if item.source_id == source.source_id and item.pool_name == pool_name
                    ),
                )
            )

        validation = StagingValidationReport(ok=False, exercise_count=0, pool_count=0, failures=[])
        if write:
            self._reset_directory(self.reconciliation_root)
            self._write_pools(repaired_candidates, self.reconciliation_repaired_root)
            validation = self._validate_repaired_pools()

        report = ReconciliationReport(
            generated_at=self.generated_at,
            staging_root=str(self.staging_root),
            canonical_sources={exam_group: source.source_id for exam_group, source in canonical_sources.items()},
            issue_classification=self._classify_issue_remediation(
                issues,
                alias_mappings=alias_mappings,
                ambiguous_mappings=ambiguous_mappings,
                canonical_source_ids=canonical_source_ids,
            ),
            alias_mappings=alias_mappings,
            auto_repaired_references=auto_repaired,
            unresolved_references_remaining=unresolved_remaining,
            ambiguous_mappings=ambiguous_mappings,
            repaired_pools=repaired_pool_summaries,
            validation=validation,
        )
        if write:
            self._write_reconciliation_reports(report)
        return report

    def _load_staging_report(self) -> dict[str, object]:
        if not self.staging_report_path.exists():
            raise FileNotFoundError(f"Missing staging import report: {self.staging_report_path}")
        return yaml.safe_load(self.staging_report_path.read_text(encoding="utf-8")) or {}

    def _accepted_by_group(self, accepted_entries) -> dict[str, list[tuple[str, str]]]:
        groups: dict[str, list[tuple[str, str]]] = {}
        for entry in accepted_entries:
            groups.setdefault(entry.group, []).append((entry.slug, entry.exercise_id))
        return groups

    def _canonical_sources_by_group(self) -> dict[str, LegacyExamSource]:
        canonical: dict[str, LegacyExamSource] = {}
        for source in self.discover_sources([], source_order=DEFAULT_SOURCE_ORDER):
            canonical.setdefault(source.exam_group, source)
        return canonical

    def _source_exam_group(self, source_id: str) -> str:
        lowered = source_id.split("/")[-1].lower()
        return lowered

    def _canonical_unresolved_pool_keys(
        self,
        issues: list[MigrationIssue],
        canonical_source_ids: set[str],
    ) -> list[tuple[str, str]]:
        keys: set[tuple[str, str]] = set()
        for issue in issues:
            if issue.code != "bad_pool_reference":
                continue
            if issue.source_id not in canonical_source_ids:
                continue
            if issue.pool_name is None:
                continue
            keys.add((issue.source_id, issue.pool_name))
        return sorted(keys)

    def _build_alias_mappings(
        self,
        issues: list[MigrationIssue],
        *,
        accepted_by_group: dict[str, list[tuple[str, str]]],
        canonical_source_ids: set[str],
    ) -> tuple[list[AliasMapping], list[AmbiguousMapping]]:
        alias_map: dict[tuple[str, str], AliasMapping] = {}
        ambiguous_map: dict[tuple[str, str], AmbiguousMapping] = {}
        for issue in issues:
            if issue.code not in {"bad_pool_reference", "naming_mismatch"}:
                continue
            if issue.source_id not in canonical_source_ids:
                continue
            if issue.assignment is None or issue.exam_group is None:
                continue

            candidates = self._find_alias_candidates(
                issue.assignment,
                issue.exam_group,
                accepted_by_group.get(issue.exam_group, []),
            )
            key = (issue.exam_group, issue.assignment)
            if len(candidates) == 1:
                slug, exercise_id, reason = candidates[0]
                mapping = alias_map.get(key)
                if mapping is None:
                    alias_map[key] = AliasMapping(
                        exam_group=issue.exam_group,
                        legacy_assignment_name=issue.assignment,
                        canonical_exercise_id=exercise_id,
                        canonical_slug=slug,
                        reason=reason,
                        source_issue_codes=[issue.code],
                        source_locations=[issue.location],
                    )
                else:
                    if issue.code not in mapping.source_issue_codes:
                        mapping.source_issue_codes.append(issue.code)
                    if issue.location not in mapping.source_locations:
                        mapping.source_locations.append(issue.location)
                continue

            if len(candidates) > 1:
                candidate_ids = sorted(item[1] for item in candidates)
                mapping = ambiguous_map.get(key)
                if mapping is None:
                    ambiguous_map[key] = AmbiguousMapping(
                        exam_group=issue.exam_group,
                        legacy_assignment_name=issue.assignment,
                        candidate_exercise_ids=candidate_ids,
                        reason="multiple accepted exercises matched the legacy name at the same strict distance",
                        source_issue_codes=[issue.code],
                        source_locations=[issue.location],
                    )
                else:
                    for candidate_id in candidate_ids:
                        if candidate_id not in mapping.candidate_exercise_ids:
                            mapping.candidate_exercise_ids.append(candidate_id)
                    if issue.code not in mapping.source_issue_codes:
                        mapping.source_issue_codes.append(issue.code)
                    if issue.location not in mapping.source_locations:
                        mapping.source_locations.append(issue.location)

        return (
            sorted(alias_map.values(), key=lambda item: item.key()),
            sorted(ambiguous_map.values(), key=lambda item: item.key()),
        )

    def _find_alias_candidates(
        self,
        legacy_assignment_name: str,
        exam_group: str,
        accepted_entries: list[tuple[str, str]],
    ) -> list[tuple[str, str, str]]:
        legacy_slug = self._normalize_slug(legacy_assignment_name)
        exact: list[tuple[str, str, str]] = []
        strict_distance_matches: list[tuple[str, str, str]] = []
        for slug, exercise_id in accepted_entries:
            if slug == legacy_slug:
                exact.append((slug, exercise_id, "exact_slug_match"))
                continue
            distance = self._damerau_levenshtein(legacy_slug, slug)
            if distance == 1:
                strict_distance_matches.append((slug, exercise_id, "unique_edit_distance_1"))
        return exact if exact else strict_distance_matches

    def _repair_pool_candidate(
        self,
        source: LegacyExamSource,
        pool_path: Path,
        *,
        accepted_exercise_ids: set[str],
        alias_mappings: dict[tuple[str, str], AliasMapping],
        ambiguous_map: dict[tuple[str, str], AmbiguousMapping],
        auto_repaired: list[AutoRepairedReference],
        unresolved_remaining: list[MigrationIssue],
    ) -> NormalizedPoolCandidate | None:
        payload = yaml.safe_load(pool_path.read_text(encoding="utf-8")) or {}
        raw_levels = payload.get("levels")
        if not isinstance(raw_levels, list) or not raw_levels:
            return None

        levels: list[dict[str, object]] = []
        invalid = False
        for level_index, item in enumerate(raw_levels):
            assignments = item.get("assignments") if isinstance(item, dict) else None
            if not isinstance(assignments, list) or not assignments:
                invalid = True
                continue
            exercise_refs: list[dict[str, object]] = []
            for assignment_name in assignments:
                if not isinstance(assignment_name, str) or not assignment_name.strip():
                    invalid = True
                    continue
                legacy_slug = self._normalize_slug(assignment_name)
                exercise_id = f"exams.{source.exam_group}.{legacy_slug}"
                if exercise_id in accepted_exercise_ids:
                    exercise_refs.append({"exercise_id": exercise_id, "variant": "normal", "weight": 1})
                    continue

                alias_key = (source.exam_group, assignment_name)
                if alias_key in alias_mappings:
                    mapping = alias_mappings[alias_key]
                    exercise_refs.append(
                        {
                            "exercise_id": mapping.canonical_exercise_id,
                            "variant": "normal",
                            "weight": 1,
                        }
                    )
                    auto_repaired.append(
                        AutoRepairedReference(
                            source_id=source.source_id,
                            exam_group=source.exam_group,
                            pool_name=pool_path.name,
                            level=level_index,
                            original_assignment_name=assignment_name,
                            canonical_exercise_id=mapping.canonical_exercise_id,
                            mapping_reason=mapping.reason,
                        )
                    )
                    continue

                if alias_key in ambiguous_map:
                    invalid = True
                    continue

                unresolved_remaining.append(
                    MigrationIssue(
                        code="bad_pool_reference",
                        severity="error",
                        source_id=source.source_id,
                        location=str(pool_path),
                        message=f"pool reference remains unresolved after reconciliation for assignment {assignment_name!r}",
                        exam_group=source.exam_group,
                        assignment=assignment_name,
                        pool_name=pool_path.name,
                    )
                )
                invalid = True
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

        pool_slug = self._normalize_slug(pool_path.stem)
        total_time_seconds = self.per_level_time_seconds * len(levels)
        manifest: dict[str, object] = {
            "schema_version": 1,
            "id": f"exams.{source.exam_group}.{pool_slug}",
            "title": f"{source.exam_group.upper()} {pool_path.stem}",
            "track": "exams",
            "mode": "practice" if bool(payload.get("practice")) else "exam",
            "description": f"Reconciled legacy pool from {source.source_id}.",
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
                "status": "reconciled",
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

    def _classify_issue_remediation(
        self,
        issues: list[MigrationIssue],
        *,
        alias_mappings: list[AliasMapping],
        ambiguous_mappings: list[AmbiguousMapping],
        canonical_source_ids: set[str],
    ) -> list[dict[str, object]]:
        alias_keys = {item.key() for item in alias_mappings}
        ambiguous_keys = {item.key() for item in ambiguous_mappings}
        by_code: dict[str, dict[str, object]] = {}
        for issue in issues:
            if issue.source_id not in canonical_source_ids:
                continue
            bucket = by_code.setdefault(
                issue.code,
                {
                    "issue_type": issue.code,
                    "total_count": 0,
                    "auto_remediable_count": 0,
                    "manual_review_count": 0,
                    "non_remediable_count": 0,
                },
            )
            bucket["total_count"] += 1
            key = (issue.exam_group, issue.assignment) if issue.exam_group and issue.assignment else None
            if issue.code in {"bad_pool_reference", "naming_mismatch"} and key in alias_keys:
                bucket["auto_remediable_count"] += 1
            elif issue.code in {"bad_pool_reference", "naming_mismatch"} and key in ambiguous_keys:
                bucket["manual_review_count"] += 1
            else:
                bucket["non_remediable_count"] += 1
        return [by_code[key] for key in sorted(by_code)]

    def _validate_repaired_pools(self) -> StagingValidationReport:
        self._reset_directory(self.reconciliation_validation_root)
        accepted_exercises_root = self.staging_accepted_root / "datasets/exercises"
        repaired_pools_root = self.reconciliation_repaired_root / "datasets/pools"

        if accepted_exercises_root.exists():
            shutil.copytree(
                accepted_exercises_root,
                self.reconciliation_validation_root / "datasets/exercises",
                dirs_exist_ok=True,
            )
        if repaired_pools_root.exists():
            shutil.copytree(
                repaired_pools_root,
                self.reconciliation_validation_root / "datasets/pools",
                dirs_exist_ok=True,
            )

        catalog = CatalogService(self.reconciliation_validation_root)
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

    def _write_reconciliation_reports(self, report: ReconciliationReport) -> None:
        self.reconciliation_reports_root.mkdir(parents=True, exist_ok=True)
        self._write_yaml(self.reconciliation_report_path, report.to_dict())
        self._write_yaml(
            self.reconciliation_reports_root / "alias_mappings.latest.yml",
            {"alias_mappings": [item.to_dict() for item in report.alias_mappings]},
        )
        self._write_yaml(
            self.reconciliation_reports_root / "auto_repaired_references.latest.yml",
            {"auto_repaired_references": [item.to_dict() for item in report.auto_repaired_references]},
        )
        self._write_yaml(
            self.reconciliation_reports_root / "unresolved_references.remaining.latest.yml",
            {
                "unresolved_references_remaining": [
                    item.to_dict() for item in report.unresolved_references_remaining
                ]
            },
        )
        self._write_yaml(
            self.reconciliation_reports_root / "ambiguous_mappings.latest.yml",
            {"ambiguous_mappings": [item.to_dict() for item in report.ambiguous_mappings]},
        )
        self._write_yaml(
            self.reconciliation_reports_root / "repaired_pools.latest.yml",
            {"repaired_pools": [item.to_dict() for item in report.repaired_pools]},
        )
        self._write_yaml(
            self.reconciliation_reports_root / "issue_classification.latest.yml",
            {"issue_classification": report.issue_classification},
        )
        self._write_yaml(
            self.reconciliation_reports_root / "validation.latest.yml",
            report.validation.to_dict(),
        )

    def _damerau_levenshtein(self, left: str, right: str) -> int:
        len_left = len(left)
        len_right = len(right)
        if len_left == 0:
            return len_right
        if len_right == 0:
            return len_left
        matrix = [[0] * (len_right + 1) for _ in range(len_left + 1)]
        for i in range(len_left + 1):
            matrix[i][0] = i
        for j in range(len_right + 1):
            matrix[0][j] = j
        for i in range(1, len_left + 1):
            for j in range(1, len_right + 1):
                cost = 0 if left[i - 1] == right[j - 1] else 1
                matrix[i][j] = min(
                    matrix[i - 1][j] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j - 1] + cost,
                )
                if (
                    i > 1
                    and j > 1
                    and left[i - 1] == right[j - 2]
                    and left[i - 2] == right[j - 1]
                ):
                    matrix[i][j] = min(matrix[i][j], matrix[i - 2][j - 2] + 1)
        return matrix[len_left][len_right]
