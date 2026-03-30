# Legacy Sources

This document describes generated migration inputs and their role after source-of-truth cleanup.

## Canonical Rule

Legacy repositories are not canonical product data.

Canonical learner-facing truth must live only in:

- `datasets/exercises/`
- `datasets/pools/`
- `datasets/curriculum/`

Everything under `runtime/staging/import_legacy/` is generated import, audit, or repair output.

## Current Legacy Inputs

- `ExamPoolRevanced-main`
- `Exam00`
- `Exam01`
- `Exam02`
- `ExamFinal`
- `grademe-main`
- `grademe-mainn`

## Current Precedence In Import Tooling

The implemented import tooling prefers direct exam trees such as `Exam00`, `Exam01`, `Exam02`, and `ExamFinal` when available.
`ExamPoolRevanced-main` is treated as a fallback or supplemental source, not as canonical truth.

## Promotion Policy

Imported content follows this lifecycle:

1. legacy source discovered
2. staging import generated under `runtime/staging/import_legacy/`
3. reconciliation and manual curation applied in staging
4. runtime-ready audit performed in staging
5. only then may content be promoted into canonical `datasets/`

If imported content is unresolved or unstable, it stays in staging and is represented in `datasets/curriculum/tree.yml` as `draft` or `placeholder` rather than silently appearing as canonical content.

## Practical Consequence

- use staging reports for migration work
- use canonical datasets for learner flows
- never build learner UI or curriculum sequencing directly from staging import folders
