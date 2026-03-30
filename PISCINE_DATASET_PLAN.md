# Piscine Dataset Plan

## Goal

Populate canonical piscine datasets for:

- `shell00`
- `shell01`
- `c00` through `c13`

The engine should stay unchanged as much as possible. The work should reuse:

- `CatalogService`
- catalog validation
- `PoolEngineService`
- `PiscineSessionService`
- the existing grading engine

This phase is content population and validation only.

## Current Baseline

Piscine mode is implemented and tested, but the canonical dataset layer is still mostly empty.

Current checked-in canonical piscine content:

- `piscine.c00.foundations`
- `piscine.c00.ft_putchar`
- `piscine.c00.ft_putstr`

Everything else still needs canonical bundle population.

## Source Priority

Use legacy sources in this order:

1. grademe-packaged `.subjects` content when available
2. existing repository exercise content when it can be normalized safely
3. Subjects PDFs only for curriculum metadata, titles, grouping, ordering, and prerequisite hints

Rules:

- PDFs are not runtime bundle inputs
- runtime bundles must come from concrete file content, not from PDF reconstruction
- imported source provenance must be recorded per exercise

## Canonical Target Model

Each imported exercise must become a canonical bundle under:

```text
platform/datasets/exercises/piscine/<group>/<slug>/
```

Each curriculum segment must become a canonical pool under:

```text
platform/datasets/pools/piscine/<pool-slug>/pool.yml
```

Each canonical exercise bundle should use the existing dataset contract:

- `exercise.yml`
- `statement.md`
- `starter/`
- `reference/`
- `tests/tests.yml`
- `tests/main.c` when required by compile mode
- optional `fixtures/`, `hints/`, `assets/`

No new engine-level bundle shape should be introduced for piscine.

## Migration Workflow

Add a staged piscine import workflow parallel to the existing legacy import tooling.

Suggested tooling:

- `platform/tooling/import_legacy/piscine_import.py`
- `platform/tooling/import_legacy/piscine_curation.py`
- `platform/tooling/import_legacy/piscine_status.py`

Suggested entrypoints:

- `discover_piscine_sources(...)`
- `import_piscine_exercises(...)`
- `build_piscine_pools(...)`
- `validate_piscine_datasets(...)`
- `write_piscine_status(...)`

The workflow should run in ordered passes:

1. discover available legacy content by track
2. map legacy exercises to canonical exercise IDs
3. import or normalize bundle files into canonical structure
4. attach metadata, provenance, and beginner-learning hooks
5. generate canonical piscine pools
6. validate all imported bundles and pools
7. run targeted piscine-session progression checks on imported content
8. emit machine-readable reports and `PISCINE_DATASET_STATUS.md`

## Legacy Mapping Strategy

For each imported exercise:

- assign one canonical ID: `piscine.<group>.<slug>`
- retain original source identifiers in `source.origin_id`
- retain original source paths in `source.origin_path`
- normalize filenames only when deterministic
- keep authored statements in Markdown
- keep starter/reference/tests separate

Mapping policy:

- prefer one canonical exercise per distinct legacy task
- avoid merging semantically different legacy variants into one bundle
- keep unresolved duplicates explicit in reports instead of silently collapsing them

## Runtime Bundle Population

Each imported exercise should be classified into one of these states:

- `runtime_ready`
- `structurally_valid_but_incomplete`
- `missing_runtime_content`
- `manual_repair_required`

Import checks per exercise:

- required files present
- starter bundle present
- reference bundle present
- tests manifest present
- harness present when needed
- expected file mapping consistent
- build metadata resolvable
- grading path runnable end to end

The goal is to populate canonical runtime-ready bundles, not just metadata shells.

## Pool Construction

Create canonical piscine pools for:

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

Pool rules:

- keep `track: piscine`
- keep `mode: practice`
- use ordered progression by default unless legacy sequencing requires otherwise
- use explicit level unlock rules
- prefer `repeat_policy: avoid_passed`
- keep time metadata simple and deterministic

Subjects PDFs may inform ordering, titles, and prerequisite flow, but not runtime file generation.

## Learning Metadata

Attach `learning` metadata where source evidence is sufficient.

Preferred hooks:

- `visible_edge_cases`
- `hints`
- `observation`

Population policy:

- derive visible edge cases from existing tests when they are obvious and stable
- derive hints from statement constraints and common failure modes when deterministic
- add observation hooks only when the runtime shape supports meaningful previews
- omit uncertain hooks rather than inventing low-quality guidance

## Validation

Validate imported bundles and pools with the existing stack:

- `CatalogService.build_index()`
- exercise manifest validation
- pool manifest validation
- `PoolEngineService` candidate resolution
- `PiscineSessionService` progression on imported sample pools
- grading-engine execution on runtime-ready imported bundles

Validation must separate:

- schema validity
- bundle structural validity
- runtime validity

## Staging and Output Layout

Keep import outputs staged and explicit.

Suggested staging layout:

```text
platform/runtime/staging/import_legacy/latest/piscine_import/
  raw/
  normalized/
  reports/
    piscine_sources.latest.yml
    piscine_import.latest.yml
    piscine_validation.latest.yml
    piscine_missing.latest.yml
```

Canonical checked-in outputs remain:

- `platform/datasets/exercises/piscine/...`
- `platform/datasets/pools/piscine/...`

If a staged-first workflow is needed before promotion, promotion into checked-in canonical datasets should happen only after validation passes.

## Reporting

Produce `PISCINE_DATASET_STATUS.md` with:

- imported exercise counts by track
- imported pool counts
- missing or incomplete exercises
- unresolved migration gaps

Machine-readable reports should also include:

- per-track discovered source counts
- per-track imported canonical exercise counts
- per-exercise provenance
- per-exercise validation state
- missing runtime assets
- unresolved duplicate or ambiguous mappings

## Tests

Add tests for:

- piscine dataset loading across imported tracks
- piscine pool validation for imported pool manifests
- piscine session progression on imported canonical content

Suggested test shape:

- fixture repos with imported piscine bundles
- catalog load assertions for imported IDs
- pool-engine unlock assertions on imported pools
- one or more progression tests through `PiscineSessionService`

## Non-Goals

This phase does not include:

- UI
- productivity features
- K&R lab content
- engine redesign
- unsafe content reconstruction from PDFs alone

## Implementation Order

1. build source discovery and legacy-to-canonical mapping
2. import runtime-ready exercises for `shell00`, `shell01`, and `c00` first
3. validate the imported bundles and pools end to end
4. extend track-by-track through `c13`
5. generate `PISCINE_DATASET_STATUS.md`
6. promote validated canonical datasets without changing the piscine engine contract
