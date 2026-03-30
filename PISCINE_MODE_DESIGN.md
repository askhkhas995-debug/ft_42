# Piscine Mode Design

## Scope

This document defines piscine mode on top of the current platform foundation.

It covers:

- `shell00`
- `shell01`
- `C00` through `C13`
- canonical exercise bundles and canonical piscine pools
- progression, completion, unlocks, and resume/load state
- grading through the existing grading engine
- beginner-friendly metadata hooks for visible edge cases, optional hints, and optional observation-mode support

It does not cover:

- UI
- productivity analytics
- non-canonical dataset migration

## Design Goal

Piscine mode should feel like a guided long-form curriculum, not an exam.

The architecture should reuse the same core building blocks already present for exam mode:

- `CatalogService` for canonical exercise and pool loading
- `PoolEngineService` for unlock-aware next-exercise selection
- `GradingEngine` for immutable evaluation reports
- `StorageService` for persisted session state and append-only attempt history

The new work is primarily a mode-specific session service and a richer piscine metadata contract.

## Dataset Model

Piscine mode uses the existing canonical exercise dataset model unchanged as the base contract.

Each piscine exercise remains a standard canonical bundle under:

```text
platform/datasets/exercises/piscine/<group>/<slug>/
```

Each curriculum segment is represented as a canonical pool under:

```text
platform/datasets/pools/piscine/<pool-slug>/pool.yml
```

Track remains:

- `track: piscine`

Groups expand to:

- `shell00`
- `shell01`
- `c00`
- `c01`
- `c02`
- `c03`
- `c04`
- `c05`
- `c06`
- `c07`
- `c08`
- `c09`
- `c10`
- `c11`
- `c12`
- `c13`

## Curriculum Layout

Piscine progression should be chapter-oriented.

Recommended canonical pools:

- `piscine.shell00.foundations`
- `piscine.shell01.foundations`
- `piscine.c00.foundations`
- `piscine.c01.core`
- `piscine.c02.core`
- `piscine.c03.core`
- `piscine.c04.core`
- `piscine.c05.core`
- `piscine.c06.core`
- `piscine.c07.core`
- `piscine.c08.core`
- `piscine.c09.core`
- `piscine.c10.core`
- `piscine.c11.core`
- `piscine.c12.core`
- `piscine.c13.core`

Optionally, a higher-level curriculum manifest may later sequence these pools, but v1 piscine mode can begin with independent canonical pools plus persistent learner state.

## Core Flow

Piscine mode composes the same base services as exam mode, but with different progression semantics:

1. Start or load a piscine session for a canonical piscine pool.
2. Resolve the next unlocked exercise through the pool engine.
3. Persist file-backed session state under `storage/sessions/`.
4. On submission, append an attempt record under `storage/attempts/`.
5. Grade the submission through `GradingEngine.grade_submission(...)`.
6. Persist the grading report under `runtime/reports/`.
7. Update piscine progress:
   - success: mark exercise completed, unlock dependent levels, select the next eligible exercise
   - failure: retain the same exercise or leave the pool engine to reselect it depending on repeat policy
8. Allow the learner to resume from persisted state at any time.

## Session Service

Add a new service:

```text
platform/core/sessions/src/platform_sessions/piscine.py
```

Primary API:

- `start_session(pool_id, user_id="local.user")`
- `load_session(session_id)`
- `load_or_start(pool_id, user_id="local.user")`
- `submit_submission(session_id, submission_root)`
- `select_next(session_id)`
- `finish_session(session_id)`

The implementation should mirror the exam session service where practical, but piscine mode differs in two ways:

1. completion is exercise-centric rather than exam-attempt-centric
2. resume/load is a first-class behavior, not just a convenience

## Session Contract

Piscine sessions are file-backed YAML documents under:

```text
storage/sessions/<session_id>.yml
```

Required fields:

- `schema_version`
- `session_id`
- `user_id`
- `mode`
- `state`
- `started_at`
- `updated_at`
- `finished_at`
- `pool_id`
- `track`
- `selection_strategy`
- `repeat_policy`
- `progress`
- `current_assignment`
- `resume_policy`
- `analytics_policy`

Session states:

- `active`
- `completed`
- `finished`

`completed` means all eligible exercises in the pool are done.

`finished` means explicitly closed by the caller after completion or abandonment.

## Progress State

Piscine progress should persist richer learner state than exam mode.

Required `progress` fields:

- `attempts_total`
- `completed_exercise_ids`
- `passed_exercise_ids`
- `failed_attempts_total`
- `current_level`
- `highest_unlocked_level`
- `completed_levels`
- `available_exercise_ids`
- `last_completed_exercise_id`
- `completion_ratio`
- `finished_at`

This keeps progression inspectable and makes resume deterministic.

## Current Assignment

`current_assignment` keeps the learner’s active target:

- `exercise_id`
- `variant_id`
- `level`
- `assigned_at`
- `attempt_count`
- `failure_count`
- `last_attempt_id`
- `last_report_id`
- `status`

