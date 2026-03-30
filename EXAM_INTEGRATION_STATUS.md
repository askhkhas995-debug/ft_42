# EXAM_INTEGRATION_STATUS

- Generated at: `2026-03-07`
- Dataset scope: staged accepted exercise bundles plus the 4 curated staged pools only
- Curated pools exercised: `exam00`, `exam01`, `exam02`, `exam_final`
- Runnable pool count: `0 / 4`
- Runnable exercise count: `34 / 84`

## Pool Status

- `exam00`: not fully runnable
  - First assignment selected: `exams.exam00.fix_z`
  - Verified: start session, first assignment selection, failing submission, retry on same assignment, passing submission, next-level progression, explicit finish session
  - Blocked on: `exams.exam00.rectangle_area` (`wrong_output`) after level 0 completed
  - Reference probes passed: `5 / 13`

- `exam01`: not fully runnable
  - First assignment selected: `exams.exam01.fix_z`
  - Verified: start session, first assignment selection, failing submission, retry on same assignment, passing submission, next-level progression, explicit finish session
  - Blocked on: `exams.exam01.next_character` (`compile_error`) after levels 0 and 1 completed
  - Reference probes passed: `7 / 19`

- `exam02`: not fully runnable
  - First assignment selected: `exams.exam02.volume_cube`
  - Verified: start session, first assignment selection, failing submission, retry on same assignment, explicit finish session
  - Not verified end to end: passing submission for the first assignment or next-level progression
  - Blocked on: `exams.exam02.volume_cube` (`compile_error`) on the staged reference bundle itself
  - Reference probes passed: `9 / 20`

- `exam_final`: not fully runnable
  - First assignment selected: `exams.examfinal.fix_z`
  - Verified: start session, first assignment selection, failing submission, retry on same assignment, passing submission, next-level progression, explicit finish session
  - Blocked on: `exams.examfinal.volume_cuboid` (`wrong_output`) after level 0 completed
  - Reference probes passed: `13 / 32`

## Remaining Blockers

- Curated unresolved gaps inherited from staging remain in `exam_final`:
  - legacy level `9` unresolved assignment `naahio`
  - one excluded legacy level where all references remained unresolved
- Real staged reference-bundle probe failures: `50`
  - `exam00`: `8` failures
  - `exam01`: `12` failures
  - `exam02`: `11` failures
  - `exam_final`: `19` failures
- First blocking lifecycle failures encountered during real session play:
  - `exam00`: `exams.exam00.rectangle_area` (`wrong_output`)
  - `exam01`: `exams.exam01.next_character` (`compile_error`)
  - `exam02`: `exams.exam02.volume_cube` (`compile_error`)
  - `exam_final`: `exams.examfinal.volume_cuboid` (`wrong_output`)

## Integration Notes

- The integration run used a staged-only repository view built from `platform/runtime/staging/import_legacy/latest/accepted/datasets/exercises` and `platform/runtime/staging/import_legacy/latest/curated_pools/v1/datasets/pools`.
- Forced failing submissions used invalid staged C source to verify retry semantics without leaving staged data.
- Explicit `finish_session` worked for all 4 pools even when the pool hit a blocked reference exercise.
- No curated pool is currently fully runnable end to end against the accepted staged exercise bundles.
- The stale expectation in `platform/tests/test_exam_integration_curated.py` (`4` runnable pools and `78` runnable exercises) does not match the current staged curated datasets that were actually executed here.
