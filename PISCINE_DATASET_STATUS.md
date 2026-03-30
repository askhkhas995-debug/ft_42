# PISCINE_DATASET_STATUS

- Generated at: `2026-03-07T15:19:57Z`
- Staging root: `/home/xapet/Desktop/f/platform/runtime/staging/import_legacy/latest/piscine_import/latest`
- Repository root: `/home/xapet/Desktop/f/platform/runtime/staging/import_legacy/latest/piscine_import/latest/repository_root`

## Discovered Source Counts

- `shell00`: sources=`1`, discovered candidates=`0`, importable candidates=`0`
- `shell01`: sources=`1`, discovered candidates=`0`, importable candidates=`0`
- `c00`: sources=`3`, discovered candidates=`11`, importable candidates=`4`
- `c01`: sources=`2`, discovered candidates=`2`, importable candidates=`2`
- `c02`: sources=`2`, discovered candidates=`3`, importable candidates=`3`
- `c03`: sources=`2`, discovered candidates=`6`, importable candidates=`4`

## Imported Canonical Exercise Counts

- `shell00`: `0`
- `shell01`: `0`
- `c00`: `4`
- `c01`: `2`
- `c02`: `3`
- `c03`: `4`

## Imported Pool Counts

- `shell00`: `0`
- `shell01`: `0`
- `c00`: `1`
- `c01`: `1`
- `c02`: `1`
- `c03`: `1`

## Missing Or Incomplete Exercises

- `shell00` (shell00, exercise_set): `missing_runtime_content` - no deterministic legacy runtime bundles were found in the current workspace
- `shell01` (shell01, exercise_set): `missing_runtime_content` - no deterministic legacy runtime bundles were found in the current workspace
- `piscine.shell00.foundations` (shell00, pool): `blocked` - pool generation is blocked until at least one runtime-valid shell00 exercise bundle exists
- `piscine.shell01.foundations` (shell01, pool): `blocked` - pool generation is blocked until at least one runtime-valid shell01 exercise bundle exists

## Unresolved Migration Gaps

- shell00 and shell01 have no deterministic runtime bundle sources in the current workspace
- the current canonical grading contract is C-only, so shell exercises cannot be promoted as runtime-ready without a shell runtime contract
- Subjects PDFs are available only for C00 to C13; no shell00 or shell01 PDF metadata is present locally

## Validation

- Catalog validation: `True`
- Pool validation: `True`
- Pool candidate resolution: `True`
- Piscine session progression: `True`
- Session progression order: `piscine.c00.ft_putchar, piscine.c00.ft_print_numbers, piscine.c00.ft_countdown, piscine.c00.ft_putstr, piscine.c01.ft_strlen, piscine.c01.ft_strcpy, piscine.c02.ulstr, piscine.c02.search_and_replace, piscine.c02.repeat_alpha, piscine.c03.first_word, piscine.c03.rev_print, piscine.c03.rotone, piscine.c03.rot_13`

## Grading Validation

- `piscine.c00.ft_putchar`: passed=`True`, failure_class=`none`
- `piscine.c00.ft_print_numbers`: passed=`True`, failure_class=`none`
- `piscine.c00.ft_countdown`: passed=`True`, failure_class=`none`
- `piscine.c00.ft_putstr`: passed=`True`, failure_class=`none`
- `piscine.c01.ft_strlen`: passed=`True`, failure_class=`none`
- `piscine.c01.ft_strcpy`: passed=`True`, failure_class=`none`
- `piscine.c02.ulstr`: passed=`True`, failure_class=`none`
- `piscine.c02.search_and_replace`: passed=`True`, failure_class=`none`
- `piscine.c02.repeat_alpha`: passed=`True`, failure_class=`none`
- `piscine.c03.first_word`: passed=`True`, failure_class=`none`
- `piscine.c03.rev_print`: passed=`True`, failure_class=`none`
- `piscine.c03.rotone`: passed=`True`, failure_class=`none`
- `piscine.c03.rot_13`: passed=`True`, failure_class=`none`

## Notes

- validated exercises=13 pools=4
