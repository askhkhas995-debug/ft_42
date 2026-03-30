# Reference Bundle Repair Plan

## Goal

Add a strict staged audit and repair workflow for curated exam exercise bundles whose canonical structure is valid but whose runtime bundle content is not yet runnable.

The workflow must:

- audit every staged curated exam exercise bundle for runtime viability
- classify structural validity separately from runtime validity
- identify which defects are safely auto-repairable and which require manual content repair
- write repaired outputs only into a separate staging layer
- produce a curated runtime-ready subset for real exam-mode integration
- re-run exam integration against that repaired subset

## Current Baseline

Current real staged integration status:

- `0 / 4` curated pools fully runnable
- `34 / 84` curated pool exercise references runnable
- `50` reference-bundle runtime failures
- `2` unresolved curated gaps remain in `exam_final`

This means the session architecture is working, but the staged canonical bundle content is not yet runtime-ready.

## Inputs

The workflow reads from the existing staged layers only:

- `platform/runtime/staging/import_legacy/latest/accepted/datasets/exercises/`
- `platform/runtime/staging/import_legacy/latest/curated_pools/v1/datasets/pools/`
- `platform/runtime/staging/import_legacy/latest/curated_pools/v1/reports/curated_pools.latest.yml`
- `platform/runtime/staging/import_legacy/latest/exam_integration/` reports for real runtime evidence

It must not mutate:

- raw accepted staged canonical exercises
- raw curated staged pools
- prior staging reconciliation or manual curation outputs

## Separation of Concerns

Structural validity and runtime validity must be tracked separately.

Structural validity means the bundle is catalog-loadable and schema-valid.

Runtime validity means the bundle can actually be used by the grading and exam session path end to end.

Rules:

1. A structurally valid bundle may still be runtime-invalid.
2. Runtime repair must never silently rewrite structurally valid source data in place.
3. Runtime-ready outputs must be derived artifacts in a separate staging subtree.
4. Manual content bugs must remain explicitly reported rather than auto-massaged.

## Audit Pass

Add a reference bundle audit pass that runs against every canonical exercise bundle referenced by the 4 curated pools:

- `exam00`
- `exam01`
- `exam02`
- `exam_final`

For each bundle, the audit must check:

- required files present
- reference implementation present
- generator path valid
- harness path valid
- compile command resolvable
- test bundle runnable
- grading path executable end to end

The audit should run in increasing strictness order so reports distinguish where the failure occurred:

1. manifest and file-layout checks
2. path resolution checks
3. compile-plan derivation checks
4. harness and test fixture checks
5. reference compile checks
6. grading execution checks

## Failure Classification

Every failing bundle must be assigned one primary failure class, with optional secondary notes.

Initial failure classes:

- `missing_reference_file`
- `missing_required_file`
- `broken_generator_path`
- `broken_harness_path`
- `compile_command_unresolvable`
- `compile_failure_in_reference`
- `malformed_metadata`
- `malformed_test_fixture`
- `unsupported_standalone_function_mismatch`
- `missing_expected_user_file_mapping`
- `runtime_wrong_output`
- `runtime_crash`
- `runtime_nonzero_exit`
- `unknown_runtime_failure`

Classification policy:

1. Prefer the earliest concrete root cause.
2. Do not classify `wrong_output` as a structural issue.
3. Distinguish “cannot run” from “runs but fails”.
4. Preserve raw evidence paths for every classification.

## Safe Repair Scope

Only automatically repair defects that are deterministic, local, and reversible.

Automatically repairable classes:

- alternate subject or reference filenames when a unique safe target exists
- generator filename typos
- harness `main.c` discovery when a unique valid harness exists
- declared filename normalization where safe
- common legacy path normalization

Not automatically repairable:

- wrong reference algorithm or incorrect business logic
- ambiguous file matches
- conflicting multiple plausible harnesses
- incomplete tests or semantically broken fixtures
- standalone/function semantic mismatch when intent is not uniquely recoverable
- any repair that rewrites source code behavior without a deterministic justification

## Repair Strategy

The repair pass operates on copied bundle artifacts only.

For each audited bundle:

