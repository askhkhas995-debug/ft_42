# DESIGN

## 1. Purpose

This document defines the implementation contract for a new local-first learning and exam platform for C training. The platform replaces the current split between content repositories, ad hoc correction folders, and runtime-specific scripts with:

- one canonical dataset model
- one modular grading engine
- one event-driven session model
- multiple learning and simulation modes over the same content

This is a technical specification, not an implementation.

## 2. Design Goals

- Dataset-driven: exercises, pools, labs, book examples, and rubrics are declarative.
- Runtime-agnostic: CLI, local dashboard, and future services consume the same contracts.
- Mode-aware: piscine, exam, observation, experiment, bug injection, completion, and prediction are first-class modes.
- Local-first: everything works without network access.
- Traceable: every attempt, grade, failure mode, and productivity signal is evented and reproducible.
- Safe: compile and runtime execution happen inside a constrained sandbox.

## 3. Repository Layout

The platform repository root SHALL use the following structure.

```text
platform/
  DESIGN.md
  README.md
  apps/
    cli/
      README.md
      config/
      src/
      templates/
    dashboard/
      README.md
      public/
      src/
      widgets/
  core/
    catalog/
      README.md
      src/
    sessions/
      README.md
      src/
    scheduler/
      README.md
      src/
    grading/
      README.md
      src/
      contracts/
      builtins/
        languages/
        comparators/
        analyzers/
        reporters/
    sandbox/
      README.md
      src/
      profiles/
    analytics/
      README.md
      src/
    timeline/
      README.md
      src/
    storage/
      README.md
      src/
  datasets/
    schemas/
      exercise.schema.yml
      pool.schema.yml
      grading_report.schema.yml
      attempt_log.schema.yml
      session.schema.yml
      timeline_event.schema.yml
      book_asset.schema.yml
    exercises/
      piscine/
        c00/
        c01/
        c02/
        c03/
        c04/
        c05/
        c06/
        c07/
        c08/
        c09/
        c10/
        c11/
        c12/
        c13/
      exams/
        exam00/
        exam01/
        exam02/
        exam_final/
      knr/
      theory_to_practice/
      labs/
      bug_injection/
      completion/
      prediction/
    pools/
      piscine/
      exams/
      labs/
      adaptive/
    books/
      knr/
        assets/
        manifests/
      theory_to_practice/
        assets/
        manifests/
    rubrics/
    fixtures/
      shared/
      c/
    imports/
      raw/
      normalized/
      audit/
  runtime/
    workspaces/
    sandboxes/
    toolchains/
    cache/
    traces/
    reports/
    exports/
  storage/
    users/
    sessions/
    attempts/
    events/
    analytics/
    snapshots/
    indexes/
  tooling/
    validate/
    migrate/
    import_books/
    import_legacy/
    inspect/
    doctor/
  docs/
    architecture/
    migration/
    contracts/
```

## 4. Dataset Conventions

- Every exercise lives in a single directory named by `slug`.
- Every exercise directory contains exactly one `exercise.yml`.
- Every pool file contains exactly one `pool.yml`.
- All IDs are globally unique and stable.
- All paths inside manifests are relative to the manifest location.
- All timestamps use ISO-8601 UTC strings.
- All durations are integer seconds unless otherwise stated.
- All append-only logs use JSON Lines on disk even if their schemas are documented in YAML here.

## 5. Exercise Dataset Contract

Each exercise directory SHALL use this layout.

```text
datasets/exercises/<track>/<group>/<slug>/
  exercise.yml
  statement.md
  starter/
  reference/
  tests/
  fixtures/
  hints/
  assets/
  variants/
```

### 5.1 `exercise.yml` exact schema

