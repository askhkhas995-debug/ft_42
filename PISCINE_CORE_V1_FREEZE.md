# Piscine Core v1 Freeze

This document marks the freeze of the canonical C00-C03 piscine dataset subset, designated as **Piscine Core v1**. 

## 1. Imported Canonical Tracks
The following legacy blocks have been successfully discovered, generated, validated, and promoted to canonical format:
- `c00`
- `c01`
- `c02`
- `c03`

## 2. Imported Exercise Count
**Total: 13**
- `c00`: 4
- `c01`: 2
- `c02`: 3
- `c03`: 4

## 3. Imported Pool Count
**Total: 4**
- `c00` (`piscine.c00.foundations`): 1
- `c01` (`piscine.c01.core`): 1
- `c02` (`piscine.c02.core`): 1
- `c03` (`piscine.c03.core`): 1

## 4. Known Exclusions
- `piscine.c03.ft_swap` was explicitly excluded from `c03` due to an irreparable runtime fault in the legacy test harness that made grading non-viable without fixes.

## 5. Validation Status
- **Catalog Validation**: Passing. All exercises and pools are healthy and loadable.
- **Pool Validation**: Passing. All core pool manifests are topologically valid without candidate gaps.

## 6. Grading Status
- **Execution Validation**: Passing. Real execution against reference solutions using designated compilation modes and grading strategies (`stdout diff`, etc.) completes cleanly across the subset.

## 7. Progression Status
- **Session Ordering**: Passing. The session progression rules have been verified to unlock consecutive levels within each individual piscine track precisely as defined:
  - `piscine.c00.ft_putchar` → `piscine.c00.ft_print_numbers` → `piscine.c00.ft_countdown` → `piscine.c00.ft_putstr`
  - `piscine.c01.ft_strlen` → `piscine.c01.ft_strcpy`
  - `piscine.c02.ulstr` → `piscine.c02.search_and_replace` → `piscine.c02.repeat_alpha`
  - `piscine.c03.first_word` → `piscine.c03.rev_print` → `piscine.c03.rotone` → `piscine.c03.rot_13`

## 8. Promotion-Safe Dataset Locations
The subset has been safely persisted and promoted into the runtime environment:
- **Canonical Exercises**: `platform/datasets/exercises/piscine/`
- **Canonical Pools**: `platform/datasets/pools/piscine/`

## 9. Backlog for Next Import Block
The next wave of processing should continue with the following modules, maintaining the unmodified import engine and format requirements:
- `c04`
- `c05`
- `c06`
- `c07`
