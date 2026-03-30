# Exam Mode Design

## Scope

This document defines the exam session engine for canonical exam pools.

It covers:

- starting an exam session from a canonical exam pool
- selecting exercises through the pool engine
- grading submissions through the grading engine
- advancing levels on success
- persisting failures and retry state
- persisting cooldown metadata
- persisting session state, attempt logs, and reports

It does not cover:

- dashboard or UI work
- productivity analytics
- strict runtime enforcement of cooldown waits or total exam time

## Core Flow

The exam engine composes three existing platform services:

- `CatalogService` for validated canonical exam pools and exercises
- `PoolEngineService` for candidate resolution and next-exercise selection
- `GradingEngine` for immutable grading reports

Lifecycle:

1. Start a session from a canonical exam pool.
2. Select the first exercise through the pool engine.
3. Persist a session file under `storage/sessions/`.
4. On submission, append an attempt log entry under `storage/attempts/`.
5. Grade the submission with the grading engine.
6. Persist or augment the grading report under `runtime/reports/`.
7. Update session state:
   - success: advance to next unlocked level or finish
   - failure: keep the current exercise active and increment retry state

## Session Contract

Exam sessions are file-backed YAML documents under:

```text
storage/sessions/<session_id>.yml
```

Required session fields:

- `schema_version`
- `session_id`
- `user_id`
- `mode`
- `state`
- `started_at`
- `pool_id`
- `track`
- `selection_strategy`
- `repeat_policy`
- `timing`
- `progress`
- `current_assignment`
- `analytics_policy`

Session states:

- `active`
- `finished`

## Current Assignment

`current_assignment` captures the active exam target:

- `exercise_id`
- `variant_id`
- `level`
- `assigned_at`
- `attempt_count`
- `failure_count`
- `last_attempt_id`
- `last_report_id`

Behavior:

- on failure, `current_assignment` stays on the same exercise
- on success, `current_assignment` is replaced by the next selected exercise
- if no next exercise is available, the session is finished

## Progress State

`progress` tracks session-level exam state:

- `attempts_total`
- `passed_exercise_ids`
- `failed_attempts_total`
- `current_level`
- `highest_unlocked_level`
- `completed_levels`
- `finished_at`

Level advancement is derived from pool-engine history after each graded attempt.

## Attempt Persistence

Each submission produces an append-only JSONL log:

```text
storage/attempts/<attempt_id>.jsonl
```

Two records are written per attempt:

- `opened`
- `graded`

Stored attempt information includes:

- session identity
- pool identity
- exercise identity
- attempt indexes
- workspace metadata
- grading outcome summary

## Grading Integration

The exam engine constructs an `AttemptContext` and calls `GradingEngine.grade_submission(...)`.

The grading report remains the canonical immutable execution result.
The exam engine may augment metadata after grading, such as:

- cooldown seconds applied
- session-linked report path

## Retry Semantics

Retry policy for exam mode:

- a failed submission does not advance the pool
- the same assignment remains active
- `attempt_index_for_exercise` increments for each retry
- retry metadata is stored in session state

This gives deterministic retry behavior independent of pool repeat policy.

## Cooldown Metadata

Cooldown is persisted as metadata, not enforced as a hard wait in this phase.

Session cooldown state stores:

- `enabled`
- `scope`
- `seconds`
- `last_applied_at`
- `available_at`

Cooldown metadata is updated after each graded submission and copied into the session and report payloads.

## Finish Conditions

A session is finished when either:

- the pool engine has no remaining eligible exercises after a successful submission
- the caller explicitly finishes the session

Finish state stores:

- `state: finished`
- `finished_at`
- `current_assignment: null`

## Service API

The exam session engine exposes:

- `start_session(pool_id, user_id="local.user")`
- `load_session(session_id)`
- `submit_submission(session_id, submission_root)`
- `finish_session(session_id)`

`start_session(...)`:

- validates that the pool is a canonical exam pool
- selects the initial assignment
- persists the session file

`submit_submission(...)`:

- appends an attempt-opened record
- grades the submission
- appends an attempt-graded record
- updates the grading report metadata
- updates session progress, retry state, cooldown metadata, and finish state

## Testing

Required tests:

- start
- submit
- next level
- retry after failure
- finish session

Tests should use validated canonical exam datasets and pool fixtures, while stubbing grading results when the lifecycle behavior itself is under test.
