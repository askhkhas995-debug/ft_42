# Import Legacy Tooling

Legacy repository import helpers for legacy exam repositories live here.

Current scope:

- discover `ExamPoolRevanced-main`, `Exam00`, `Exam01`, `Exam02`, and `ExamFinal`
- normalize legacy assignments into canonical exercise bundles
- normalize legacy pool YAML into canonical `pool.yml`
- emit migration reports for invalid or conflicting legacy content
- support safe write-mode staging imports under `platform/runtime/staging/import_legacy/latest/`
- validate staged accepted datasets with the catalog and pool validators