```yaml
schema_version: 1

id: string                      # required, global unique id, e.g. piscine.c00.ft_putchar
slug: string                    # required, filesystem-safe slug
title: string                   # required
summary: string                 # required, 1-3 sentence summary

track: string                   # required, one of: piscine, exam, knr, theory_to_practice, lab, bug_injection, completion, prediction
group: string                   # required, e.g. c00, exam01, chapter_01
source:
  kind: string                  # required, one of: legacy_exam_repo, knr_book, theory_book, authored, generated
  origin_id: string             # optional, legacy id or chapter id
  origin_path: string           # optional, source repo path or book reference
  copyright_status: string      # required, one of: owned, licensed, extracted_for_index_only, unknown

language: string                # required, currently "c"
difficulty:
  level: integer                # required, 1..10
  category: string              # required, one of: beginner, easy, medium, hard, advanced

pedagogy:
  modes:                        # required, non-empty list
    - string                    # each one of: practice, exam, observation, experiment, bug_injection, completion, prediction, review
  concepts:
    - string                    # e.g. loops, pointers, strings
  skills:
    - string                    # e.g. parsing, memory, io
  misconceptions:
    - string                    # optional
  prerequisite_ids:
    - string                    # optional
  followup_ids:
    - string                    # optional
  estimated_minutes: integer    # required, > 0

files:
  statement: string             # required, usually statement.md
  starter_dir: string           # optional
  reference_dir: string         # optional
  tests_dir: string             # required
  fixtures_dir: string          # optional
  hints_dir: string             # optional
  assets_dir: string            # optional

student_contract:
  expected_files:
    - string                    # required, non-empty
  allowed_functions:
    - string                    # may contain "any"
  forbidden_functions:
    - string                    # optional
  required_headers:
    - string                    # optional
  output_contract:
    channel: string             # required, one of: stdout, stderr, files, mixed
    newline_policy: string      # required, one of: exact, flexible, ignore
  norm:
    enabled: boolean            # required
    profile: string             # optional, e.g. 42_norm_v1

build:
  compiler: string              # required, e.g. gcc
  standard: string              # required, e.g. c11
  flags:
    - string                    # required
  link_flags:
    - string                    # optional
  compile_mode: string          # required, one of: single_program, function_with_harness, multi_file
  entry_files:
    - string                    # optional

runtime:
  argv_policy: string           # required, one of: none, fixed, generated, fixture_driven
  stdin_policy: string          # required, one of: none, fixed, generated, fixture_driven
  timeout_seconds: integer      # required, >= 1
  memory_limit_mb: integer      # required, >= 16
  file_write_policy: string     # required, one of: deny, temp_only, declared_outputs_only
  network_access: boolean       # required, must be false for local platform exercises

grading:
  strategy: string              # required, one of: output_diff, structured, file_compare, ast_rule, hybrid
  comparator: string            # required, plugin id
  rubric_id: string             # required
  pass_policy:
    mode: string                # required, one of: all_tests, weighted_threshold, rubric_threshold
    threshold: number           # optional, 0..1
  edge_case_suite_id: string    # optional
  analyzer_ids:
    - string                    # optional, plugin ids

variants:
  default: string               # required, variant id
  available:
    - id: string                # required
      kind: string              # required, one of: normal, buggy, partial, prediction_prompt, observation_only, experiment_seed
      starter_dir: string       # optional
      reference_dir: string     # optional
      tests_dir: string         # optional
      description: string       # optional

tracking:
  productivity_tags:
    - string                    # optional
  habit_tags:
    - string                    # optional
  timeline_tags:
    - string                    # optional

metadata:
  author: string                # optional
  reviewers:
    - string                    # optional
  created_at: string            # required, ISO-8601 UTC
  updated_at: string            # required, ISO-8601 UTC
  status: string                # required, one of: draft, review, active, deprecated
```

## 6. Pool Dataset Contract

Each pool SHALL use this layout.

```text
datasets/pools/<track>/<pool_id>/
  pool.yml
  notes.md
```

### 6.1 `pool.yml` exact schema

