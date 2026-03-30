# Import Report Summary

## Dry-Run Snapshot

Dry-run migration result for the current workspace:

- sources analyzed: 8
- exercises normalized successfully: 85
- pools normalized successfully: 1
- total issues: 136
- errors: 136
- warnings: 0

All recorded issues are currently classified as blocking errors for the affected item.

## Issue Categories

| Issue Type | Count | Severity | Blocks Import | Proposed Automatic Fix Strategy | Manual Review Required |
| --- | ---: | --- | --- | --- | --- |
| duplicate_source_conflict | 86 | error | Partial only. Blocks the lower-priority duplicate, but not the preferred source copy. | Add source-dedup policy with precedence plus content-hash equality detection. If two sources are byte-identical, downgrade to duplicate notice; if different, keep preferred source and quarantine the lower-priority copy in the report. | Yes. Conflicting duplicates should be reviewed before trusting the chosen canonical source. |
| bad_pool_reference | 22 | error | Yes, for the affected pool. A pool with unresolved assignments is rejected. | Add a controlled alias-normalization layer for known name drift such as typo variants, then re-resolve against imported exercise ids. Keep unresolved refs as hard failures. | Yes. Alias fixes can be wrong if the legacy pool intended a different assignment. |
| missing_file | 14 | error | Yes, for the affected exercise or pool. | Auto-detect missing optional assets only where the canonical format allows synthesis. For required legacy inputs, emit stub placeholders only in an explicit repair mode and preserve the error in the report. | Yes. Missing subject text, correction bundles, generators, or declared user files all need confirmation. |
| naming_mismatch | 6 | error | Yes, for the affected exercise pair. | Add slug-normalization and typo-alias heuristics between `subjects/` and `corrections/`, then match only when the rest of the bundle agrees. | Yes. Name-only matching is not safe enough to apply silently. |
| malformed_generator | 4 | error | Yes, for the affected exercise. | Support a degraded migration path that synthesizes canonical smoke tests when `generator.py` is missing or unusable, while keeping generator fidelity marked as failed in provenance. | Yes. Missing generators reduce trust in migrated tests and should be reviewed. |
| malformed_correction_bundle | 4 | error | Yes, for the affected exercise. | Add targeted repair heuristics for known legacy shapes: infer compile mode from bundle topology, validate declared `user_files`, and detect wrong filenames against actual contents. | Yes. These cases indicate structural inconsistency inside the correction bundle. |

## Category Notes

### 1. `duplicate_source_conflict` (86)

This is the largest bucket by far. It reflects the same logical assignment or pool appearing in both:

- `ExamPoolRevanced-main/<ExamXX>/...`
- direct `ExamXX/...`

Current importer behavior is intentionally strict: it imports the first source by precedence and records every non-identical duplicate as a conflict.

Observed pattern:

- 13 assignment conflicts against `ExamPoolRevanced-main/Exam00`
- 18 assignment conflicts against `ExamPoolRevanced-main/Exam01`
- 21 assignment conflicts against `ExamPoolRevanced-main/Exam02`
- 33 assignment conflicts against `ExamPoolRevanced-main/ExamFinal`
- 1 pool conflict against `ExamPoolRevanced-main/Exam00`

Interpretation:

- This is mostly a source-governance problem, not a schema problem.
- It does not stop the entire migration run, but it does block trusting the lower-priority duplicate copy.

### 2. `bad_pool_reference` (22)

These are pool entries that reference assignments that did not resolve to imported canonical exercise ids.

Observed unresolved names include:

- `prev_character`
- `ascii_character_v2`
- `binary_to_decimal`
- `add_complex`
- `sub_complex`
- `naahio`
- `sum_n`

Root causes are mixed:

- pool name differs from assignment directory slug
- referenced assignment was rejected earlier due to missing files or malformed bundle structure
- subject/correction naming drift exists in the legacy repo

Interpretation:

- This blocks canonical pool import for the affected pool.
- A safe fix needs resolution rules plus a report trail, not silent rewriting.

### 3. `missing_file` (14)

This bucket covers direct absence of required legacy inputs.

Observed missing-file subtypes:

- missing correction bundle for an existing subject
- missing subject file for an existing correction bundle
- missing `generator.py`
- missing declared legacy user file

Interpretation:

- This is a hard blocker for the affected item because the importer cannot establish a complete canonical exercise bundle from incomplete legacy data.

### 4. `naming_mismatch` (6)

These are structural mismatches where a subject and correction bundle do not pair cleanly by assignment name.

Observed examples:

- correction exists without matching subject
- subject exists without matching correction

Examples in the current workspace include:

- `circle_perimeter`
- `naahio`
- `sum_n`

Interpretation:

- This is often the upstream cause behind both missing-file and bad-pool-reference failures.
- It should be fixed before rerunning bulk imports.

### 5. `malformed_generator` (4)

These are legacy correction bundles that fail generator requirements.

Current observed form:

- `generator.py` missing entirely

Examples:

- `binary_to_decimal` in both `Exam02` and `ExamFinal`, and in their `ExamPoolRevanced-main` copies

Interpretation:

- The importer currently treats generators as required legacy evidence and rejects the bundle when they are absent.
- A future degraded mode could still synthesize canonical smoke tests, but that should remain explicit and audited.

### 6. `malformed_correction_bundle` (4)

These are correction bundles whose internal structure is inconsistent even when the directory exists.

Observed forms:

- compile mode cannot be determined cleanly from the legacy bundle
- declared user file is missing or mismatched

Examples:

- `prev_charcter` could not be classified cleanly as `function_with_harness` or `standalone_program`
- `sub_complex` declares a user-file layout that does not match the files actually present

Interpretation:

- These are high-signal quality failures and should not be auto-imported without verification.

## Recommended Prioritization

1. Resolve duplicate-source policy first, because it accounts for 86 of 136 issues and will materially reduce noise.
2. Fix naming mismatches and bad pool references next, because that is what prevents additional canonical pool imports.
3. Add degraded import handling for missing generators only after structural bundle mismatches are understood.
4. Keep missing files and malformed correction bundles as hard blockers until explicitly repaired.