1. Read the raw staged canonical bundle.
2. Apply only allowed normalization rules.
3. Rebuild a repaired bundle candidate in a separate runtime-ready layer.
4. Re-run the same audit on the repaired candidate.
5. Mark the candidate:
   - runtime-ready
   - still failing but structurally valid
   - manual content repair required

Safe repair rules must be explicit and machine-readable. Each applied repair record should include:

- canonical exercise id
- repair class
- source path
- repaired path
- justification

## Staging Output Layout

Write new outputs under separate staging subtrees:

```text
platform/runtime/staging/import_legacy/latest/reference_bundle_audit/
  reports/
    reference_bundle_audit.latest.yml
    failure_classification.latest.yml
    affected_pools.latest.yml

platform/runtime/staging/import_legacy/latest/runtime_ready/
  repaired/
    datasets/exercises/exams/
    datasets/pools/exams/
  reports/
    applied_repairs.latest.yml
    unrepaired_bundles.latest.yml
    runtime_ready_subset.latest.yml
    exam_runtime_repair.latest.yml
```

Workspace summaries:

- `REFERENCE_BUNDLE_AUDIT_STATUS.md`
- `EXAM_RUNTIME_REPAIR_STATUS.md`

## Curated Runtime-Ready Subset

Build a derived curated runtime-ready subset from:

- repaired runtime-ready exercise bundles
- unrepaired but already runnable bundles
- the 4 curated pools filtered or revalidated against the runtime-ready exercise set

Rules:

1. Keep raw curated pools unchanged.
2. Write any filtered or repaired pool manifests only into the runtime-ready staging layer.
3. Preserve pool-level reporting of which levels lost coverage due to unrepaired bundles.
4. Do not claim a pool runnable unless the real exam session path completes on the runtime-ready layer.

## Audit Reporting

Generate `REFERENCE_BUNDLE_AUDIT_STATUS.md` with:

- total audited bundles
- runnable bundles
- failing bundles
- counts by failure class
- affected pools and levels

The machine-readable audit report must also include:

- structural-valid vs runtime-valid counts
- per-bundle evidence paths
- per-pool affected exercise IDs
- repairability classification:
  - auto-repairable
  - manual-content-repair
  - unresolved-gap-derived

## Post-Repair Integration

After building the runtime-ready repaired layer:

1. run real exam-mode integration against the runtime-ready subset
2. record runnable pools and runnable exercise references after repair
3. list bundles still blocking full pool execution
4. separate unrepaired content defects from unresolved curated gaps

Generate `EXAM_RUNTIME_REPAIR_STATUS.md` with:

- runnable pool count after repairs
- runnable exercise count after repairs
- remaining blockers
- unrepaired bundles requiring manual content repair

## Suggested Implementation Shape

Add new tooling alongside the existing import-legacy workflow:

- `platform/tooling/import_legacy/reference_bundle_audit.py`
- `platform/tooling/import_legacy/runtime_ready_repair.py`

Expose service entrypoints similar to the existing staging flows:

- `audit_reference_bundles(...)`
- `build_runtime_ready_subset(...)`
- `run_runtime_ready_exam_integration(...)`

Keep report dataclasses and status writers parallel to:

- staging import
- reconciliation
- manual curation
- curated pools
- exam integration

## Tests

Required tests:

- audit detects missing reference file
- audit detects harness path breakage
- audit distinguishes compile failure from wrong-output runtime failure
- safe filename normalization repair
- safe harness discovery repair
- repaired outputs remain isolated from raw staged canonical bundles
- runtime-ready subset excludes unrepaired bundles
- post-repair exam integration rerun uses only runtime-ready staged data

## Initial Deliverables

1. Add the reference bundle audit service and reports.
2. Add `REFERENCE_BUNDLE_AUDIT_STATUS.md` generation.
3. Add safe auto-repair rules for deterministic path and filename defects only.
4. Add the runtime-ready repaired staging layer and reports.
5. Rebuild a curated runtime-ready subset from staged data only.
6. Re-run real exam integration against the runtime-ready subset.
7. Add `EXAM_RUNTIME_REPAIR_STATUS.md`.
