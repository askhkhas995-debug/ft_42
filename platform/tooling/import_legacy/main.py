"""Legacy repository import entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from import_legacy.curated_pools import CuratedExamPoolService
    from import_legacy.reference_bundle_audit import ReferenceBundleAuditService
    from import_legacy.manual_curation import LegacyManualCurationService
    from import_legacy.reconciliation import LegacyReconciliationService
    from import_legacy.runtime_ready_repair import RuntimeReadyRepairService
    from import_legacy.piscine_import import PiscineDatasetImportService
    from import_legacy.service import LegacyImportService
else:
    from .curated_pools import CuratedExamPoolService
    from .reference_bundle_audit import ReferenceBundleAuditService
    from .manual_curation import LegacyManualCurationService
    from .reconciliation import LegacyReconciliationService
    from .runtime_ready_repair import RuntimeReadyRepairService
    from .piscine_import import PiscineDatasetImportService
    from .service import LegacyImportService


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="import-legacy")
    parser.add_argument(
        "--workspace-root",
        default=str(_workspace_root()),
        help="Workspace root containing legacy sources and the platform directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and normalize inputs without writing canonical output bundles.",
    )
    parser.add_argument(
        "--write-target",
        choices=("staging", "final"),
        default="staging",
        help="Choose whether write mode targets the isolated staging area or the final platform datasets root.",
    )
    parser.add_argument(
        "--workflow",
        choices=("import", "reconcile", "curate", "curated-pools", "reference-audit", "runtime-ready", "piscine-import"),
        default="import",
        help="Run the initial staging import workflow, the second-pass reconciliation workflow, the manual curation workflow, curated pool generation, reference bundle audit, runtime-ready repair workflow, or the first staged piscine dataset import workflow.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if args.workflow == "piscine-import":
        service = PiscineDatasetImportService(Path(args.workspace_root))
        report = service.build_first_pass(write=not args.dry_run)
        payload = report.to_dict()["summary"]
        print(
            "piscine_import:"
            f" sources={sum(payload['discovered_source_counts'].values())}"
            f" exercises={sum(payload['imported_canonical_exercise_counts'].values())}"
            f" pools={sum(payload['imported_pool_counts'].values())}"
            f" catalog_valid={payload['catalog_valid']}"
            f" pool_valid={payload['pool_valid']}"
            f" session_progression_valid={payload['session_progression_valid']}"
        )
        if not args.dry_run:
            print(service.report_path)
            print(service.status_path)
        return 0 if payload["catalog_valid"] and payload["session_progression_valid"] else 1

    if args.workflow == "runtime-ready":
        service = RuntimeReadyRepairService(Path(args.workspace_root))
        repair_report = service.build_runtime_ready_subset(write=not args.dry_run)
        integration_report = service.run_runtime_ready_exam_integration(
            write=not args.dry_run,
            repair_report=repair_report,
        )
        payload = repair_report.to_dict()["summary"]
        print(
            "runtime_ready:"
            f" repaired={payload['applied_repair_count']}"
            f" runnable_bundles={payload['runnable_bundles_after_repair']}"
            f" failing_bundles={payload['failing_bundles_after_repair']}"
            f" runnable_pools={integration_report.runnable_pool_count}"
            f" runnable_exercises={integration_report.runnable_exercise_count}"
        )
        if not args.dry_run:
            print(service.runtime_ready_report_path)
            print(service.exam_runtime_repair_report_path)
            print(service.exam_runtime_repair_status_path)
        return 0 if not integration_report.remaining_blockers else 1

    if args.workflow == "reference-audit":
        service = ReferenceBundleAuditService(Path(args.workspace_root))
        report = service.audit_reference_bundles(write=not args.dry_run)
        payload = report.to_dict()["summary"]
        print(
            "reference_bundle_audit:"
            f" total={payload['total_audited_bundles']}"
            f" runnable={payload['runnable_bundles']}"
            f" failing={payload['failing_bundles']}"
        )
        if not args.dry_run:
            print(service.audit_report_path)
            print(service.audit_status_path)
        return 0 if payload["failing_bundles"] == 0 else 1

    if args.workflow == "curated-pools":
        service = CuratedExamPoolService(Path(args.workspace_root))
        report = service.build_curated_pools(write=not args.dry_run)
        payload = report.to_dict()["summary"]
        print(
            "curated_pools:"
            f" usable={payload['usable_pool_count']}"
            f" unresolved_gaps={payload['unresolved_gap_count']}"
            f" validation_ok={payload['validation_ok']}"
        )
        if not args.dry_run:
            print(service.curated_report_path)
            print(service.curated_status_path)
        return 0 if payload["validation_ok"] else 1

    if args.workflow == "curate":
        service = LegacyManualCurationService(Path(args.workspace_root))
        report = service.curate_manual_overrides(write=not args.dry_run)
        payload = report.to_dict()["summary"]
        print(
            "manual_curation:"
            f" review={payload['manual_review_count']}"
            f" alias_overrides={payload['manual_alias_override_count']}"
            f" pool_overrides={payload['manual_pool_override_count']}"
            f" applied={payload['applied_override_count']}"
            f" repaired_pools={payload['repaired_pool_count']}"
            f" unresolved={payload['remaining_unresolved_count']}"
            f" validation_ok={payload['validation_ok']}"
        )
        if not args.dry_run:
            print(service.manual_report_path)
            print(service.manual_review_queue_path)
        return 0 if payload["remaining_unresolved_count"] == 0 else 1

    if args.workflow == "reconcile":
        service = LegacyReconciliationService(Path(args.workspace_root))
        report = service.reconcile_staging(write=not args.dry_run)
        payload = report.to_dict()["summary"]
        print(
            "reconcile_staging:"
            f" aliases={payload['alias_mapping_count']}"
            f" repaired_refs={payload['auto_repaired_reference_count']}"
            f" unresolved={payload['unresolved_reference_count']}"
            f" ambiguous={payload['ambiguous_mapping_count']}"
            f" repaired_pools={payload['repaired_pool_count']}"
            f" validation_ok={payload['validation_ok']}"
        )
        if not args.dry_run:
            print(service.reconciliation_report_path)
        return 0 if payload["unresolved_reference_count"] == 0 and payload["ambiguous_mapping_count"] == 0 else 1

    service = LegacyImportService(Path(args.workspace_root))
    if args.write_target == "staging":
        report = service.stage_import(write=not args.dry_run)
        payload = report.to_dict()["summary"]
        print(
            "stage_import:"
            f" exercises={payload['accepted_exercise_count']}"
            f" pools={payload['accepted_pool_count']}"
            f" rejected={payload['rejected_count']}"
            f" duplicates={payload['duplicate_count']}"
            f" unresolved={payload['unresolved_reference_count']}"
            f" blocking={payload['blocking_error_count']}"
            f" validation_ok={payload['validation_ok']}"
        )
        if not args.dry_run:
            print(service.staging_report_path)
            print(service.staging_status_path)
        return 0 if payload["blocking_error_count"] == 0 else 1

    report = service.migrate(write=not args.dry_run)
    payload = report.to_dict()["summary"]
    print(
        "import_legacy:"
        f" exercises={payload['exercise_count']}"
        f" pools={payload['pool_count']}"
        f" issues={payload['issue_count']}"
        f" errors={payload['error_count']}"
        f" warnings={payload['warning_count']}"
    )
    if not args.dry_run:
        print(service.report_path)
    return 0 if payload["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
