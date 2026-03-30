# Catalog Design

## Scope

This document defines the dataset-driven exercise layer that sits underneath grading.

It covers:

- the canonical on-disk exercise bundle format
- strict schema validation rules
- bundle loaders for manifest, statement, tests, starter, and reference assets
- the catalog index used by the grading engine

Out of scope for this phase:

- dashboard features
- productivity features
- adaptive sequencing
- pool orchestration beyond loading exercise metadata

## Supported Tracks

The catalog recognizes these canonical exercise tracks:

- `piscine`
- `exams`
- `knr`
- `theory_to_practice`
- `bug_injection`
- `completion`
- `prediction`

Exercises live under `datasets/exercises/<track>/...`.

## Canonical Exercise Bundle

Each exercise is a directory bundle.

Canonical layout:

```text
datasets/exercises/<track>/<group>/<slug>/
  exercise.yml
  statement.md
  tests/
    tests.yml
    main.c
  starter/
    <expected student files>
  reference/
    <expected student files>
  fixtures/      # optional
  hints/         # optional
  assets/        # optional
```

Track-specific grouping is flexible after the `<track>` segment:

- `piscine/c00/ft_putchar`
- `exams/exam00/aff_a`
- `knr/ch01/hello_world_observation`
- `theory_to_practice/ch02/variables_guided`
- `bug_injection/c03/ft_strcmp_bugfix`
- `completion/c01/ft_swap_completion`
- `prediction/c00/ft_putchar_prediction`

The manifest remains the canonical source of metadata and policy, but all operational files are loaded as a single `ExerciseDataset` bundle.

## Loader Contract

The catalog loads exactly these assets for each exercise:

- `exercise.yml`: structured manifest
- `statement.md`: learner-facing statement text
- `tests/tests.yml`: declarative test cases
- `tests/main.c`: harness for `function_with_harness` exercises
- `starter/`: starter file bundle
- `reference/`: reference implementation bundle

The loader returns an immutable bundle with:

- resolved paths
- parsed manifest
- parsed test cases
- statement markdown
- starter/reference file inventories
- summary metadata used for indexing

## Validation Rules

Validation is strict and fail-fast.

General rules:

- unknown keys are rejected for manifest sections covered by the schema
- required keys must exist
- required values must have the expected type
- enum-like fields are validated against explicit allowed values
- relative file and directory paths must stay inside the exercise bundle
- duplicate exercise ids are rejected
- duplicate testcase ids are rejected

Bundle rules:

- `track` in `exercise.yml` must match the directory track segment
- `statement.md` must exist and be non-empty
- `tests/tests.yml` must exist and contain at least one case
- `tests/main.c` must exist when `build.compile_mode == function_with_harness`
- `starter/` and `reference/` must exist
- every file listed in `student_contract.expected_files` must exist in both `starter/` and `reference/`
- `build.entry_files` must be a subset of `student_contract.expected_files`
- `variants.default` must point at one of `variants.available[*].id`

## Catalog Responsibilities

`CatalogService` owns:

- discovering all `exercise.yml` files under supported tracks
- validating each bundle
- building an in-memory index of exercises by id
- exposing list and lookup APIs
- returning fully-loaded `ExerciseDataset` objects to callers

The grading engine must not open dataset files directly.
It consumes only `ExerciseDataset` objects from the catalog.

## Grading Integration

The grading engine receives:

- manifest config from the dataset bundle
- testcase definitions from the dataset bundle
- harness path from the dataset bundle
- reference and starter directories from the dataset bundle

This keeps the runtime ignorant of repository layout details and makes the dataset layer the single integration boundary for exercises.

## Schema Files

Human-readable schema summaries live in `datasets/schemas/`.

This phase defines:

- `exercise.schema.yml`
- `tests.schema.yml`

The executable source of truth is the catalog validator implementation.