```yaml
schema_version: 1

id: string                      # required, global unique id
title: string                   # required
track: string                   # required, one of: piscine, exam, lab, adaptive
mode: string                    # required, one of: practice, exam, review, observation, experiment
description: string             # required

selection:
  strategy: string              # required, one of: ordered, random, weighted_random, adaptive
  seed_policy: string           # required, one of: deterministic_per_session, random_per_session, fixed_seed
  fixed_seed: integer           # required if seed_policy == fixed_seed
  repeat_policy: string         # required, one of: allow, avoid_recent, avoid_passed, never_repeat_within_session
  recent_window: integer        # optional, count of recent exercise ids

timing:
  total_time_seconds: integer   # optional, null for untimed pools
  per_level_time_seconds: integer # optional
  incremental_cooldown: boolean # required
  cooldown_policy:
    kind: string                # required, one of: none, fibonacci, exponential, fixed
    base_seconds: integer       # optional
    multiplier: number          # optional
    max_seconds: integer        # optional

progression:
  start_level: integer          # required, >= 0
  allow_resume: boolean         # required
  on_pass: string               # required, one of: advance_level, pick_next_same_level, complete_pool
  on_fail: string               # required, one of: retry_same_exercise, reshuffle_same_level, assign_remediation
  points_policy:
    kind: string                # required, one of: equal_per_level, explicit_points

docs:
  primary_doc_id: string        # optional
  secondary_doc_ids:
    - string                    # optional

levels:
  - level: integer              # required, unique within pool
    title: string               # required
    points: integer             # required if explicit_points, optional otherwise
    min_picks: integer          # required, >= 1
    max_picks: integer          # required, >= min_picks
    unlock_if:
      all_of:
        - string                # optional, exercise ids or mastery tags
      any_of:
        - string                # optional
    remediation_pool_id: string # optional
    exercise_refs:
      - exercise_id: string     # required
        weight: integer         # optional, default 1
        variant: string         # optional
        conditions:
          modes:
            - string            # optional
          exclude_if_passed: boolean # optional
          include_if_tags:
            - string            # optional
          include_if_concepts:
            - string            # optional

metadata:
  created_at: string            # required, ISO-8601 UTC
  updated_at: string            # required, ISO-8601 UTC
  status: string                # required, one of: draft, review, active, deprecated
```

## 7. Grading Report and Attempt Log Contracts

## 7.1 Grading report schema

One grading report is generated per grading action.

```yaml
schema_version: 1

report_id: string
attempt_id: string
session_id: string
user_id: string

exercise_id: string
variant_id: string
pool_id: string                 # optional
mode: string

started_at: string
finished_at: string
duration_ms: integer

build_result:
  status: string                # one of: success, failure, skipped
  compiler: string
  command: string
  exit_code: integer
  stdout_path: string
  stderr_path: string
  diagnostics:
    errors: integer
    warnings: integer

run_result:
  status: string                # one of: success, failure, timeout, crash, skipped
  command: string
  exit_code: integer
  signal: string                # optional
  timed_out: boolean
  memory_limit_hit: boolean
  stdout_path: string
  stderr_path: string
  trace_path: string            # optional

evaluation:
  comparator_id: string
  passed: boolean
  raw_score: number             # 0..1
  normalized_score: number      # 0..100
  pass_policy: string
  failure_class: string         # one of: none, compile_error, wrong_output, timeout, crash, forbidden_api, style_violation, edge_case_failure, contract_violation
  failed_test_ids:
    - string
  passed_test_ids:
    - string
  edge_case_summary:
    total: integer
    passed: integer
    failed: integer

rubric:
  rubric_id: string
  items:
    - id: string
      score: number
      max_score: number
      verdict: string
      note: string

feedback:
  summary: string
  actionable_next_steps:
    - string
  hint_ids:
    - string
  concept_gaps:
    - string

artifacts:
  workspace_snapshot_path: string
  report_path: string
  diff_path: string             # optional
  exported_trace_path: string   # optional

analytics:
  attempt_number_for_exercise: integer
  cooldown_seconds_applied: integer
  mastery_delta:
    concepts:
      - concept: string
        delta: number
  productivity_tags:
    - string
```

## 7.2 Attempt log schema

Attempt logs are append-only JSONL records persisted under `storage/attempts/`.

