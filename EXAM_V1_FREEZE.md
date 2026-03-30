# EXAM_V1_FREEZE

- Freeze date: `2026-03-07`
- Release label: `Exam Platform v1`
- Official runtime dataset: `/home/xapet/Desktop/f/platform/runtime/staging/import_legacy/frozen/exam_platform_v1/repository_root`
- Frozen reports: `/home/xapet/Desktop/f/platform/runtime/staging/import_legacy/frozen/exam_platform_v1/reports`

## Release Record

- Runnable pools: `4`
- Runnable exercise references: `34`
- Excluded unrepaired bundles: `49`
- Applied safe repairs in the frozen runtime_ready source: `2`

The frozen v1 release is the current `runtime_ready` staged subset, promoted as the official exam runtime dataset without modifying the raw staged canonical data.

## Scope

Included in v1:

- the derived runtime-ready staged subset only
- `4 / 4` derived curated exam pools runnable end to end
- `34 / 34` runtime-ready exercise references runnable end to end

Excluded from v1:

- `49` unrepaired bundles that still require manual content repair
- unresolved legacy content that never entered the runtime-ready subset

## Known Gaps

- Curated unresolved content gaps inherited from `exam_final`: `2`
- These remain known dataset gaps, but they are not v1 release blockers because the frozen runtime-ready subset is already runnable as released.

## Backlog Policy

The `49` unrepaired bundles are backlog content-repair work, not release blockers for Exam Platform v1.

They remain out of the frozen v1 runtime dataset until a future staged content-repair pass:

- repairs the bundle safely or via manual content correction
- revalidates runtime viability
- reruns exam integration on the expanded subset
- promotes a new derived release candidate without mutating the frozen v1 root

## Freeze Contract

Future content-repair passes may expand v1 coverage, but they must not break the frozen v1 contract.

Rules:

1. Do not mutate `/home/xapet/Desktop/f/platform/runtime/staging/import_legacy/frozen/exam_platform_v1/`.
2. Do not mutate the raw staged canonical roots under `platform/runtime/staging/import_legacy/latest/accepted/` or `platform/runtime/staging/import_legacy/latest/curated_pools/`.
3. Run future repairs in a new derived staging layer, not inside the frozen v1 root.
4. Treat the frozen v1 runnable baseline as:
   - `4` runnable pools
   - `34` runnable exercise references
5. A future expansion pass may only supersede v1 if it preserves or improves that runnable baseline.
6. Every future expansion pass must emit fresh staged reports and an end-to-end integration rerun before promotion.

## Promotion Contract

To promote a future content-repair pass beyond v1:

1. Build a new derived runtime-ready candidate in a separate staging path.
2. Re-run reference bundle audit and repair reports.
3. Re-run real exam-mode integration on that candidate only.
4. Compare the candidate against the frozen v1 baseline.
5. Freeze the new candidate under a new versioned path; never overwrite the v1 freeze.
