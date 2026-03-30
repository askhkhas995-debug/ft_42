"""Legacy import tooling package.

This module intentionally uses lazy imports so callers can load the pieces they
need without requiring every optional runtime dependency to already be on
``sys.path``.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING


_EXPORTS = {
    "curated_pools": [
        "CuratedExamPoolService",
        "CuratedPoolBundle",
        "CuratedPoolEntryProvenance",
        "CuratedPoolGap",
        "CuratedPoolsReport",
    ],
    "exam_integration": [
        "CuratedExamIntegrationService",
        "ExamIntegrationReport",
        "ExerciseProbeResult",
        "PoolLifecycleResult",
    ],
    "reference_bundle_audit": [
        "BundlePoolRef",
        "ReferenceBundleAuditReport",
        "ReferenceBundleAuditResult",
        "ReferenceBundleAuditService",
        "RepairProposal",
    ],
    "runtime_ready_repair": [
        "AppliedRepairRecord",
        "RuntimeReadyPoolSummary",
        "RuntimeReadyRepairReport",
        "RuntimeReadyRepairService",
    ],
    "piscine_import": [
        "PiscineDatasetImportReport",
        "PiscineDatasetImportService",
        "PiscineImportedExercise",
        "PiscinePoolRecord",
        "PiscineSourceInventory",
        "PiscineValidationSummary",
    ],
    "manual_curation": [
        "AppliedManualOverride",
        "LegacyManualCurationService",
        "ManualAliasOverride",
        "ManualCurationReport",
        "ManualPoolOverride",
        "ManualReviewRecord",
    ],
    "reconciliation": [
        "AliasMapping",
        "AmbiguousMapping",
        "AutoRepairedReference",
        "LegacyReconciliationService",
        "ReconciliationReport",
        "RepairedPoolSummary",
    ],
    "service": [
        "LegacyImportService",
        "MigrationIssue",
        "MigrationReport",
        "RejectedEntry",
        "StagingImportReport",
        "StagingValidationReport",
    ],
}

_NAME_TO_MODULE = {
    name: module_name for module_name, names in _EXPORTS.items() for name in names
}


def __getattr__(name: str):
    module_name = _NAME_TO_MODULE.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


if TYPE_CHECKING:
    from .curated_pools import (  # noqa: F401
        CuratedExamPoolService,
        CuratedPoolBundle,
        CuratedPoolEntryProvenance,
        CuratedPoolGap,
        CuratedPoolsReport,
    )
    from .exam_integration import (  # noqa: F401
        CuratedExamIntegrationService,
        ExamIntegrationReport,
        ExerciseProbeResult,
        PoolLifecycleResult,
    )
    from .manual_curation import (  # noqa: F401
        AppliedManualOverride,
        LegacyManualCurationService,
        ManualAliasOverride,
        ManualCurationReport,
        ManualPoolOverride,
        ManualReviewRecord,
    )
    from .piscine_import import (  # noqa: F401
        PiscineDatasetImportReport,
        PiscineDatasetImportService,
        PiscineImportedExercise,
        PiscinePoolRecord,
        PiscineSourceInventory,
        PiscineValidationSummary,
    )
    from .reconciliation import (  # noqa: F401
        AliasMapping,
        AmbiguousMapping,
        AutoRepairedReference,
        LegacyReconciliationService,
        ReconciliationReport,
        RepairedPoolSummary,
    )
    from .reference_bundle_audit import (  # noqa: F401
        BundlePoolRef,
        ReferenceBundleAuditReport,
        ReferenceBundleAuditResult,
        ReferenceBundleAuditService,
        RepairProposal,
    )
    from .runtime_ready_repair import (  # noqa: F401
        AppliedRepairRecord,
        RuntimeReadyPoolSummary,
        RuntimeReadyRepairReport,
        RuntimeReadyRepairService,
    )
    from .service import (  # noqa: F401
        LegacyImportService,
        MigrationIssue,
        MigrationReport,
        RejectedEntry,
        StagingImportReport,
        StagingValidationReport,
    )

__all__ = [name for names in _EXPORTS.values() for name in names]