```yaml
schema_version: 1

attempt_id: string
session_id: string
user_id: string
exercise_id: string
variant_id: string
mode: string
pool_id: string                 # optional

attempt_index_for_session: integer
attempt_index_for_exercise: integer

created_at: string
submitted_at: string            # optional
graded_at: string               # optional

state: string                   # one of: opened, edited, submitted, graded, abandoned, expired

workspace:
  root_path: string
  submitted_files:
    - string
  file_hashes:
    - path: string
      sha256: string

timing:
  active_seconds: integer
  idle_seconds: integer
  focus_blocks:
    - started_at: string
      ended_at: string
      active_seconds: integer

result:
  report_id: string             # optional
  passed: boolean               # optional
  normalized_score: number      # optional
  failure_class: string         # optional

notes:
  learner_note: string          # optional
  observer_note: string         # optional
```

## 8. Session Lifecycle

The canonical lifecycle is:

1. `session.created`
2. `session.started`
3. `exercise.assigned`
4. `workspace.prepared`
5. `attempt.opened`
6. `attempt.edited`
7. `attempt.submitted`
8. `grading.started`
9. `build.finished`
10. `run.finished`
11. `evaluation.finished`
12. `grading.finished`
13. `analytics.updated`
14. `timeline.updated`
15. `session.level_advanced` or `session.exercise_reassigned`
16. `session.completed` or `session.stopped`

### 8.1 Lifecycle contract

- A session is the container for one mode execution, such as a piscine study block or exam simulation.
- A session may contain multiple attempts.
- Exactly one exercise assignment is active at a time per session.
- A grading report is immutable after `grading.finished`.
- Analytics are derived from attempts and reports and must be reproducible.
- Timeline events are append-only.

### 8.2 Session states

Allowed session states:

- `created`
- `ready`
- `running`
- `waiting_for_submission`
- `grading`
- `cooldown`
- `paused`
- `completed`
- `abandoned`
- `expired`

## 9. Grading Engine Plugin Interface

The grading engine SHALL be plugin-based. Plugins are loaded by manifest and invoked by contract.

### 9.1 Plugin categories

- `language`: compile and run rules for a language
- `comparator`: output or file comparison
- `analyzer`: post-grade classification and diagnostics
- `rubric`: rubric scoring
- `generator`: dynamic test or fixture generation
- `reporter`: report formatting and export

### 9.2 Plugin manifest contract

```yaml
plugin_id: string
category: string                # one of: language, comparator, analyzer, rubric, generator, reporter
version: string
name: string
entrypoint: string              # runtime-resolvable plugin entry
capabilities:
  - string
supported_languages:
  - string
config_schema_ref: string       # path to plugin config schema
```

### 9.3 Runtime hook contract

Each plugin SHALL implement some subset of the following hooks.

- `validate(config, exercise_manifest) -> validation_result`
- `prepare(context) -> prepared_context`
- `compile(context) -> build_result`
- `generate_tests(context) -> test_bundle`
- `run(context, test_case) -> run_result`
- `compare(context, expected, actual) -> comparison_result`
- `analyze(context, results) -> analysis_result`
- `score(context, results) -> rubric_result`
- `report(context, report) -> exported_artifacts`

### 9.4 Engine request contract

The engine provides plugins:

- immutable exercise manifest
- immutable pool manifest when relevant
- workspace paths
- sandbox profile
- resolved variant
- test bundle
- session metadata

Plugins must not mutate canonical datasets.

## 10. Sandbox Model for C Compilation and Execution

The platform SHALL compile and run C code in a constrained local sandbox.

### 10.1 Compile sandbox

- Working directory: per-attempt isolated workspace under `runtime/workspaces/<attempt_id>/`.
- Writable paths: workspace only.
- Read-only mounts: dataset assets, toolchain binaries, shared fixtures.
- Network: disabled.
- Process limit: configurable, default `32`.
- CPU time limit: configurable, default `10s` for compile.
- Memory limit: configurable, default `512MB` for compile.
- Allowed binaries: compiler toolchain, shell wrapper, declared utilities only.

### 10.2 Runtime sandbox

- Working directory: same isolated workspace.
- Network: disabled.
- Max wall time: from `exercise.yml.runtime.timeout_seconds`.
- Memory limit: from `exercise.yml.runtime.memory_limit_mb`.
- Max output bytes: configurable, default `1MB` stdout and `1MB` stderr.
- File writes: denied unless `temp_only` or `declared_outputs_only`.
- Child processes: allowed only if the exercise explicitly permits them.
- No access to host home directory, git config, SSH keys, or environment secrets.

