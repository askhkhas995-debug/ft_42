# REFERENCE_BUNDLE_AUDIT_STATUS

- Generated at: `2026-03-07T12:52:40Z`
- Audit root: `/home/xapet/Desktop/f/platform/runtime/staging/import_legacy/latest/reference_bundle_audit/latest/repository_root`
- Total audited bundles: `83`
- Runnable bundles: `34`
- Failing bundles: `49`

## Counts By Failure Class

- `malformed_test_fixture`: `25`
- `reference_compile_failure`: `22`
- `runtime_crash`: `1`
- `runtime_wrong_output`: `1`

## Affected Pools And Levels

- `exams.curated.exam00.v1`: levels `1, 3, 5, 6`
- `exams.curated.exam01.v1`: levels `2, 3, 4, 5, 6, 7, 9`
- `exams.curated.exam02.v1`: levels `0, 2, 4, 5, 6, 7, 9`
- `exams.curated.exam_final.v1`: levels `1, 3, 5, 7, 8, 10, 11, 12, 13, 14`

## Failing Bundle Samples

- `exams.exam00.frequency_character`: `reference_compile_failure` (repairability=`manual_content_repair`)
- `exams.exam00.ft_abs`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam00.ft_div`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam00.ft_isdigit`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam00.ft_mod`: `reference_compile_failure` (repairability=`manual_content_repair`)
- `exams.exam00.ft_pow`: `reference_compile_failure` (repairability=`manual_content_repair`)
- `exams.exam00.rectangle_area`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam00.triangle_area`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam01.factorial_number`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam01.ft_abs`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam01.ft_pow`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam01.ft_sqrt`: `reference_compile_failure` (repairability=`manual_content_repair`)
- `exams.exam01.ft_str_is_alpha`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam01.ft_strcat`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam01.ft_strdiff`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam01.ft_strjoin`: `malformed_test_fixture` (repairability=`manual_content_repair`)
- `exams.exam01.next_character`: `reference_compile_failure` (repairability=`manual_content_repair`)
- `exams.exam01.prev_charcter`: `reference_compile_failure` (repairability=`manual_content_repair`)
- `exams.exam01.remove_duplicate`: `reference_compile_failure` (repairability=`manual_content_repair`)
- `exams.exam01.sum_n`: `reference_compile_failure` (repairability=`manual_content_repair`)
