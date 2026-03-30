"""Manual curation workflow for unresolved staged legacy pool references."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil

import yaml

from platform_catalog import CatalogService, CatalogValidationError

try:
    from .reconciliation import (
        AliasMapping,
        AmbiguousMapping,
        AutoRepairedReference,
        LegacyReconciliationService,
        ReconciliationReport,
        RepairedPoolSummary,
    )
    from .service import LegacyExamSource, MigrationIssue, NormalizedPoolCandidate, StagingValidationReport
except ImportError:  # pragma: no cover - direct script execution fallback
    from reconciliation import (  # type: ignore
        AliasMapping,
        AmbiguousMapping,
        AutoRepairedReference,
        LegacyReconciliationService,
        ReconciliationReport,
        RepairedPoolSummary,
    )
    from service import LegacyExamSource, MigrationIssue, NormalizedPoolCandidate, StagingValidationReport  # type: ignore


@dataclass(slots=True)
class ManualReviewRecord:
    """One unresolved legacy reference queued for manual review."""

    legacy_reference_name: str
    source_id: str
    source_pool: str
    exam_group: str
    likely_intended_exam_rank: str
    level: int
    position_in_level: int
    candidate_canonical_exercise_ids: list[str]
    auto_repair_not_safe_reason: str
    issue_type: str

    def key(self) -> tuple[str, str, int, str]:
        return (self.source_id, self.source_pool, self.level, self.legacy_reference_name)

    def to_dict(self) -> dict[str, object]:
        return {
            "legacy_reference_name": self.legacy_reference_name,
            "source_id": self.source_id,
            "source_pool": self.source_pool,
            "exam_group": self.exam_group,
            "likely_intended_exam_rank": self.likely_intended_exam_rank,
            "level": self.level,
            "position_in_level": self.position_in_level,
            "candidate_canonical_exercise_ids": self.candidate_canonical_exercise_ids,
            "auto_repair_not_safe_reason": self.auto_repair_not_safe_reason,
            "issue_type": self.issue_type,
        }


@dataclass(slots=True)
class ManualAliasOverride:
    """One curated legacy-name to canonical-exercise mapping."""

    exam_group: str
    legacy_assignment_name: str
    canonical_exercise_id: str
    justification: str

    def key(self) -> tuple[str, str]:
        return (self.exam_group, self.legacy_assignment_name)

    def to_dict(self) -> dict[str, object]:
        return {
            "exam_group": self.exam_group,
            "legacy_assignment_name": self.legacy_assignment_name,
            "canonical_exercise_id": self.canonical_exercise_id,
            "justification": self.justification,
        }


@dataclass(slots=True)
class ManualPoolOverride:
    """One pool-specific curated mapping."""

    source_id: str
    pool_name: str
    level: int
    legacy_assignment_name: str
    canonical_exercise_id: str
    justification: str

    def key(self) -> tuple[str, str, int, str]:
        return (self.source_id, self.pool_name, self.level, self.legacy_assignment_name)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "pool_name": self.pool_name,
            "level": self.level,
            "legacy_assignment_name": self.legacy_assignment_name,
            "canonical_exercise_id": self.canonical_exercise_id,
            "justification": self.justification,
        }


@dataclass(slots=True)
class AppliedManualOverride:
    """One manual override actually applied to a repaired pool reference."""

    override_type: str
    source_id: str
    pool_name: str
    level: int
    legacy_assignment_name: str
    canonical_exercise_id: str
    justification: str

    def to_dict(self) -> dict[str, object]:
        return {
            "override_type": self.override_type,
            "source_id": self.source_id,
            "pool_name": self.pool_name,
            "level": self.level,
            "legacy_assignment_name": self.legacy_assignment_name,
            "canonical_exercise_id": self.canonical_exercise_id,
            "justification": self.justification,
        }


@dataclass(slots=True)
class ManualCurationReport:
    """Aggregate report for manual curation and override application."""

    generated_at: str
    staging_root: str
    manual_review_records: list[ManualReviewRecord]
    manual_alias_overrides: list[ManualAliasOverride]
    manual_pool_overrides: list[ManualPoolOverride]
    applied_overrides: list[AppliedManualOverride]
    repaired_pools: list[dict[str, object]]
    unresolved_references_remaining: list[MigrationIssue]
    validation: StagingValidationReport

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "staging_root": self.staging_root,
            "summary": {
                "manual_review_count": len(self.manual_review_records),
                "manual_alias_override_count": len(self.manual_alias_overrides),
                "manual_pool_override_count": len(self.manual_pool_overrides),
                "applied_override_count": len(self.applied_overrides),
                "repaired_pool_count": len(self.repaired_pools),
                "remaining_unresolved_count": len(self.unresolved_references_remaining),
                "validation_ok": self.validation.ok,
            },
            "manual_review_records": [item.to_dict() for item in self.manual_review_records],
            "manual_alias_overrides": [item.to_dict() for item in self.manual_alias_overrides],
            "manual_pool_overrides": [item.to_dict() for item in self.manual_pool_overrides],
            "applied_overrides": [item.to_dict() for item in self.applied_overrides],
            "repaired_pools": self.repaired_pools,
            "unresolved_references_remaining": [item.to_dict() for item in self.unresolved_references_remaining],
            "validation": self.validation.to_dict(),
        }


class LegacyManualCurationService(LegacyReconciliationService):
    """Apply curator-reviewed overrides in a separate staging repair layer."""

    @property
    def manual_curation_root(self) -> Path:
        return self.staging_root / "manual_curation"

    @property
    def manual_reports_root(self) -> Path:
        return self.manual_curation_root / "reports"

    @property
    def manual_repaired_root(self) -> Path:
        return self.manual_curation_root / "repaired"

    @property
    def manual_validation_root(self) -> Path:
        return self.manual_curation_root / "validation_view"

    @property
    def manual_overrides_root(self) -> Path:
        return self.manual_curation_root / "overrides"

    @property
    def manual_aliases_path(self) -> Path:
        return self.manual_overrides_root / "manual_aliases.yml"

    @property
    def manual_pool_overrides_path(self) -> Path:
        return self.manual_overrides_root / "manual_pool_overrides.yml"

    @property
    def manual_report_path(self) -> Path:
        return self.manual_reports_root / "manual_curation.latest.yml"

    @property
    def manual_review_queue_path(self) -> Path:
        return self.workspace_root / "MANUAL_REVIEW_QUEUE.md"

    def curate_manual_overrides(self, *, write: bool = True) -> ManualCurationReport:
        reconciliation = self._load_reconciliation_report()
        accepted_catalog = CatalogService(self.staging_accepted_root)
        accepted_entries = accepted_catalog.list_exercises(track="exams")
        accepted_by_group = self._accepted_entries_by_group(accepted_entries)
        rejected_lookup = self._load_rejected_lookup()
        review_records = self._build_manual_review_records(
            reconciliation.unresolved_references_remaining,
            accepted_entries=accepted_entries,
            accepted_by_group=accepted_by_group,
            rejected_lookup=rejected_lookup,
        )
        if write:
            self._ensure_manual_override_templates()

        alias_overrides = self._load_manual_alias_overrides(accepted_catalog)
        pool_overrides = self._load_manual_pool_overrides(accepted_catalog)

        auto_alias_map = {item.key(): item for item in reconciliation.alias_mappings}
        manual_alias_map = {item.key(): item for item in alias_overrides}
        manual_pool_map = {item.key(): item for item in pool_overrides}
        canonical_sources = self._canonical_sources_by_group()
        applied_overrides: list[AppliedManualOverride] = []
        repaired_candidates: list[NormalizedPoolCandidate] = []
        repaired_pool_summaries: list[dict[str, object]] = []
        remaining_unresolved: list[MigrationIssue] = []

        for source_id, pool_name in self._reconciliation_unresolved_pool_keys(reconciliation):
            source = canonical_sources[self._source_exam_group(source_id)]
            candidate = self._repair_pool_with_manual_overrides(
                source,
                source.pools_root / pool_name,
                accepted_exercise_ids={entry.exercise_id for entry in accepted_entries},
                auto_aliases=auto_alias_map,
                manual_aliases=manual_alias_map,
                manual_pool_overrides=manual_pool_map,
                applied_overrides=applied_overrides,
                remaining_unresolved=remaining_unresolved,
            )
            if candidate is None:
                continue
            repaired_candidates.append(candidate)
            repaired_pool_summaries.append(candidate.summary())

        validation = StagingValidationReport(ok=False, exercise_count=0, pool_count=0, failures=[])
        if write:
            self._ensure_manual_override_templates()
            self._reset_directory(self.manual_repaired_root)
            self._reset_directory(self.manual_reports_root)
            self._write_pools(repaired_candidates, self.manual_repaired_root)
            validation = self._validate_manual_repaired_pools()

        report = ManualCurationReport(
            generated_at=self.generated_at,
            staging_root=str(self.staging_root),
            manual_review_records=review_records,
            manual_alias_overrides=alias_overrides,
            manual_pool_overrides=pool_overrides,
            applied_overrides=applied_overrides,
            repaired_pools=repaired_pool_summaries,
            unresolved_references_remaining=remaining_unresolved,
            validation=validation,
        )
        if write:
            self._write_manual_curation_reports(report)
            self._write_manual_review_queue(report)
        return report

    def _load_reconciliation_report(self) -> ReconciliationReport:
        payload = yaml.safe_load(self.reconciliation_report_path.read_text(encoding="utf-8")) or {}
        validation_payload = payload.get("validation", {})
        return ReconciliationReport(
            generated_at=payload["generated_at"],
            staging_root=payload["staging_root"],
            canonical_sources=payload.get("canonical_sources", {}),
            issue_classification=payload.get("issue_classification", []),
            alias_mappings=[AliasMapping(**item) for item in payload.get("alias_mappings", [])],
            auto_repaired_references=[
                AutoRepairedReference(**item) for item in payload.get("auto_repaired_references", [])
            ],
            unresolved_references_remaining=[
                MigrationIssue(**item) for item in payload.get("unresolved_references_remaining", [])
            ],
            ambiguous_mappings=[AmbiguousMapping(**item) for item in payload.get("ambiguous_mappings", [])],
            repaired_pools=[RepairedPoolSummary(**item) for item in payload.get("repaired_pools", [])],
            validation=StagingValidationReport(
                ok=bool(validation_payload.get("ok", False)),
                exercise_count=int(validation_payload.get("exercise_count", 0)),
                pool_count=int(validation_payload.get("pool_count", 0)),
                failures=list(validation_payload.get("failures", [])),
            ),
        )

    def _accepted_entries_by_group(self, accepted_entries) -> dict[str, list[tuple[str, str]]]:
        grouped: dict[str, list[tuple[str, str]]] = {}
        for entry in accepted_entries:
            grouped.setdefault(entry.group, []).append((entry.slug, entry.exercise_id))
        return grouped

    def _load_rejected_lookup(self) -> dict[tuple[str, str], dict[str, object]]:
        rejected_lookup: dict[tuple[str, str], dict[str, object]] = {}
        if not self.staging_rejected_root.exists():
            return rejected_lookup
        for path in sorted(self.staging_rejected_root.rglob("*.yml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            exam_group = payload.get("exam_group")
            identifier = payload.get("assignment") or payload.get("identifier")
            if isinstance(exam_group, str) and isinstance(identifier, str):
                rejected_lookup[(exam_group, identifier)] = payload
        return rejected_lookup

    def _build_manual_review_records(
        self,
        unresolved: list[MigrationIssue],
        *,
        accepted_entries,
        accepted_by_group: dict[str, list[tuple[str, str]]],
        rejected_lookup: dict[tuple[str, str], dict[str, object]],
    ) -> list[ManualReviewRecord]:
        records: list[ManualReviewRecord] = []
        all_candidates = [(entry.group, entry.slug, entry.exercise_id) for entry in accepted_entries]
        for issue in unresolved:
            level, position = self._locate_pool_reference(issue)
            candidates = self._manual_candidate_ids(
                issue.assignment or "",
                issue.exam_group or "",
                accepted_by_group,
                all_candidates,
            )
            rejected_payload = rejected_lookup.get((issue.exam_group or "", issue.assignment or ""))
            issue_type, reason = self._classify_manual_issue(issue, candidates, rejected_payload)
            records.append(
                ManualReviewRecord(
                    legacy_reference_name=issue.assignment or "",
                    source_id=issue.source_id,
                    source_pool=issue.pool_name or "",
                    exam_group=issue.exam_group or "",
                    likely_intended_exam_rank=f"{issue.exam_group} level {level}" if issue.exam_group else f"level {level}",
                    level=level,
                    position_in_level=position,
                    candidate_canonical_exercise_ids=candidates,
                    auto_repair_not_safe_reason=reason,
                    issue_type=issue_type,
                )
            )
        return sorted(records, key=lambda item: item.key())

    def _manual_candidate_ids(
        self,
        legacy_assignment_name: str,
        exam_group: str,
        accepted_by_group: dict[str, list[tuple[str, str]]],
        all_candidates: list[tuple[str, str, str]],
    ) -> list[str]:
        legacy_slug = self._normalize_slug(legacy_assignment_name)
        same_group_matches: list[tuple[int, str]] = []
        cross_group_matches: list[tuple[int, str]] = []
        for candidate_group, slug, exercise_id in all_candidates:
            distance = self._damerau_levenshtein(legacy_slug, slug)
            if slug == legacy_slug:
                distance = 0
            if candidate_group == exam_group and distance <= 2:
                same_group_matches.append((distance, exercise_id))
            elif candidate_group != exam_group and (distance <= 1 or slug == legacy_slug):
                cross_group_matches.append((distance, exercise_id))
        ordered = sorted(same_group_matches) + sorted(cross_group_matches)
        candidate_ids: list[str] = []
        for _, exercise_id in ordered:
            if exercise_id not in candidate_ids:
                candidate_ids.append(exercise_id)
        return candidate_ids[:6]

    def _classify_manual_issue(
        self,
        issue: MigrationIssue,
        candidate_ids: list[str],
        rejected_payload: dict[str, object] | None,
    ) -> tuple[str, str]:
        reasons = set(rejected_payload.get("reasons", [])) if rejected_payload else set()
        if "malformed_generator" in reasons or "malformed_correction_bundle" in reasons:
            return (
                "malformed legacy reference",
                "the legacy bundle exists but was rejected as malformed, so auto-repair could not trust any canonical target",
            )
        if "missing_file" in reasons:
            return (
                "missing content",
                "the legacy bundle is incomplete or missing required files, so no accepted canonical target exists to auto-repair against",
            )
        if len(candidate_ids) > 1:
            return (
                "ambiguous mapping",
                "multiple plausible canonical candidates exist, and auto-repair only permits unique justified mappings",
            )
        if candidate_ids:
            return (
                "naming mismatch",
                "a plausible canonical target exists, but it falls outside the strict automatic same-group exact or 1-edit reconciliation rules",
            )
        return (
            "missing content",
            "no accepted canonical candidate was found, so auto-repair had no safe target",
        )

    def _locate_pool_reference(self, issue: MigrationIssue) -> tuple[int, int]:
        if issue.exam_group is None or issue.pool_name is None or issue.assignment is None:
            return (0, 0)
        source = self._canonical_sources_by_group()[issue.exam_group]
        payload = yaml.safe_load((source.pools_root / issue.pool_name).read_text(encoding="utf-8")) or {}
        levels = payload.get("levels", [])
        for level_index, item in enumerate(levels):
            assignments = item.get("assignments") if isinstance(item, dict) else None
            if not isinstance(assignments, list):
                continue
            for position, assignment in enumerate(assignments):
                if assignment == issue.assignment:
                    return (level_index, position)
        return (0, 0)

    def _ensure_manual_override_templates(self) -> None:
        self.manual_overrides_root.mkdir(parents=True, exist_ok=True)
        if not self.manual_aliases_path.exists():
            self.manual_aliases_path.write_text(
                yaml.safe_dump({"schema_version": 1, "aliases": []}, sort_keys=False),
                encoding="utf-8",
            )
        if not self.manual_pool_overrides_path.exists():
            self.manual_pool_overrides_path.write_text(
                yaml.safe_dump({"schema_version": 1, "overrides": []}, sort_keys=False),
                encoding="utf-8",
            )

    def _load_manual_alias_overrides(self, catalog: CatalogService) -> list[ManualAliasOverride]:
        payload = yaml.safe_load(self.manual_aliases_path.read_text(encoding="utf-8")) or {}
        self._validate_override_root(payload, expected_root_keys={"schema_version", "aliases"}, list_key="aliases")
        aliases: list[ManualAliasOverride] = []
        for item in payload.get("aliases", []):
            self._validate_override_item(
                item,
                required_keys={"exam_group", "legacy_assignment_name", "canonical_exercise_id", "justification"},
            )
            override = ManualAliasOverride(**item)
            dataset = catalog.load_exercise(override.canonical_exercise_id)
            if dataset.entry.group != override.exam_group:
                raise ValueError(
                    f"manual alias override {override.legacy_assignment_name!r} points to cross-group exercise "
                    f"{override.canonical_exercise_id!r}; use a pool override instead"
                )
            aliases.append(override)
        return aliases

    def _load_manual_pool_overrides(self, catalog: CatalogService) -> list[ManualPoolOverride]:
        payload = yaml.safe_load(self.manual_pool_overrides_path.read_text(encoding="utf-8")) or {}
        self._validate_override_root(payload, expected_root_keys={"schema_version", "overrides"}, list_key="overrides")
        overrides: list[ManualPoolOverride] = []
        for item in payload.get("overrides", []):
            self._validate_override_item(
                item,
                required_keys={
                    "source_id",
                    "pool_name",
                    "level",
                    "legacy_assignment_name",
                    "canonical_exercise_id",
                    "justification",
                },
            )
            catalog.load_exercise(item["canonical_exercise_id"])
            overrides.append(ManualPoolOverride(**item))
        return overrides

    def _validate_override_root(self, payload: dict, *, expected_root_keys: set[str], list_key: str) -> None:
        if not isinstance(payload, dict):
            raise ValueError("manual override file must contain a YAML mapping")
        unknown = set(payload) - expected_root_keys
        if unknown:
            raise ValueError(f"manual override file contains unknown keys: {sorted(unknown)}")
        if payload.get("schema_version") != 1:
            raise ValueError("manual override file must declare schema_version: 1")
        items = payload.get(list_key)
        if not isinstance(items, list):
            raise ValueError(f"manual override file must contain a list at {list_key!r}")

    def _validate_override_item(self, item: object, *, required_keys: set[str]) -> None:
        if not isinstance(item, dict):
            raise ValueError("manual override entries must be mappings")
        unknown = set(item) - required_keys
        missing = required_keys - set(item)
        if unknown:
            raise ValueError(f"manual override entry contains unknown keys: {sorted(unknown)}")
        if missing:
            raise ValueError(f"manual override entry is missing keys: {sorted(missing)}")

    def _reconciliation_unresolved_pool_keys(
        self,
        reconciliation: ReconciliationReport,
    ) -> list[tuple[str, str]]:
        keys = {
            (issue.source_id, issue.pool_name)
            for issue in reconciliation.unresolved_references_remaining
            if issue.pool_name is not None
        }
        return sorted(keys)

    def _repair_pool_with_manual_overrides(
        self,
        source: LegacyExamSource,
        pool_path: Path,
        *,
        accepted_exercise_ids: set[str],
        auto_aliases: dict[tuple[str, str], AliasMapping],
        manual_aliases: dict[tuple[str, str], ManualAliasOverride],
        manual_pool_overrides: dict[tuple[str, str, int, str], ManualPoolOverride],
        applied_overrides: list[AppliedManualOverride],
        remaining_unresolved: list[MigrationIssue],
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
                direct_exercise_id = f"exams.{source.exam_group}.{self._normalize_slug(assignment_name)}"
                if direct_exercise_id in accepted_exercise_ids:
                    exercise_refs.append({"exercise_id": direct_exercise_id, "variant": "normal", "weight": 1})
                    continue

                manual_pool_key = (source.source_id, pool_path.name, level_index, assignment_name)
                if manual_pool_key in manual_pool_overrides:
                    override = manual_pool_overrides[manual_pool_key]
                    exercise_refs.append(
                        {"exercise_id": override.canonical_exercise_id, "variant": "normal", "weight": 1}
                    )
                    applied_overrides.append(
                        AppliedManualOverride(
                            override_type="manual_pool_override",
                            source_id=source.source_id,
                            pool_name=pool_path.name,
                            level=level_index,
                            legacy_assignment_name=assignment_name,
                            canonical_exercise_id=override.canonical_exercise_id,
                            justification=override.justification,
                        )
                    )
                    continue

                alias_key = (source.exam_group, assignment_name)
                if alias_key in manual_aliases:
                    override = manual_aliases[alias_key]
                    exercise_refs.append(
                        {"exercise_id": override.canonical_exercise_id, "variant": "normal", "weight": 1}
                    )
                    applied_overrides.append(
                        AppliedManualOverride(
                            override_type="manual_alias_override",
                            source_id=source.source_id,
                            pool_name=pool_path.name,
                            level=level_index,
                            legacy_assignment_name=assignment_name,
                            canonical_exercise_id=override.canonical_exercise_id,
                            justification=override.justification,
                        )
                    )
                    continue

                if alias_key in auto_aliases:
                    auto = auto_aliases[alias_key]
                    exercise_refs.append(
                        {"exercise_id": auto.canonical_exercise_id, "variant": "normal", "weight": 1}
                    )
                    continue

                remaining_unresolved.append(
                    MigrationIssue(
                        code="bad_pool_reference",
                        severity="error",
                        source_id=source.source_id,
                        location=str(pool_path),
                        message=f"pool reference remains unresolved after manual curation for assignment {assignment_name!r}",
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
                    "unlock_if": {"all_of": [] if level_index == 0 else [level_index - 1], "any_of": []},
                    "exercise_refs": exercise_refs,
                }
            )
        if invalid:
            return None

        pool_slug = self._normalize_slug(pool_path.stem)
        total_time_seconds = self.per_level_time_seconds * len(levels)
        manifest = {
            "schema_version": 1,
            "id": f"exams.{source.exam_group}.{pool_slug}",
            "title": f"{source.exam_group.upper()} {pool_path.stem}",
            "track": "exams",
            "mode": "practice" if bool(payload.get("practice")) else "exam",
            "description": f"Manual-curated legacy pool from {source.source_id}.",
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
                "status": "manual_curated",
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

    def _validate_manual_repaired_pools(self) -> StagingValidationReport:
        self._reset_directory(self.manual_validation_root)
        accepted_exercises_root = self.staging_accepted_root / "datasets/exercises"
        repaired_pools_root = self.manual_repaired_root / "datasets/pools"
        if accepted_exercises_root.exists():
            shutil.copytree(
                accepted_exercises_root,
                self.manual_validation_root / "datasets/exercises",
                dirs_exist_ok=True,
            )
        if repaired_pools_root.exists():
            shutil.copytree(
                repaired_pools_root,
                self.manual_validation_root / "datasets/pools",
                dirs_exist_ok=True,
            )
        catalog = CatalogService(self.manual_validation_root)
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

    def _write_manual_curation_reports(self, report: ManualCurationReport) -> None:
        self.manual_reports_root.mkdir(parents=True, exist_ok=True)
        self._write_yaml(self.manual_report_path, report.to_dict())
        self._write_yaml(
            self.manual_reports_root / "manual_review_records.latest.yml",
            {"manual_review_records": [item.to_dict() for item in report.manual_review_records]},
        )
        self._write_yaml(
            self.manual_reports_root / "applied_overrides.latest.yml",
            {"applied_overrides": [item.to_dict() for item in report.applied_overrides]},
        )
        self._write_yaml(
            self.manual_reports_root / "repaired_pools.latest.yml",
            {"repaired_pools": report.repaired_pools},
        )
        self._write_yaml(
            self.manual_reports_root / "unresolved_references.remaining.latest.yml",
            {
                "unresolved_references_remaining": [
                    item.to_dict() for item in report.unresolved_references_remaining
                ]
            },
        )
        self._write_yaml(
            self.manual_reports_root / "validation.latest.yml",
            report.validation.to_dict(),
        )

    def _write_manual_review_queue(self, report: ManualCurationReport) -> None:
        unresolved_keys = {
            (item.source_id, item.pool_name, item.assignment)
            for item in report.unresolved_references_remaining
            if item.pool_name is not None and item.assignment is not None
        }
        pending_records = [
            record
            for record in report.manual_review_records
            if (record.source_id, record.source_pool, record.legacy_reference_name) in unresolved_keys
        ]
        lines = [
            "# Manual Review Queue",
            "",
            f"- Generated at: `{report.generated_at}`",
            f"- Remaining unresolved cases: {len(pending_records)}",
            f"- Manual alias overrides loaded: {len(report.manual_alias_overrides)}",
            f"- Manual pool overrides loaded: {len(report.manual_pool_overrides)}",
            f"- Applied overrides: {len(report.applied_overrides)}",
            f"- Repaired pool candidates: {len(report.repaired_pools)}",
            "",
        ]
        for record in pending_records:
            candidates = ", ".join(f"`{item}`" for item in record.candidate_canonical_exercise_ids) or "none"
            lines.extend(
                [
                    f"## {record.exam_group} / {record.legacy_reference_name}",
                    "",
                    f"- source pool: `{record.source_id}:{record.source_pool}`",
                    f"- likely intended exam/rank: `{record.likely_intended_exam_rank}`",
                    f"- candidate canonical exercise IDs: {candidates}",
                    f"- issue type: {record.issue_type}",
                    f"- why auto-repair was not safe: {record.auto_repair_not_safe_reason}",
                    "",
                ]
            )
        self.manual_review_queue_path.write_text("\n".join(lines), encoding="utf-8")