### 10.3 C toolchain contract

- Supported compilers: `gcc`, `clang`.
- Supported standards initially: `c89`, `c99`, `c11`.
- Default flags for strict mode:
  - `-Wall`
  - `-Wextra`
  - `-Werror`
- Optional diagnostics layers:
  - address sanitizer
  - undefined behavior sanitizer
  - leak detection
- The grader may run multiple profiles:
  - strict compile
  - normal execution
  - sanitizer execution
  - edge-case execution

## 11. Timeline and Productivity Event Model

The platform SHALL use append-only events for both learning history and productivity tracking.

### 11.1 Timeline event schema

```yaml
schema_version: 1

event_id: string
user_id: string
session_id: string
attempt_id: string             # optional
exercise_id: string            # optional
pool_id: string                # optional

event_type: string             # required
occurred_at: string            # ISO-8601 UTC

mode: string                   # optional
track: string                  # optional
source: string                 # one of: session, grading, analytics, dashboard, user

payload:
  summary: string
  tags:
    - string
  metrics:
    active_seconds: integer    # optional
    idle_seconds: integer      # optional
    score: number              # optional
    streak: integer            # optional
    mastery_delta: number      # optional
```

### 11.2 Required event types

- `session.created`
- `session.started`
- `session.paused`
- `session.resumed`
- `session.completed`
- `session.abandoned`
- `exercise.assigned`
- `attempt.opened`
- `attempt.submitted`
- `grading.started`
- `grading.finished`
- `exercise.passed`
- `exercise.failed`
- `level.advanced`
- `cooldown.applied`
- `habit.streak_updated`
- `productivity.focus_block_closed`
- `productivity.daily_goal_completed`
- `review.scheduled`

### 11.3 Productivity aggregates

The analytics layer SHALL derive:

- daily active minutes
- focus blocks completed
- exercises attempted
- exercises passed
- pass rate by concept
- first-pass success rate
- retry depth
- edge-case failure rate
- bug-fix success rate
- prediction accuracy
- completion accuracy
- streak count
- weekly habit compliance

## 12. Local Intra Dashboard Contract

The dashboard is a local UI over storage and analytics. It SHALL display:

- current session state
- active exercise statement and timer
- current pool and level
- attempt history
- grading reports
- concept mastery heatmap
- productivity and habit widgets
- timeline feed
- remediation suggestions

The dashboard MUST NOT depend on remote services.

## 13. Dataset Migration Plan

## 13.1 Source systems

Legacy sources:

- `ExamPoolRevanced-main`
- `Exam00`
- `Exam01`
- `Exam02`
- `ExamFinal`
- `grademe-main`
- `grademe-mainn`

Observed facts from the current repository:

- `Exam00`, `Exam01`, `Exam02`, and `ExamFinal` are duplicates of the corresponding subfolders in `ExamPoolRevanced-main`.
- `grademe-main` and `grademe-mainn` are duplicates.
- Legacy content mixes production data, validation scripts, report files, and runtime scripts.

## 13.2 Migration principles

- `ExamPoolRevanced-main` becomes the canonical content source.
- Root `Exam00/01/02/Final` are discarded as duplicate content after audit.
- `grademe-main` is treated as runtime reference behavior, not source-of-truth dataset input.
- Migration preserves all source file hashes and creates an audit trail.

## 13.3 Migration phases

### Phase A: inventory

- index all legacy subjects, corrections, pools, docs, and tools
- compute stable hashes
- detect duplicates and mismatches
- produce import audit report

### Phase B: normalize exercises

For each legacy assignment:

- create one normalized exercise directory
- convert `subject.en.txt` into `statement.md`
- map `profile.yml`, `generator.py`, `main.c`, and reference source into normalized `reference/` and `tests/`
- capture legacy defects in migration metadata

### Phase C: normalize pools

- convert each legacy pool YAML into canonical `pool.yml`
- preserve level ordering and assignment membership
- map legacy flags such as trace and cooldown into canonical timing and progression fields

