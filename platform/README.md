# Nexus42 Platform

Local-first 42-style learning platform for C practice, piscine progression, and exam simulation.

## Product State

The repository is no longer just a grader skeleton.

Today it provides:

- canonical exercise bundles under `datasets/exercises/`
- canonical pool bundles under `datasets/pools/`
- canonical curriculum sequencing under `datasets/curriculum/`
- a working grading engine for C reference and learner submissions
- piscine session services and exam session services
- learner-facing CLI flows for curriculum browsing, practice, progress, and exam simulation
- learner-facing exam shell helper for workspace readiness checks during an active exam session
- a minimal local dashboard entrypoint

## Canonical Source Of Truth

These paths are authoritative:

- `datasets/exercises/**` -> canonical exercise content
- `datasets/pools/**` -> canonical pool and exam content
- `datasets/curriculum/**` -> canonical learner progression graph

These paths are derived or runtime-only:

- `storage/**` -> persistent learner state only
- `runtime/**` -> execution workspaces, traces, and reports only
- `runtime/staging/import_legacy/**` -> generated import, audit, and repair workspace only

Do not manually curate learner-facing truth inside `storage/`, `runtime/`, or staging imports.

## Current Coverage

- piscine: canonical ready coverage for `c00` to `c06`
- exams: canonical ready starter coverage for `exam00`
- curriculum graph: modeled for `shell00`, `shell01`, `c00` to `c13`, rushes, and exam tracks
- placeholders: shell tracks, rushes, `c07` to `c13`, and higher exam tracks are present as explicit draft or placeholder nodes until canonical content is promoted

## Quick Start

From `platform/`:

```bash
python3 -m pytest
PYTHONPATH="apps/cli/src:apps/dashboard/src:core/catalog/src:core/curriculum/src:core/exams/src:core/grading/src:core/progression/src:core/sandbox/src:core/scheduler/src:core/sessions/src:core/storage/src:tooling" python3 -m platform_cli.main home
PYTHONPATH="apps/cli/src:apps/dashboard/src:core/catalog/src:core/curriculum/src:core/exams/src:core/grading/src:core/progression/src:core/sandbox/src:core/scheduler/src:core/sessions/src:core/storage/src:tooling" python3 -m platform_cli.main curriculum
```

Practice flow:

```bash
PYTHONPATH="apps/cli/src:apps/dashboard/src:core/catalog/src:core/curriculum/src:core/exams/src:core/grading/src:core/progression/src:core/sandbox/src:core/scheduler/src:core/sessions/src:core/storage/src:tooling" python3 -m platform_cli.main start --exercise-id piscine.c00.ft_putchar --workspace /tmp/nexus42-practice
PYTHONPATH="apps/cli/src:apps/dashboard/src:core/catalog/src:core/curriculum/src:core/exams/src:core/grading/src:core/progression/src:core/sandbox/src:core/scheduler/src:core/sessions/src:core/storage/src:tooling" python3 -m platform_cli.main submit /tmp/nexus42-practice
```

Exam flow:

```bash
PYTHONPATH="apps/cli/src:apps/dashboard/src:core/catalog/src:core/curriculum/src:core/exams/src:core/grading/src:core/progression/src:core/sandbox/src:core/scheduler/src:core/sessions/src:core/storage/src:tooling" python3 -m platform_cli.main exam start --workspace /tmp/nexus42-exam
PYTHONPATH="apps/cli/src:apps/dashboard/src:core/catalog/src:core/curriculum/src:core/exams/src:core/grading/src:core/progression/src:core/sandbox/src:core/scheduler/src:core/sessions/src:core/storage/src:tooling" python3 -m platform_cli.main exam shell /tmp/nexus42-exam
PYTHONPATH="apps/cli/src:apps/dashboard/src:core/catalog/src:core/curriculum/src:core/exams/src:core/grading/src:core/progression/src:core/sandbox/src:core/scheduler/src:core/sessions/src:core/storage/src:tooling" python3 -m platform_cli.main exam submit /tmp/nexus42-exam
```

## Architecture Map

- `apps/cli/` -> learner and operator CLI
- `apps/dashboard/` -> local dashboard server
- `core/catalog/` -> canonical content loader
- `core/curriculum/` -> canonical curriculum graph loader
- `core/progression/` -> learner progress read model
- `core/sessions/` -> piscine sessions
- `core/exams/` -> exam sessions
- `core/grading/` -> compile, run, compare, report
- `core/storage/` -> local YAML and JSONL persistence
- `tooling/import_legacy/` -> generated import and repair workflows only

## Intentional Gaps

- shell runtime is not canonical yet
- rush content is modeled but not authored
- `c07` to `c13` and higher exam tracks are represented as placeholders, not silently omitted
- imported legacy exam content remains in staging until it is promoted into canonical datasets