`status` values:

- `active`
- `completed`
- `retrying`

## Resume / Load Behavior

Piscine mode must support resume/load state by default.

Rules:

1. `load_session(session_id)` returns the persisted state without mutation.
2. `load_or_start(pool_id, user_id)` should return an active existing piscine session for that `(user_id, pool_id)` pair when one exists.
3. If a session has an unfinished `current_assignment`, resume that assignment first.
4. If the current assignment is missing or already completed, resolve the next eligible unlocked exercise.
5. If no eligible exercises remain, transition the session to `completed`.

## Progression and Unlocks

Unlock logic should continue to live in the existing pool engine.

Piscine mode relies on:

- canonical level unlock rules in pool manifests
- `PoolEngineService.resolve_candidates(...)`
- `PoolEngineService.select_next(...)`

Behavior:

- passing an exercise marks it completed for the session
- completed exercises are excluded by default through `repeat_policy: avoid_passed`
- level unlocks are recomputed from persisted session history
- the next exercise is selected from the currently unlocked candidate set

## Completion Semantics

A piscine pool is completed when no eligible unlocked exercises remain.

On completion:

- `state` becomes `completed`
- `current_assignment` becomes `null`
- `progress.finished_at` is set
- the session remains loadable and inspectable

This is distinct from exam mode, where a session ends because an exam run is over.

## Grading Integration

Piscine mode must use the existing grading engine directly.

Submission handling should construct an `AttemptContext` with:

- `mode="piscine"`
- the canonical `exercise_id`
- the canonical `variant_id`
- the owning `pool_id`
- `attempt_index_for_exercise`

The grading report remains the immutable source of truth for evaluation.

Piscine session state may reference:

- `report_id`
- `report_path`
- normalized pass/fail outcome

but should not duplicate the full grading payload.

## Beginner-Friendly Metadata Hooks

The canonical exercise model already has extensible sections such as `pedagogy`, `files`, `variants`, and `tracking`.

Piscine mode should add optional metadata hooks without breaking the existing canonical model.

Recommended optional section:

```yaml
learning:
  visible_edge_cases:
    - id: empty_input
      prompt: "What should happen for an empty string?"
      reveal_before_submit: true
  hints:
    - id: write_signature
      prompt: "Remember the expected function signature."
      unlock_after_attempts: 2
  observation:
    enabled: true
    prompts:
      - "Trace the control flow before compiling."
    capture:
      show_expected_files: true
      show_test_ids: true
```

Hooks:

- `visible_edge_cases`
  - optional learner-visible cases surfaced before or after attempts
- `hints`
  - optional hints unlocked by attempt count or explicit request
- `observation`
  - optional observation-mode hooks for future tooling

These are metadata hooks only in this phase. No UI or observation execution layer is required yet.

## Selection Policy

Piscine pools should default to:

- `selection.strategy: ordered`
- `repeat_policy: avoid_passed`
- deterministic progression per session

This keeps early-learning flow predictable.

Where a chapter has multiple equivalent exercises at one level, ordered or weighted selection can still be used, but the default should remain simple and beginner-friendly.

## Persistence

Reuse the existing persistence layout:

- sessions: `storage/sessions/`
- attempts: `storage/attempts/`
- grading reports: `runtime/reports/`

Each piscine submission should append:

- an `opened` attempt record
- a `graded` attempt record

This matches exam mode and avoids a new persistence model.

## Suggested Implementation Shape

Add:

- `platform/core/sessions/src/platform_sessions/piscine.py`
- `platform/core/sessions/src/platform_sessions/__init__.py`
- `platform/tests/test_piscine_session_engine.py`

If reuse is high, shared helpers may be extracted from exam mode into a common session utility module, but only if the extraction stays mechanical and low-risk.

## Sample Pool Contract

Example piscine pool shape remains canonical:

- ordered levels
- explicit unlock rules
- one or more exercise refs per level
- `mode: practice`

Nothing piscine-specific is required in the pool schema beyond current canonical fields.

## Testing

Required tests:

- progression
  - a passed exercise unlocks the next eligible exercise
- completion
  - the session transitions to `completed` when no eligible exercises remain
- resume/load state
  - an unfinished session reloads with the same current assignment and progress
- next exercise selection
  - `select_next(...)` returns the correct unlocked exercise according to pool order and repeat policy

Recommended additional tests:

- failed submission retains retry state
- completed exercises are not reselected under `avoid_passed`
- `load_or_start(...)` reuses an existing active session for the same pool and user
- optional `learning` metadata survives catalog loading without affecting grading behavior

## Rollout Order

1. Add canonical pools for `shell00`, `shell01`, and `C00` to `C13`.
2. Add the piscine session service on top of catalog, pool engine, grading, and storage.
3. Add beginner-friendly optional metadata hooks to authored piscine bundles.
4. Add persistence and resume/load tests.
5. Add progression and completion tests.

This keeps piscine mode aligned with the existing platform core and avoids introducing a second architecture beside the exam/session foundation.
