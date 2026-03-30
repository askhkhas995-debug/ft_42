# Piscine Mode Status

## Supported Tracks

The `PiscineSessionService` now defines the piscine curriculum contract for:

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

The current checked-in canonical piscine dataset inventory is still limited to:

- `piscine.c00.foundations`
- `piscine.c00.ft_putchar`
- `piscine.c00.ft_print_numbers`
- `piscine.c00.ft_countdown`
- `piscine.c00.ft_putstr`

## Tested Flows

Implemented and verified with targeted tests:

- start session and select current next exercise
- pass-first progression into the next unlocked exercise
- pool completion distinct from explicit session finish
- resume/load state through `load_or_start(...)`
- recovery of next assignment when persisted `current_assignment` is missing
- beginner metadata hook loading for visible edge cases, hints, and observation hooks
- existing piscine pool-engine unlock behavior after the manifest extension

Verification run:

```bash
python3 -m py_compile \
  platform/core/catalog/src/platform_catalog/validation.py \
  platform/core/sessions/src/platform_sessions/__init__.py \
  platform/core/sessions/src/platform_sessions/piscine.py \
  platform/tests/test_piscine_session_engine.py

cd platform && \
PYTHONPATH=core/catalog/src:core/scheduler/src:core/grading/src:core/storage/src:core/sandbox/src:core/sessions/src \
pytest -q tests/test_piscine_session_engine.py tests/test_pool_engine.py
```

Result:

- `12 passed`

## Current Limitations

- Piscine logic is implemented and kept separate from exam logic, but canonical piscine content currently exists only for the first `c00` pool and four `c00` exercises.
- `shell00`, `shell01`, and `c01` to `c13` are supported by the service contract, but they still need canonical pool and exercise bundles before they are runnable.
- Beginner-friendly `learning` hooks are metadata-only in this implementation. They are exposed through the catalog/session layer, but no UI or interactive observation runner exists yet.
- No productivity features were added.
- No K&R labs were added.
