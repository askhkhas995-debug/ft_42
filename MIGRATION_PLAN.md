# Migration Plan

## Goal

Import the legacy exam repositories into the canonical dataset format under:

- `platform/datasets/exercises/exams/`
- `platform/datasets/pools/exams/`

The migration must normalize valid content, reject invalid content explicitly, and emit machine-readable migration reports.

## Sources

Primary legacy inputs:

- `ExamPoolRevanced-main`
- `Exam00`
- `Exam01`
- `Exam02`
- `ExamFinal`

Imported legacy artifacts:

- `subjects/<assignment>/subject.en.txt`
- `corrections/<assignment>/`
- `pools/*.yml`

## Output Model

### Canonical exercises

Each legacy assignment becomes a canonical exercise bundle:

```text
platform/datasets/exercises/exams/<group>/<slug>/
  exercise.yml
  statement.md
  starter/
  reference/
  tests/
```

Normalization rules:

- `group` is derived from the legacy exam name: `exam00`, `exam01`, `exam02`, `examfinal`
- `slug` is derived from the legacy assignment directory name
- `exercise_id` becomes `exams.<group>.<slug>`
- `statement.md` is converted from `subject.en.txt`
- `reference/` is populated from legacy `user_files`
- `starter/` is synthesized from expected files when no starter exists in the legacy source
- `tests/main.c` is copied from legacy `common_files/main.c` when present
- `tests/tests.yml` is synthesized as a reference-derived smoke test manifest

### Canonical pools

Each legacy pool file becomes a canonical pool bundle:

```text
platform/datasets/pools/exams/<pool-slug>/
  pool.yml
```

Normalization rules:

- pool ids are derived from the legacy exam group plus the legacy pool filename stem
- pool entries reference canonical `exercise_id` values, never file paths
- each legacy level becomes one canonical level
- unlock rules are synthesized as linear progression from the previous level
- timing fields are normalized deterministically from configurable defaults

## Migration Phases

### 1. Source inventory

Build an inventory for every configured source root:

- discover exam groups
- collect subject directories
- collect correction directories
- collect pool files
- detect duplicate bundles across sources

### 2. Validation and anomaly detection

For each assignment and pool, record issues before writing output:

- missing files
- naming mismatches between `subjects/` and `corrections/`
- malformed `generator.py`
- malformed correction bundles
- bad pool references
- duplicate-source conflicts

Nothing invalid is skipped silently. Every rejected item produces an error in the migration report.

### 3. Exercise normalization

Convert valid legacy assignments into canonical exercise bundles.

Key mapping decisions:

- function-style legacy bundles with `common_files/main.c` normalize to `function_with_harness`
- standalone legacy bundles normalize to `standalone_program`
- source provenance is preserved in `exercise.source`
- legacy whitelist functions become `student_contract.allowed_functions`
- unknown semantics are filled with deterministic migration defaults, not omitted

### 4. Pool normalization

Convert valid legacy pool YAML files into canonical `pool.yml`.

Key mapping decisions:

- legacy `assignments` lists become canonical `exercise_refs`
- canonical selection defaults to `random`
- canonical repeat policy defaults to `avoid_passed`
- canonical cooldown defaults are explicit
- unresolved assignment names fail the pool import and are reported

### 5. Report generation

Emit a reusable migration report under:

- `platform/runtime/reports/import_legacy/`

The report includes:

- source inventory counts
- imported exercises
- imported pools
- rejected exercises
- rejected pools
- all issues with severity, source, location, and message

## Reusability Requirements

The migration layer should be reusable for future imports:

- source roots are configurable
- write mode and dry-run mode are both supported
- migration defaults are centralized
- conversion logic is implemented as library code, not only CLI code
- tests run against synthetic fixtures instead of relying only on the large legacy repos

## Minimal Canonical Extension

The current canonical exercise schema only supports `function_with_harness`.
Legacy exam content requires a second compile mode:

- `standalone_program`

That extension is limited to:

- exercise schema documentation
- catalog validation
- preserving harness optionality for standalone programs

No UI or productivity changes are part of this work.

## Verification

Add tests for:

- valid assignment migration
- valid pool migration
- naming mismatch detection
- malformed generator detection
- malformed correction bundle detection
- bad pool reference detection
- report generation

Run:

- focused migration tests
- canonical catalog validation against migrated fixture output
