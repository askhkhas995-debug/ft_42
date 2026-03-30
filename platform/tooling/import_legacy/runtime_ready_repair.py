"""Build a staged runtime-ready subset from audited curated exam bundles."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
import shutil

import yaml

from platform_catalog import CatalogService, CatalogValidationError

from .exam_integration import ExamIntegrationReport
from .reference_bundle_audit import ReferenceBundleAuditReport, ReferenceBundleAuditResult, ReferenceBundleAuditService


@dataclass(slots=True)
class AppliedRepairRecord:
    """One applied safe repair in the runtime-ready layer."""

    exercise_id: str
    repair_class: str
    source_path: str
    target_path: str
    applied: bool
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "exercise_id": self.exercise_id,
            "repair_class": self.repair_class,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "applied": self.applied,
            "note": self.note,
        }


@dataclass(slots=True)
class RuntimeReadyPoolSummary:
    """One runtime-ready curated pool summary."""

    pool_id: str
    retained_level_count: int
    retained_exercise_count: int
    dropped_levels: list[int] = field(default_factory=list)
    dropped_exercise_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "pool_id": self.pool_id,
            "retained_level_count": self.retained_level_count,
            "retained_exercise_count": self.retained_exercise_count,
            "dropped_levels": self.dropped_levels,
            "dropped_exercise_ids": self.dropped_exercise_ids,
        }


@dataclass(slots=True)
class RuntimeReadyRepairReport:
    """Aggregate report for the runtime-ready repair layer."""

    generated_at: str
    staging_root: str
    runtime_ready_root: str
    raw_audit_report: ReferenceBundleAuditReport
    repaired_results: list[ReferenceBundleAuditResult]
    applied_repairs: list[AppliedRepairRecord]
    pool_summaries: list[RuntimeReadyPoolSummary]

    def to_dict(self) -> dict[str, object]:
        failure_counts = Counter(
            item.primary_failure_class for item in self.repaired_results if item.primary_failure_class is not None
        )
        runtime_valid_results = [item for item in self.repaired_results if item.runtime_valid]
        unrepaired = [item for item in self.repaired_results if not item.runtime_valid]
        return {
            "generated_at": self.generated_at,
            "staging_root": self.staging_root,
            "runtime_ready_root": self.runtime_ready_root,
            "summary": {
                "total_audited_bundles": len(self.repaired_results),
                "runnable_bundles_after_repair": len(runtime_valid_results),
                "failing_bundles_after_repair": len(unrepaired),
                "applied_repair_count": sum(1 for item in self.applied_repairs if item.applied),
                "runtime_ready_pool_count": len(self.pool_summaries),
                "counts_by_failure_class_after_repair": dict(sorted(failure_counts.items())),
            },
            "applied_repairs": [item.to_dict() for item in self.applied_repairs],
            "pool_summaries": [item.to_dict() for item in self.pool_summaries],
            "repaired_results": [item.to_dict() for item in self.repaired_results],
            "unrepaired_bundles": [
                {
                    "exercise_id": item.exercise_id,
                    "primary_failure_class": item.primary_failure_class,
                    "repairability": item.repairability,
                    "pool_refs": [ref.to_dict() for ref in item.pool_refs],
                    "notes": item.notes,
                }
                for item in unrepaired
            ],
            "raw_audit_summary": self.raw_audit_report.to_dict()["summary"],
        }


class RuntimeReadyRepairService(ReferenceBundleAuditService):
    """Apply safe repairs and build a runtime-ready curated subset."""

    @property
    def runtime_ready_root(self) -> Path:
        return self.staging_root / "runtime_ready" / "latest"

    @property
    def runtime_ready_repo_root(self) -> Path:
        return self.runtime_ready_root / "repaired"

    @property
    def runtime_ready_reports_root(self) -> Path:
        return self.runtime_ready_root / "reports"

    @property
    def runtime_ready_report_path(self) -> Path:
        return self.runtime_ready_reports_root / "runtime_ready_subset.latest.yml"

    @property
    def applied_repairs_report_path(self) -> Path:
        return self.runtime_ready_reports_root / "applied_repairs.latest.yml"

    @property
    def unrepaired_bundles_report_path(self) -> Path:
        return self.runtime_ready_reports_root / "unrepaired_bundles.latest.yml"

    @property
    def exam_runtime_repair_report_path(self) -> Path:
        return self.runtime_ready_reports_root / "exam_runtime_repair.latest.yml"

    @property
    def exam_runtime_repair_status_path(self) -> Path:
        return self.workspace_root / "EXAM_RUNTIME_REPAIR_STATUS.md"

    def build_runtime_ready_subset(
        self,
        *,
        write: bool = True,
        raw_audit_report: ReferenceBundleAuditReport | None = None,
    ) -> RuntimeReadyRepairReport:
        audit_report = raw_audit_report or self.audit_reference_bundles(write=write)
        repo_root = self.runtime_ready_repo_root.resolve()
        self._prepare_repository_view(
            repo_root,
            exercises_source_root=self.staging_accepted_root / "datasets/exercises",
            pools_source_root=self.curated_datasets_root / "pools",
            reset=write,
        )

        applied_repairs = self._apply_safe_repairs(repo_root, audit_report.results)
        repaired_results = self._audit_existing_repository(repo_root)
        self._drop_unrepaired_exercises(repo_root, repaired_results)
        runtime_valid_ids = {item.exercise_id for item in repaired_results if item.runtime_valid}
        pool_summaries = self._write_runtime_ready_pools(repo_root, runtime_valid_ids)

        report = RuntimeReadyRepairReport(
            generated_at=self.generated_at,
            staging_root=str(self.staging_root),
            runtime_ready_root=str(self.runtime_ready_root),
            raw_audit_report=audit_report,
            repaired_results=repaired_results,
            applied_repairs=applied_repairs,
            pool_summaries=pool_summaries,
        )
        if write:
            self._write_runtime_ready_reports(report)
        return report

    def run_runtime_ready_exam_integration(
        self,
        *,
        write: bool = True,
        repair_report: RuntimeReadyRepairReport | None = None,
    ) -> ExamIntegrationReport:
        report = repair_report or self.build_runtime_ready_subset(write=write)
        repo_root = self.runtime_ready_repo_root.resolve()
        self._reset_repository_runtime_state(repo_root)

        catalog = CatalogService(repo_root)
        catalog.build_index(refresh=True)
        catalog.build_pool_index(refresh=True)

        probe_results = self._probe_curated_exercises(repo_root)
        pool_results = self._run_pool_lifecycle_checks(repo_root)
        remaining_blockers = self._runtime_ready_blockers(report, pool_results, probe_results)
        integration_report = ExamIntegrationReport(
            generated_at=self.generated_at,
            staging_root=str(self.staging_root),
            integration_root=str(repo_root),
            runnable_pool_count=sum(1 for item in pool_results if item.fully_runnable),
            runnable_exercise_count=sum(1 for item in probe_results if item.passed),
            total_curated_exercise_count=len(probe_results),
            remaining_blockers=remaining_blockers,
            pool_results=pool_results,
            probe_results=probe_results,
        )
        if write:
            self.runtime_ready_reports_root.mkdir(parents=True, exist_ok=True)
            self._write_yaml(self.exam_runtime_repair_report_path, integration_report.to_dict())
            self._write_exam_runtime_repair_status(integration_report, report)
        return integration_report

    def _audit_existing_repository(self, repo_root: Path) -> list[ReferenceBundleAuditResult]:
        pool_refs = self._collect_curated_pool_refs(repo_root / "datasets/pools")
        return [
            self._audit_bundle(repo_root, exercise_id, refs)
            for exercise_id, refs in sorted(pool_refs.items())
        ]

    def _apply_safe_repairs(
        self,
        repo_root: Path,
        raw_results: list[ReferenceBundleAuditResult],
    ) -> list[AppliedRepairRecord]:
        applied: list[AppliedRepairRecord] = []
        metadata_root = repo_root / "repair_metadata"
        for result in raw_results:
            manifest_path = self._bundle_root(repo_root, result.exercise_id) / "exercise.yml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            metadata_updates: dict[str, object] = {}
            manifest_changed = False

            for proposal in result.proposed_repairs:
                record = AppliedRepairRecord(
                    exercise_id=result.exercise_id,
                    repair_class=proposal.repair_class,
                    source_path=proposal.source_path,
                    target_path=proposal.target_path,
                    applied=False,
                )
                source_path = Path(proposal.source_path)
                if proposal.repair_class in {
                    "alternate_filename_normalization",
                    "declared_filename_normalization",
                    "harness_main_discovery",
                }:
                    local_target = self._local_repair_target(repo_root, result.exercise_id, proposal)
                    if source_path.exists():
                        local_target.parent.mkdir(parents=True, exist_ok=True)
                        if not local_target.exists():
                            shutil.copyfile(source_path, local_target)
                        record.applied = True
                        record.target_path = str(local_target)
                    else:
                        record.note = "source file missing during repair application"
                elif proposal.repair_class == "legacy_path_normalization":
                    manifest.setdefault("source", {})["origin_path"] = proposal.target_path
                    manifest_changed = True
                    record.applied = True
                elif proposal.repair_class == "generator_filename_typo":
                    metadata_updates["resolved_generator_path"] = proposal.source_path
                    metadata_updates["normalized_generator_target"] = proposal.target_path
                    record.applied = Path(proposal.source_path).exists()
                    if not record.applied:
                        record.note = "generator source missing during repair application"
                applied.append(record)

            if manifest_changed:
                self._write_yaml(manifest_path, manifest)
            if metadata_updates:
                metadata_path = metadata_root / f"{result.exercise_id.replace('.', '-')}.yml"
                metadata_path.parent.mkdir(parents=True, exist_ok=True)
                self._write_yaml(
                    metadata_path,
                    {
                        "exercise_id": result.exercise_id,
                        "metadata_updates": metadata_updates,
                    },
                )
        return applied

    def _local_repair_target(self, repo_root: Path, exercise_id: str, proposal) -> Path:
        bundle_root = self._bundle_root(repo_root, exercise_id)
        target_name = Path(proposal.target_path).name
        if proposal.repair_class == "alternate_filename_normalization":
            return bundle_root / "reference" / target_name
        if proposal.repair_class == "declared_filename_normalization":
            return bundle_root / "starter" / target_name
        return bundle_root / "tests" / "main.c"

    def _drop_unrepaired_exercises(
        self,
        repo_root: Path,
        repaired_results: list[ReferenceBundleAuditResult],
    ) -> None:
        for result in repaired_results:
            if result.runtime_valid:
                continue
            bundle_root = self._bundle_root(repo_root, result.exercise_id)
            if bundle_root.exists():
                shutil.rmtree(bundle_root)

    def _write_runtime_ready_pools(
        self,
        repo_root: Path,
        runnable_exercise_ids: set[str],
    ) -> list[RuntimeReadyPoolSummary]:
        summaries: list[RuntimeReadyPoolSummary] = []
        pools_root = repo_root / "datasets/pools/exams"
        for pool_path in sorted(pools_root.glob("*/pool.yml")):
            payload = yaml.safe_load(pool_path.read_text(encoding="utf-8")) or {}
            transformed, summary = self._runtime_ready_pool_payload(payload, runnable_exercise_ids)
            if summary is None:
                shutil.rmtree(pool_path.parent)
                continue
            self._write_yaml(pool_path, transformed)
            summaries.append(summary)
        return summaries

    def _runtime_ready_pool_payload(
        self,
        payload: dict,
        runnable_exercise_ids: set[str],
    ) -> tuple[dict, RuntimeReadyPoolSummary | None]:
        new_levels: list[dict[str, object]] = []
        dropped_levels: list[int] = []
        dropped_exercise_ids: list[str] = []
        retained_exercise_count = 0
        for original_level in payload.get("levels", []):
            original_level_number = int(original_level.get("level", 0))
            retained_refs = [
                ref
                for ref in original_level.get("exercise_refs", [])
                if ref.get("exercise_id") in runnable_exercise_ids
            ]
            removed_refs = [
                ref.get("exercise_id")
                for ref in original_level.get("exercise_refs", [])
                if ref.get("exercise_id") not in runnable_exercise_ids
            ]
            dropped_exercise_ids.extend(
                exercise_id for exercise_id in removed_refs if isinstance(exercise_id, str)
            )
            if not retained_refs:
                dropped_levels.append(original_level_number)
                continue
            new_level_number = len(new_levels)
            max_picks = original_level.get("max_picks")
            if isinstance(max_picks, int):
                max_picks = min(max_picks, len(retained_refs))
            level_payload = {
                "level": new_level_number,
                "title": original_level.get("title", f"Runtime Ready Level {new_level_number}"),
                "min_picks": min(int(original_level.get("min_picks", 1)), len(retained_refs)),
                "max_picks": max_picks or len(retained_refs),
                "time_limit_seconds": original_level.get("time_limit_seconds"),
                "unlock_if": {
                    "all_of": [new_level_number - 1] if new_level_number > 0 else [],
                    "any_of": [],
                },
                "exercise_refs": retained_refs,
            }
            new_levels.append(level_payload)
            retained_exercise_count += len(retained_refs)

        if not new_levels:
            return (payload, None)

        transformed = dict(payload)
        transformed["title"] = f"{payload['title']} Runtime Ready"
        transformed["description"] = (
            f"{payload['description']} Filtered to the runtime-ready staged subset."
        )
        transformed["levels"] = new_levels
        transformed.setdefault("metadata", {})
        transformed["metadata"]["updated_at"] = self.generated_at
        transformed["metadata"]["status"] = "runtime_ready_subset"
        return (
            transformed,
            RuntimeReadyPoolSummary(
                pool_id=str(payload["id"]),
                retained_level_count=len(new_levels),
                retained_exercise_count=retained_exercise_count,
                dropped_levels=sorted(dropped_levels),
                dropped_exercise_ids=sorted(set(dropped_exercise_ids)),
            ),
        )

    def _reset_repository_runtime_state(self, repo_root: Path) -> None:
        for relative in (
            "storage/sessions",
            "storage/attempts",
            "runtime/reports",
            "runtime/workspaces",
            "runtime/traces",
            "runtime/cache",
            "runtime/manual_submissions",
        ):
            path = repo_root / relative
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)

    def _runtime_ready_blockers(
        self,
        repair_report: RuntimeReadyRepairReport,
        pool_results: list,
        probe_results: list,
    ) -> list[dict[str, object]]:
        blockers: list[dict[str, object]] = []
        for item in repair_report.repaired_results:
            if item.runtime_valid:
                continue
            blockers.append(
                {
                    "type": "unrepaired_bundle",
                    "pool_id": item.pool_refs[0].pool_id if item.pool_refs else "",
                    "exercise_id": item.exercise_id,
                    "reason": f"{item.primary_failure_class} ({item.repairability})",
                }
            )
        for item in probe_results:
            if item.passed:
                continue
            blockers.append(
                {
                    "type": "runtime_ready_probe_failure",
                    "pool_id": item.pool_id,
                    "exercise_id": item.exercise_id,
                    "reason": item.failure_class,
                }
            )
        for item in pool_results:
            if item.fully_runnable:
                continue
            blockers.append(
                {
                    "type": "runtime_ready_pool_failure",
                    "pool_id": item.pool_id,
                    "reason": "; ".join(item.notes) or "one or more lifecycle checks failed",
                }
            )
        return blockers

    def _write_runtime_ready_reports(self, report: RuntimeReadyRepairReport) -> None:
        payload = report.to_dict()
        self.runtime_ready_reports_root.mkdir(parents=True, exist_ok=True)
        self._write_yaml(self.runtime_ready_report_path, payload)
        self._write_yaml(
            self.applied_repairs_report_path,
            {"applied_repairs": [item.to_dict() for item in report.applied_repairs]},
        )
        self._write_yaml(
            self.unrepaired_bundles_report_path,
            {"unrepaired_bundles": payload["unrepaired_bundles"]},
        )

    def _write_exam_runtime_repair_status(
        self,
        integration_report: ExamIntegrationReport,
        repair_report: RuntimeReadyRepairReport,
    ) -> None:
        repair_payload = repair_report.to_dict()
        summary = repair_payload["summary"]
        lines = [
            "# EXAM_RUNTIME_REPAIR_STATUS",
            "",
            f"- Generated at: `{integration_report.generated_at}`",
            f"- Runtime-ready root: `{repair_report.runtime_ready_root}`",
            f"- Runnable pool count after repairs: `{integration_report.runnable_pool_count}`",
            f"- Runnable exercise count after repairs: `{integration_report.runnable_exercise_count}` / `{integration_report.total_curated_exercise_count}`",
            "",
            "## Remaining Blockers",
            "",
        ]
        if integration_report.remaining_blockers:
            for blocker in integration_report.remaining_blockers:
                reason = blocker.get("reason", "")
                exercise_id = blocker.get("exercise_id")
                if exercise_id:
                    lines.append(
                        f"- `{blocker['type']}` on `{exercise_id}` in `{blocker.get('pool_id', '')}`: {reason}"
                    )
                else:
                    lines.append(f"- `{blocker['type']}` on `{blocker.get('pool_id', '')}`: {reason}")
        else:
            lines.append("- None")
        lines.extend(["", "## Unrepaired Bundles Requiring Manual Content Repair", ""])
        unrepaired = repair_payload["unrepaired_bundles"]
        if unrepaired:
            for item in unrepaired[:30]:
                lines.append(
                    f"- `{item['exercise_id']}`: `{item['primary_failure_class']}` "
                    f"(repairability=`{item['repairability']}`)"
                )
        else:
            lines.append("- None")
        lines.extend(["", "## Runtime-Ready Pool Summary", ""])
        for item in repair_report.pool_summaries:
            lines.append(
                f"- `{item.pool_id}`: retained levels=`{item.retained_level_count}`, "
                f"retained exercises=`{item.retained_exercise_count}`, "
                f"dropped levels=`{', '.join(str(level) for level in item.dropped_levels) or 'none'}`"
            )
        lines.extend(["", "## Repair Notes", ""])
        lines.extend(
            [
                f"- Applied safe repairs: `{summary['applied_repair_count']}`",
                f"- Runnable bundles after repair: `{summary['runnable_bundles_after_repair']}`",
                f"- Failing bundles after repair: `{summary['failing_bundles_after_repair']}`",
                "- Runtime-ready pools are derived subsets written only inside the staged runtime_ready layer.",
                "- Raw staged canonical bundles and raw curated pools were not mutated.",
            ]
        )
        self.exam_runtime_repair_status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