### Phase D: extract runtime behavior from grademe

From `grademe-main`:

- extract cooldown model
- extract session persistence model
- extract level advancement semantics
- extract trace artifact semantics
- extract packaged `tester.sh` patterns for reference analyzers

This behavior informs engine defaults but is not imported as content.

### Phase E: quality repair

During migration, tag issues but do not silently fix them.

Examples:

- subject and folder name mismatches
- missing `main.c`
- typoed generator names
- incomplete examples
- missing correction folders

Repairs are applied in normalized datasets with explicit migration notes.

## 13.4 Legacy mapping rules

### `ExamPoolRevanced-main`

- `subjects/<name>/subject.en.txt` -> `statement.md`
- `corrections/<name>/profile.yml` -> `exercise.yml.grading` and `reference/profile_legacy.yml`
- `corrections/<name>/generator.py` -> `tests/generators/legacy_generator.py`
- `corrections/<name>/main.c` -> `reference/harness/main.c`
- `pools/*.yml` -> `datasets/pools/exams/.../pool.yml`
- `docs/...` -> referenced pool docs
- `results.txt` and `report.yml` -> migration audit inputs only

### `Exam00/01/02/Final`

- used only for dedupe verification against `ExamPoolRevanced-main`
- no separate import path unless differences are later introduced

### `grademe-main`

- `.subjects/...` -> reference for packaged runtime layout and legacy assignment names
- `.system/grade_request.cpp`, `.system/exam.cpp`, `.system/exercise.cpp`, `.system/utils.cpp`, `.system/data_persistence.cpp` -> behavioral reference for session, cooldown, and progression contracts
- packaged `tester.sh` files -> examples for language/comparator plugins and migration fixtures

## 14. Book Example Import Strategy

## 14.1 Source books

- K&R
- C From Theory to Practice

## 14.2 Import goals

- preserve chapter and concept structure
- avoid treating book text as executable content directly
- convert examples into learning assets and derived exercises
- keep copyright-sensitive text separate from normalized exercise statements

## 14.3 Book asset model

Each imported book example SHALL produce:

- one `book_asset.yml`
- one extracted snippet under `assets/snippets/`
- one or more derived normalized exercises

### `book_asset.yml` schema

```yaml
schema_version: 1
book_id: string
chapter_id: string
section_id: string
example_id: string
title: string
concepts:
  - string
source_pages:
  - integer
snippet_path: string
derivative_exercise_ids:
  - string
copyright_status: string
notes: string
```

## 14.4 K&R import strategy

- extract chapter and section index
- identify code examples and short exercises
- classify each example by concept and difficulty
- create derivatives:
  - observation lab
  - completion exercise
  - bug injection variant
  - prediction prompt
  - timed practice variant

## 14.5 Theory to Practice import strategy

- extract examples, guided tasks, and end-of-section exercises
- preserve theory-to-practice sequence:
  - concept brief
  - worked example
  - guided lab
  - independent exercise
  - edge-case extension

## 14.6 Copyright-aware storage rule

- Store bibliographic metadata and minimal excerpts needed for indexing.
- Store user-owned or generated derivative exercises as normalized platform content.
- Store raw extracted pages under `datasets/books/.../assets/` for local indexing only when legally permitted.
- Keep derived exercise statements original to the platform, not copied verbatim from the books.

## 15. Validation Rules

The tooling layer MUST validate:

- manifest schema correctness
- global id uniqueness
- relative path resolution
- referenced exercise existence inside pools
- referenced variant existence
- rubric existence
- forbidden missing files for active exercises
- migration provenance for imported legacy content

Validation failures block activation of datasets.

## 16. Non-Goals

- No remote grading service in v1.
- No cloud dependency for the dashboard.
- No hidden mutable logic inside dataset folders.
- No per-exercise bespoke shell scripts as the primary grading model.

## 17. Implementation Readiness

This document is sufficient to begin:

- schema definitions in `datasets/schemas/`
- storage layout and event persistence
- grading engine plugin loading
- CLI session orchestration
- dashboard data model
- legacy migration tooling

Implementation should start with schemas, validation, storage primitives, and the C language grading plugin.
