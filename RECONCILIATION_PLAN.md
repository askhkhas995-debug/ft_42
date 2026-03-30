# Reconciliation Plan

## Goal

Add a strict, non-destructive reconciliation pass for staged legacy exam imports.

The reconciliation pass must:

- reduce unresolved pool references where an alias mapping is clearly justified
- resolve legacy naming mismatches only when the mapping is unique and safe
- produce canonical alias mappings from legacy names to accepted canonical exercise IDs
- keep all repaired artifacts inside staging
- never mutate or overwrite the raw accepted import

## Inputs

The reconciliation pass operates on the staging import outputs:

- `platform/runtime/staging/import_legacy/latest/reports/staging_import.latest.yml`
- `platform/runtime/staging/import_legacy/latest/reports/unresolved_references.latest.yml`
- `platform/runtime/staging/import_legacy/latest/reports/duplicate_sources.latest.yml`
- `platform/runtime/staging/import_legacy/latest/accepted/`
- `platform/runtime/staging/import_legacy/latest/rejected/`

It also reads the original legacy pool YAML from the canonical-precedence legacy sources so repaired pool candidates are reconstructed from source, not from lossy rejection summaries.

## Strictness Rules

1. Only accepted canonical exercise bundles may be used as repair targets.
2. Alias mappings are same-exam-group only.
3. Alias mappings must be unique and justified.
4. Ambiguous mappings must be rejected and reported.
5. Unresolved references must remain unresolved and reported.
6. Repaired pools must be written to a separate staging subtree.
7. Raw accepted imports and raw rejected imports must remain unchanged.

## Automatic Remediation Classes

Automatically remediable:

- `bad_pool_reference` when a legacy assignment name maps uniquely to one accepted canonical exercise in the same exam group
- `naming_mismatch` when the mismatched legacy name maps uniquely to one accepted canonical exercise in the same exam group

Not automatically remediable:

- `duplicate_source_conflict`
- `missing_file`
- `malformed_generator`
- `malformed_correction_bundle`
- `malformed_pool`
- any alias candidate with multiple plausible canonical targets

## Alias Mapping Strategy

Alias mappings are explicit records:

```text
<exam_group>, <legacy_assignment_name> -> <canonical_exercise_id>
```

Safe mapping order:

1. Exact canonical slug match in the accepted staging catalog.
2. Unique normalized typo-distance match within the same exam group.

If more than one accepted canonical exercise is a plausible target, the alias is ambiguous and must be reported for manual review.

## Second-Pass Pool Repair

The repair workflow runs only on canonical-precedence legacy pool sources.

For each raw rejected pool:

1. Load the original legacy pool YAML from source.
2. Resolve each assignment reference against accepted staged canonical exercises.
3. Apply an explicit alias mapping only when the mapping is justified and unique.
4. Record every auto-repaired reference.
5. Record every still-unresolved reference.
6. Record every ambiguous mapping.
7. Write a repaired canonical `pool.yml` only if every reference in that pool resolves cleanly.

Repaired pools are written under staging only, separate from the raw accepted import.

## Staging Output Layout

```text
platform/runtime/staging/import_legacy/latest/reconciliation/
  repaired/
    datasets/pools/exams/
  reports/
    alias_mappings.latest.yml
    auto_repaired_references.latest.yml
    unresolved_references.remaining.latest.yml
    ambiguous_mappings.latest.yml
    reconciliation.latest.yml
```

Optional validation may use a separate combined staging view that references accepted exercises plus repaired pools, without altering the raw accepted import.

## Reports

The reconciliation pass produces:

- issue classification report for auto-remediable vs manual-only cases
- alias mapping report
- auto-repaired reference report
- unresolved reference remaining report
- ambiguous mapping report
- repaired pool candidate report
- aggregate reconciliation report

## Tests

Required tests:

- exact alias mapping
- ambiguous alias rejection
- repaired pool resolution
- unresolved reference reporting

Each test must verify that repaired content stays separate from raw accepted staging content.
