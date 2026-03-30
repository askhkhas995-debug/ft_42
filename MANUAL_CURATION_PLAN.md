# Manual Curation Plan

## Goal

Add a strict manual curation workflow for the unresolved legacy pool references that remain after automatic reconciliation.

The workflow must:

- read the reconciliation outputs
- generate manual review records for each unresolved reference
- define canonical manual override files
- apply manual overrides only inside a separate repaired staging layer
- leave the raw accepted import and raw reconciliation outputs untouched

## Inputs

The manual curation pass reads:

- `platform/runtime/staging/import_legacy/latest/reconciliation/reports/reconciliation.latest.yml`
- `platform/runtime/staging/import_legacy/latest/reconciliation/reports/alias_mappings.latest.yml`
- `platform/runtime/staging/import_legacy/latest/reconciliation/reports/unresolved_references.remaining.latest.yml`

It also reads:

- accepted staged canonical exercises
- rejected staged entries for root-cause context
- canonical-precedence legacy pool YAML to recover pool level and rank

## Manual Review Records

For every unresolved legacy reference, generate one manual review record containing:

- legacy reference name
- source pool
- source exam group
- likely intended exam/rank
- candidate canonical exercise IDs if any
- why auto-repair was not safe
- issue type:
  - missing content
  - naming mismatch
  - ambiguous mapping
  - malformed legacy reference

## Override Formats

Two canonical override files live under the manual curation staging root:

```text
platform/runtime/staging/import_legacy/latest/manual_curation/overrides/manual_aliases.yml
platform/runtime/staging/import_legacy/latest/manual_curation/overrides/manual_pool_overrides.yml
```

`manual_aliases.yml`:

- root keys: `schema_version`, `aliases`
- each alias entry:
  - `exam_group`
  - `legacy_assignment_name`
  - `canonical_exercise_id`
  - `justification`

`manual_pool_overrides.yml`:

- root keys: `schema_version`, `overrides`
- each override entry:
  - `source_id`
  - `pool_name`
  - `level`
  - `legacy_assignment_name`
  - `canonical_exercise_id`
  - `justification`

Both formats use strict validation with unknown-key rejection.

## Application Rules

1. Manual overrides apply only in the manual curation repaired staging layer.
2. Manual pool overrides are more specific than manual aliases.
3. Manual aliases must remain same-exam-group.
4. Cross-group decisions require a pool-specific manual override.
5. Invalid overrides must fail fast.
6. Raw accepted import must never be mutated.
7. Raw reconciliation output must never be overwritten.

## Staging Output Layout

```text
platform/runtime/staging/import_legacy/latest/manual_curation/
  overrides/
    manual_aliases.yml
    manual_pool_overrides.yml
  repaired/
    datasets/pools/exams/
  reports/
    manual_curation.latest.yml
    manual_review_records.latest.yml
    applied_overrides.latest.yml
    repaired_pools.latest.yml
    unresolved_references.remaining.latest.yml
    validation.latest.yml
```

The workspace summary queue is written to:

```text
MANUAL_REVIEW_QUEUE.md
```

## Tests

Required tests:

- exact manual override application
- invalid override rejection
- override-driven repaired pool resolution

Each test must verify that the repaired output remains isolated from the raw accepted staging import.
