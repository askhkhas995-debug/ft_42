"""Build curated canonical exam pools from staged legacy import outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil

import yaml

from platform_catalog import CatalogService, CatalogValidationError

try:
    from .manual_curation import AppliedManualOverride, LegacyManualCurationService, ManualCurationReport
    from .reconciliation import AutoRepairedReference, LegacyReconciliationService, ReconciliationReport
    from .service import LegacyExamSource, MigrationIssue, NormalizedPoolCandidate, StagingValidationReport
except ImportError:  # pragma: no cover - direct script execution fallback
    from manual_curation import AppliedManualOverride, LegacyManualCurationService, ManualCurationReport  # type: ignore
    from reconciliation import AutoRepairedReference, LegacyReconciliationService, ReconciliationReport  # type: ignore
    from service import LegacyExamSource, MigrationIssue, NormalizedPoolCandidate, StagingValidationReport  # type: ignore


CURATED_GROUP_ORDER = (
    ("exam00", "exam00"),
    ("exam01", "exam01"),
    ("exam02", "exam02"),
    ("examfinal", "exam_final"),
)


@dataclass(slots=True)
class CuratedPoolEntryProvenance:
    """One curated pool exercise reference with provenance."""

    curated_level: int
    legacy_level: int
    legacy_position: int
    legacy_assignment_name: str
    canonical_exercise_id: str
    provenance: str

    def to_dict(self) -> dict[str, object]:
        return {
            "curated_level": self.curated_level,
            "legacy_level": self.legacy_level,
            "legacy_position": self.legacy_position,
            "legacy_assignment_name": self.legacy_assignment_name,
            "canonical_exercise_id": self.canonical_exercise_id,
            "provenance": self.provenance,
        }


@dataclass(slots=True)
class CuratedPoolGap:
    """One excluded unresolved legacy reference or empty level gap."""

    exam_group: str
    source_id: str
    pool_name: str
    legacy_level: int
    legacy_assignment_name: str | None
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "exam_group": self.exam_group,
            "source_id": self.source_id,
            "pool_name": self.pool_name,
            "legacy_level": self.legacy_level,
            "legacy_assignment_name": self.legacy_assignment_name,
            "reason": self.reason,
        }


@dataclass(slots=True)
class CuratedPoolBundle:
    """A curated pool manifest plus provenance sidecar."""

    candidate: NormalizedPoolCandidate
    source_id: str
    source_pool_name: str
    public_exam_name: str
    per_level_counts: list[dict[str, int]]
    provenance_entries: list[CuratedPoolEntryProvenance]
    unresolved_gaps: list[CuratedPoolGap]

    def summary(self) -> dict[str, object]:
        provenance_summary: dict[str, int] = {}
        for entry in self.provenance_entries:
            provenance_summary[entry.provenance] = provenance_summary.get(entry.provenance, 0) + 1
        return {
            "pool_id": self.candidate.pool_id,
            "exam_group": self.candidate.exam_group,
            "public_exam_name": self.public_exam_name,
            "source_id": self.source_id,
            "source_pool_name": self.source_pool_name,
            "level_count": len(self.per_level_counts),
            "per_level_counts": self.per_level_counts,
            "provenance_summary": provenance_summary,
            "unresolved_gap_count": len(self.unresolved_gaps),
        }


@dataclass(slots=True)
class CuratedPoolsReport:
    """Aggregate report for curated pool generation."""

    generated_at: str
    staging_root: str
    curated_pools: list[CuratedPoolBundle]
    unresolved_gaps: list[CuratedPoolGap]
    validation: StagingValidationReport

    def to_dict(self) -> dict[str, object]:
        provenance_summary: dict[str, int] = {}
        for bundle in self.curated_pools:
            for entry in bundle.provenance_entries:
                provenance_summary[entry.provenance] = provenance_summary.get(entry.provenance, 0) + 1
        return {
            "generated_at": self.generated_at,
            "staging_root": self.staging_root,
            "summary": {
                "usable_pool_count": len(self.curated_pools),
                "unresolved_gap_count": len(self.unresolved_gaps),
                "provenance_summary": provenance_summary,
                "validation_ok": self.validation.ok,
            },
            "curated_pools": [bundle.summary() for bundle in self.curated_pools],
            "unresolved_gaps": [gap.to_dict() for gap in self.unresolved_gaps],
            "validation": self.validation.to_dict(),
        }


class CuratedExamPoolService(LegacyManualCurationService):
    """Generate curated canonical exam pools from staged accepted exercises."""

    @property
    def curated_root(self) -> Path:
        return self.staging_root / "curated_pools" / "v1"

    @property
    def curated_reports_root(self) -> Path:
        return self.curated_root / "reports"

    @property
    def curated_datasets_root(self) -> Path:
        return self.curated_root / "datasets"

    @property
    def curated_validation_root(self) -> Path:
        return self.curated_root / "validation_view"

    @property
    def curated_report_path(self) -> Path:
        return self.curated_reports_root / "curated_pools.latest.yml"

    @property
    def curated_status_path(self) -> Path:
        return self.workspace_root / "CURATED_POOLS_STATUS.md"

    def build_curated_pools(self, *, write: bool = True) -> CuratedPoolsReport:
        accepted_catalog = CatalogService(self.staging_accepted_root)
        accepted_entries = accepted_catalog.list_exercises(track="exams")
        accepted_ids = {entry.exercise_id for entry in accepted_entries}
        reconciliation = self._load_reconciliation_report()
        manual = self._load_manual_curation_report()

        auto_map = {
            (item.source_id, item.pool_name, item.level, item.original_assignment_name): item
            for item in reconciliation.auto_repaired_references
        }
        manual_map = {
            (item.source_id, item.pool_name, item.level, item.legacy_assignment_name): item
            for item in manual.applied_overrides
        }
        unresolved_lookup = {
            (item.source_id, item.pool_name, item.assignment, item.exam_group): item
            for item in manual.unresolved_references_remaining
        }

        canonical_sources = self._canonical_sources_by_group()
        bundles: list[CuratedPoolBundle] = []
        all_gaps: list[CuratedPoolGap] = []
        for exam_group, public_exam_name in CURATED_GROUP_ORDER:
            source = canonical_sources.get(exam_group)
            if source is None:
                continue
            source_pools = sorted(source.pools_root.glob("*.yml"))
            if not source_pools:
                continue
            bundle = self._build_curated_bundle(
                source,
                source_pools[0],
                public_exam_name=public_exam_name,
                accepted_ids=accepted_ids,
                auto_map=auto_map,
                manual_map=manual_map,
                unresolved_lookup=unresolved_lookup,
            )
            if bundle is None:
                continue
            bundles.append(bundle)
            all_gaps.extend(bundle.unresolved_gaps)

        validation = StagingValidationReport(ok=False, exercise_count=0, pool_count=0, failures=[])
        if write:
            self._reset_directory(self.curated_root)
            self._write_curated_bundles(bundles)
            validation = self._validate_curated_pools()

        report = CuratedPoolsReport(
            generated_at=self.generated_at,
            staging_root=str(self.staging_root),
            curated_pools=bundles,
            unresolved_gaps=all_gaps,
            validation=validation,
        )
        if write:
            self._write_curated_reports(report)
            self._write_curated_status(report)
        return report

    def _build_curated_bundle(
        self,
        source: LegacyExamSource,
        pool_path: Path,
        *,
        public_exam_name: str,
        accepted_ids: set[str],
        auto_map: dict[tuple[str, str, int, str], AutoRepairedReference],
        manual_map: dict[tuple[str, str, int, str], AppliedManualOverride],
        unresolved_lookup: dict[tuple[str, str | None, str | None, str | None], MigrationIssue],
    ) -> CuratedPoolBundle | None:
        payload = yaml.safe_load(pool_path.read_text(encoding="utf-8")) or {}
        raw_levels = payload.get("levels")
        if not isinstance(raw_levels, list) or not raw_levels:
            return None

        curated_levels: list[dict[str, object]] = []
        per_level_counts: list[dict[str, int]] = []
        provenance_entries: list[CuratedPoolEntryProvenance] = []
        unresolved_gaps: list[CuratedPoolGap] = []
        curated_level_index = 0

        for legacy_level, item in enumerate(raw_levels):
            assignments = item.get("assignments") if isinstance(item, dict) else None
            if not isinstance(assignments, list) or not assignments:
                unresolved_gaps.append(
                    CuratedPoolGap(
                        exam_group=source.exam_group,
                        source_id=source.source_id,
                        pool_name=pool_path.name,
                        legacy_level=legacy_level,
                        legacy_assignment_name=None,
                        reason="legacy level had no usable assignments",
                    )
                )
                continue
            exercise_refs: list[dict[str, object]] = []
            kept_in_level = 0
            for position, assignment_name in enumerate(assignments):
                direct_exercise_id = f"exams.{source.exam_group}.{self._normalize_slug(str(assignment_name))}"
                provenance = None
                exercise_id = None
                if direct_exercise_id in accepted_ids:
                    exercise_id = direct_exercise_id
                    provenance = "imported_directly"
                else:
                    key = (source.source_id, pool_path.name, legacy_level, str(assignment_name))
                    if key in manual_map:
                        exercise_id = manual_map[key].canonical_exercise_id
                        provenance = "repaired_manually"
                    elif key in auto_map:
                        exercise_id = auto_map[key].canonical_exercise_id
                        provenance = "repaired_automatically"

                if exercise_id is None:
                    issue = unresolved_lookup.get(
                        (source.source_id, pool_path.name, str(assignment_name), source.exam_group)
                    )
                    reason = issue.message if issue is not None else "excluded by curation policy because no safe canonical mapping exists"
                    unresolved_gaps.append(
                        CuratedPoolGap(
                            exam_group=source.exam_group,
                            source_id=source.source_id,
                            pool_name=pool_path.name,
                            legacy_level=legacy_level,
                            legacy_assignment_name=str(assignment_name),
                            reason=reason,
                        )
                    )
                    continue

                exercise_refs.append(
                    {
                        "exercise_id": exercise_id,
                        "variant": "normal",
                        "weight": 1,
                        "order": position + 1,
                    }
                )
                provenance_entries.append(
                    CuratedPoolEntryProvenance(
                        curated_level=curated_level_index,
                        legacy_level=legacy_level,
                        legacy_position=position,
                        legacy_assignment_name=str(assignment_name),
                        canonical_exercise_id=exercise_id,
                        provenance=provenance,
                    )
                )
                kept_in_level += 1

            if not exercise_refs:
                unresolved_gaps.append(
                    CuratedPoolGap(
                        exam_group=source.exam_group,
                        source_id=source.source_id,
                        pool_name=pool_path.name,
                        legacy_level=legacy_level,
                        legacy_assignment_name=None,
                        reason="legacy level was excluded because all references were unresolved",
                    )
                )
                continue

            curated_levels.append(
                {
                    "level": curated_level_index,
                    "title": f"Legacy Level {legacy_level}",
                    "min_picks": 1,
                    "max_picks": 1,
                    "time_limit_seconds": self.per_level_time_seconds,
                    "unlock_if": {"all_of": [] if curated_level_index == 0 else [curated_level_index - 1], "any_of": []},
                    "exercise_refs": exercise_refs,
                }
            )
            per_level_counts.append(
                {
                    "curated_level": curated_level_index,
                    "legacy_level": legacy_level,
                    "exercise_count": kept_in_level,
                }
            )
            curated_level_index += 1

        if not curated_levels:
            return None

        slug = f"curated-{public_exam_name}-v1"
        manifest = {
            "schema_version": 1,
            "id": f"exams.curated.{public_exam_name}.v1",
            "title": f"Curated {public_exam_name.upper()} v1",
            "track": "exams",
            "mode": "exam",
            "description": f"Curated canonical pool for {public_exam_name} based on staged legacy import outputs.",
            "selection": {
                "strategy": "random",
                "repeat_policy": "avoid_passed",
                "seed_policy": "deterministic_per_session",
            },
            "timing": {
                "total_time_seconds": self.per_level_time_seconds * len(curated_levels),
                "per_level_time_seconds": self.per_level_time_seconds,
                "cooldown": {"enabled": False, "seconds": 0, "scope": "pool"},
            },
            "levels": curated_levels,
            "metadata": {
                "created_at": self.generated_at,
                "updated_at": self.generated_at,
                "status": "curated_v1",
            },
        }
        candidate = NormalizedPoolCandidate(
            pool_id=manifest["id"],
            slug=slug,
            exam_group=source.exam_group,
            source_id=source.source_id,
            manifest=manifest,
            fingerprint=self._fingerprint(yaml.safe_dump(manifest, sort_keys=True)),
        )
        return CuratedPoolBundle(
            candidate=candidate,
            source_id=source.source_id,
            source_pool_name=pool_path.name,
            public_exam_name=public_exam_name,
            per_level_counts=per_level_counts,
            provenance_entries=provenance_entries,
            unresolved_gaps=unresolved_gaps,
        )

    def _load_manual_curation_report(self) -> ManualCurationReport:
        payload = yaml.safe_load(self.manual_report_path.read_text(encoding="utf-8")) or {}
        validation_payload = payload.get("validation", {})
        return ManualCurationReport(
            generated_at=payload["generated_at"],
            staging_root=payload["staging_root"],
            manual_review_records=[],
            manual_alias_overrides=[],
            manual_pool_overrides=[],
            applied_overrides=[AppliedManualOverride(**item) for item in payload.get("applied_overrides", [])],
            repaired_pools=list(payload.get("repaired_pools", [])),
            unresolved_references_remaining=[
                MigrationIssue(**item) for item in payload.get("unresolved_references_remaining", [])
            ],
            validation=StagingValidationReport(
                ok=bool(validation_payload.get("ok", False)),
                exercise_count=int(validation_payload.get("exercise_count", 0)),
                pool_count=int(validation_payload.get("pool_count", 0)),
                failures=list(validation_payload.get("failures", [])),
            ),
        )

    def _write_curated_bundles(self, bundles: list[CuratedPoolBundle]) -> None:
        self._write_pools((bundle.candidate for bundle in bundles), self.curated_root)
        for bundle in bundles:
            root = bundle.candidate.output_root(self.curated_root)
            provenance_payload = {
                "schema_version": 1,
                "pool_id": bundle.candidate.pool_id,
                "source_id": bundle.source_id,
                "source_pool_name": bundle.source_pool_name,
                "public_exam_name": bundle.public_exam_name,
                "entries": [entry.to_dict() for entry in bundle.provenance_entries],
                "unresolved_gaps": [gap.to_dict() for gap in bundle.unresolved_gaps],
            }
            self._write_yaml(root / "provenance.yml", provenance_payload)

    def _validate_curated_pools(self) -> StagingValidationReport:
        self._reset_directory(self.curated_validation_root)
        accepted_exercises_root = self.staging_accepted_root / "datasets/exercises"
        curated_pools_root = self.curated_root / "datasets/pools"
        if accepted_exercises_root.exists():
            shutil.copytree(
                accepted_exercises_root,
                self.curated_validation_root / "datasets/exercises",
                dirs_exist_ok=True,
            )
        if curated_pools_root.exists():
            shutil.copytree(
                curated_pools_root,
                self.curated_validation_root / "datasets/pools",
                dirs_exist_ok=True,
            )
        catalog = CatalogService(self.curated_validation_root)
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

    def _write_curated_reports(self, report: CuratedPoolsReport) -> None:
        self.curated_reports_root.mkdir(parents=True, exist_ok=True)
        self._write_yaml(self.curated_report_path, report.to_dict())
        self._write_yaml(
            self.curated_reports_root / "unresolved_gaps.latest.yml",
            {"unresolved_gaps": [gap.to_dict() for gap in report.unresolved_gaps]},
        )
        self._write_yaml(
            self.curated_reports_root / "validation.latest.yml",
            report.validation.to_dict(),
        )

    def _write_curated_status(self, report: CuratedPoolsReport) -> None:
        payload = report.to_dict()
        summary = payload["summary"]
        lines = [
            "# Curated Pools Status",
            "",
            f"- Generated at: `{report.generated_at}`",
            f"- usable pool count: {summary['usable_pool_count']}",
            f"- validation: {'passed' if report.validation.ok else 'failed'}",
            "",
            "## Per-Pool Level Counts",
            "",
        ]
        for bundle in report.curated_pools:
            counts = ", ".join(
                f"L{item['curated_level']} (legacy {item['legacy_level']}): {item['exercise_count']}"
                for item in bundle.per_level_counts
            )
            lines.append(f"- `{bundle.candidate.pool_id}`: {counts}")

        provenance_summary = summary["provenance_summary"]
        lines.extend(["", "## Provenance Summary", ""])
        for key in ("imported_directly", "repaired_automatically", "repaired_manually", "curated_by_policy"):
            lines.append(f"- {key}: {provenance_summary.get(key, 0)}")

        lines.extend(["", "## Unresolved Gaps", ""])
        if not report.unresolved_gaps:
            lines.append("- none")
        else:
            for gap in report.unresolved_gaps:
                target = gap.legacy_assignment_name or "<level>"
                lines.append(
                    f"- `{gap.exam_group}` `{gap.pool_name}` level {gap.legacy_level}: {target} -> {gap.reason}"
                )
        self.curated_status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
