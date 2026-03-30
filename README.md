# ft_42 – Local 42 Practice + Exam Simulator

This repository now contains a working local platform to practice 42-style exercises and run exam simulations directly on your PC.

The main product lives in `platform/`.

## What You Can Do Right Now

- Start a **practice exercise workspace** with statement + starter files.
- Submit the workspace and get a local grading report.
- Start an **exam session** from canonical pools.
- Continue the exam level-by-level by submitting locally.
- Use a lightweight **exam shell helper** to inspect the current exam workspace status.

## Quick Start (from project root)

```bash
cd platform
python3 -m pytest
```

For CLI commands, use:

```bash
export PYTHONPATH="apps/cli/src:apps/dashboard/src:core/catalog/src:core/curriculum/src:core/exams/src:core/grading/src:core/progression/src:core/sandbox/src:core/scheduler/src:core/sessions/src:core/storage/src:tooling"
```

### Practice Flow

```bash
python3 -m platform_cli.main start --exercise-id piscine.c00.ft_putchar --workspace /tmp/ft42-practice
python3 -m platform_cli.main submit /tmp/ft42-practice
```

### Exam Flow

```bash
python3 -m platform_cli.main exam start --workspace /tmp/ft42-exam
python3 -m platform_cli.main exam shell /tmp/ft42-exam
python3 -m platform_cli.main exam submit /tmp/ft42-exam
```

## Important Notes

- Canonical source content is under `platform/datasets/**`.
- Learner state lives under `platform/storage/**`.
- Runtime workspaces and generated artifacts are under `platform/runtime/**`.

See `platform/README.md` for architecture and deeper product details.
