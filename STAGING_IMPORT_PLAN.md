# Staging Import Plan

## Goal

Add a safe write-mode workflow that imports the legacy exam repositories into an isolated staging dataset root before anything is promoted into `platform/datasets/`.

The staging workflow must:

- normalize legacy assignments into canonical exam exercise bundles
- normalize legacy pool YAML into canonical `pool.yml`
- preserve accepted and rejected content separately
- report duplicates and unresolved references explicitly
- run full catalog and pool validation on the staged accepted datasets

## Source Precedence

The direct exam trees and the `ExamPoolRevanced-main` copies represent the same logical content layer.

Canonical source of truth:

- `Exam00`
- `Exam01`
- `Exam02`
- `ExamFinal`

Alias duplicate layer:

- `ExamPoolRevanced-main/Exam00`
- `ExamPoolRevanced-main/Exam01`
- `ExamPoolRevanced-main/Exam02`
- `ExamPoolRevanced-main/ExamFinal`

Rules:

1. Prefer the direct exam tree when both direct and alias copies exist.
2. Use the `ExamPoolRevanced-main` copy only as a fallback when the direct exam tree for that exam group is absent.
3. If duplicate content is byte-equivalent after normalization, keep the higher-precedence source and record the lower-precedence source in the duplicate-source report.
4. If duplicate content conflicts after normalization, keep the higher-precedence source, reject the lower-precedence source, and record a blocking duplicate conflict.
5. Never silently merge conflicting duplicates.

## Staging Layout

Write-mode staging output lives under:

```text
platform/runtime/staging/import_legacy/latest/
```

Subtrees:

```text
accepted/
  datasets/exercises/exams/
  datasets/pools/exams/
rejected/
  exercises/
  pools/
reports/
```

Accepted content is valid canonical output intended for catalog loading.
Rejected content contains per-entry YAML rejection records with issue codes, locations, and messages.

## Reports

The staging workflow produces:

- accepted exercise report
- accepted pool report
- rejected entry report
- duplicate-source report
- unresolved-reference report
- staged validation report
- aggregate staging import report

It also produces a workspace summary document:

```text
STAGING_IMPORT_STATUS.md
```

## Validation

Validation runs against the staged accepted root, not the final datasets root.

The validation pass uses the existing catalog and pool validators to confirm:

- exercise manifests are canonical and strict
- pool manifests are canonical and strict
- all staged pool exercise references resolve against staged exercise IDs
- variants referenced by pools exist

Validation failures are blocking and must be included in both the aggregate staging report and `STAGING_IMPORT_STATUS.md`.

## Rejected Entries

Rejected entries are grouped per logical source item:

- exercise rejection: keyed by assignment name
- pool rejection: keyed by pool filename
- source rejection: keyed by source-level failures when no assignment or pool key exists

Each rejection record stores:

- source id
- exam group
- location
- reason codes
- human-readable messages

## Reusability

Keep the importer reusable by:

- retaining the existing final-write migration path
- exposing staging import as a separate service method
- keeping source precedence declarative
- writing machine-readable YAML reports
- making the CLI target explicit with `--write-target staging|final`

## Initial Deliverables

1. Add `stage_import(...)` to the legacy import service.
2. Add staging report and validation dataclasses.
3. Add staging output writers for accepted, rejected, duplicate, unresolved, and aggregate reports.
4. Add `STAGING_IMPORT_STATUS.md` generation.
5. Add tests for precedence, rejected separation, unresolved references, and staged validation.
6. Run the staging workflow on the real legacy sources and record the resulting counts.
