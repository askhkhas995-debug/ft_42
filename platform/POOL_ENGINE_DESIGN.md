# Pool Engine Design

## Scope

This document defines the canonical dataset-driven pool engine for the current platform state.

It covers:

- the strict canonical `pool.yml` schema
- level-based pools and unlock rules
- selection strategies and repeat policies
- timing metadata
- catalog-backed exercise resolution
- the service contract for loading pools, resolving candidates, and selecting the next exercise

It does not cover:

- UI
- dashboard or productivity features
- session authoring workflows
- timing enforcement or cooldown enforcement at runtime

## Canonical Pool Bundle

Pools are canonical dataset bundles under `datasets/pools/<track>/<slug>/`.

```text
datasets/pools/<track>/<slug>/
  pool.yml
```

Examples:

- `datasets/pools/piscine/c00-foundations/pool.yml`
- `datasets/pools/exams/exam00-starter/pool.yml`

Pool bundles are catalog assets. They are discovered, validated, and loaded through `CatalogService`.
Pool entries reference canonical `exercise_id` values plus optional `variant` ids. They never reference file paths.

## Canonical `pool.yml` Schema

Top-level required keys:

- `schema_version`
- `id`
- `title`
- `track`
- `mode`
- `description`
- `selection`
- `timing`
- `levels`
- `metadata`

Top-level optional keys:

- none

Supported scalar semantics:

- `schema_version`: must be `1`
- `id`: globally unique pool id
- `track`: must match the directory track segment and a supported catalog track
- `mode`: canonical pool mode, currently `practice` or `exam`

### Selection Block

Required keys:

- `strategy`
- `repeat_policy`

Optional keys:

- `recent_window`
- `seed_policy`

Supported values:

- `strategy`: `random`, `weighted`, `ordered`
- `repeat_policy`: `avoid_passed`, `avoid_recent`, `allow_review`
- `seed_policy`: `deterministic_per_session`, `system_random`

Rules:

- `avoid_recent` requires `recent_window`
- `recent_window` must be `>= 0`
- `ordered` uses ascending `order`, then declaration order
- `weighted` defaults missing weights to `1`

### Timing Block

Required keys:

- `total_time_seconds`
- `per_level_time_seconds`
- `cooldown`

Required cooldown keys:

- `enabled`
- `seconds`
- `scope`

Rules:

- `total_time_seconds` must be `> 0`
- `per_level_time_seconds` must be `> 0`
- `cooldown.seconds` must be `>= 0`
- `cooldown.scope` must be `pool` or `level`

Timing is metadata emitted by the pool engine. It is not enforced in this phase.

### Levels Block

`levels` is a non-empty list of level objects sorted logically by `level`.

Each level requires:

- `level`
- `title`
- `min_picks`
- `unlock_if`
- `exercise_refs`

Each level may include:

- `max_picks`
- `time_limit_seconds`

Rules:

- `level` must be unique
- `min_picks` must be `> 0`
- `max_picks`, when present, must be `> 0` and `>= min_picks`
- `time_limit_seconds`, when present, must be `> 0`
- `time_limit_seconds` overrides `timing.per_level_time_seconds` for that level

### Unlock Rules

Each level requires `unlock_if` with:

- `all_of`
- `any_of`

Rules:

- unlock references must point to defined lower levels
- a level is unlocked when all `all_of` levels are completed and either `any_of` is empty or one `any_of` level is completed
- level completion is based on passed candidate entries, not file paths

### Exercise References

Each level contains a non-empty `exercise_refs` list.

Each exercise ref requires:

- `exercise_id`

Each exercise ref may include:

- `variant`
- `weight`
- `order`

Rules:

- `exercise_id` must resolve through the catalog
- `variant`, when present, must resolve on the target exercise
- `(exercise_id, variant)` pairs must be unique within a level
- `weight` must be `> 0`
- `ordered` strategy requires `order` on every ref
- when `order` is present it must be an integer `> 0`
- declaration order is preserved for ordered ties

## Selection Strategies

Selection is always level-based.

- `random`: choose uniformly from eligible candidates in the active level
- `weighted`: choose probabilistically using candidate weights in the active level
- `ordered`: choose the eligible candidate with the lowest `order`, then the earliest declaration index

The active level is the lowest unlocked level that still has eligible candidates after repeat policy filtering.

## Repeat Policies

Repeat policy is evaluated against catalog candidate entries, using `(exercise_id, variant_id)` identity.

- `avoid_passed`: exclude candidate entries already passed in session history
- `avoid_recent`: exclude candidate entries present in the recent session window
- `allow_review`: keep previously seen candidate entries eligible

`max_picks` is evaluated before candidate selection. Once a level has consumed its allowed picks, that level has no further candidates for the session.

## Catalog Integration

The catalog owns:

- pool discovery
- schema validation
- unknown-key rejection
- exercise-id and variant resolution
- duplicate pool id rejection

The pool engine does not crawl files directly. It only consumes validated `PoolDataset` instances from `CatalogService`.

## Service Contract

The pool engine service provides:

- `load_pool(pool_id)`
  returns a validated `PoolDataset`
- `resolve_candidates(pool_id, session_history, level=None, session_id=None)`
  returns eligible `CandidateExercise` entries for an explicit level or the active level
- `select_next(pool_id, session_id, session_history=None)`
  returns the next assignment plus timing and policy metadata

Session history is append-only input state derived from stored attempts and reports. It carries:

- attempt id
- exercise id
- variant id
- pool id
- created-at timestamp
- pass/fail state

## Selection Result

The selection result is deterministic for a given pool, session id, history length, and deterministic seed policy.

Returned fields include:

- `pool_id`
- `session_id`
- `track`
- `exercise_id`
- `variant_id`
- `level`
- `selection_strategy`
- `repeat_policy`
- `candidate_count`
- `timing`

The `timing` payload includes:

- `total_time_seconds`
- `per_level_time_seconds`
- `effective_level_time_seconds`
- `cooldown`

## Strict Validation

Validation is fail-fast and rejects unknown keys in every validated mapping.

Strict validation covers:

- root-level keys
- `selection`
- `timing`
- `timing.cooldown`
- each level
- each `unlock_if`
- each `exercise_ref`
- `metadata`

Representative failures:

- wrong track for directory
- unsupported `mode`
- unsupported strategy or repeat policy
- unknown keys anywhere in the schema
- unresolved `exercise_id`
- unresolved variant
- duplicate pool id
- duplicate level number
- duplicate `(exercise_id, variant)` pair within a level
- non-unique ordered ranks inside a level

## Verification

This phase is verified with canonical sample pools for:

- `piscine`
- `exams`

Both sample pools are loaded by the catalog and exercised through the pool engine service.
