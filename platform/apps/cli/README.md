# CLI App

Learner-facing and operator-facing command-line interface for the local-first platform.

## Learner Commands

- `home`
- `curriculum`
- `module show <id>`
- `exercise start <id> [--workspace PATH]`
- `start --exercise-id <id> [--workspace PATH]`
- `submit <workspace>`
- `progress`
- `history`
- `exam start [--pool-id ID] [--workspace PATH]`
- `exam submit <workspace>`

## Operator Commands

- `list-exercises [--track TRACK]`
- `list-pools [--track TRACK]`
- `show-pool POOL_ID`
- `resolve-candidates POOL_ID --session-id SESSION_ID [--level LEVEL]`
- `select-next POOL_ID --session-id SESSION_ID`
- `grade-attempt ATTEMPT_ID`
- `grade-submission --exercise-id ID --submission PATH [--attempt-id ID]`

## Product Notes

- `datasets/exercises/`, `datasets/pools/`, and `datasets/curriculum/` are canonical.
- `storage/` keeps persistent learner state.
- `runtime/` keeps execution artifacts only.
- `runtime/staging/import_legacy/` is generated import workspace only.

The preferred learner binary name is `grademe`, with `platform-cli` kept as a compatible entrypoint.
