"""Shared grading contracts for the C grading prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(slots=True)
class BuildResult:
    """Compile step result."""

    status: str
    compiler: str = ""
    command: list[str] = field(default_factory=list)
    exit_code: int = 0
    stdout_path: str | None = None
    stderr_path: str | None = None
    binary_path: str | None = None
    diagnostics: dict = field(default_factory=lambda: {"errors": 0, "warnings": 0})
    duration_ms: int = 0


@dataclass(slots=True)
class RunResult:
    """Single test-case runtime result."""

    status: str
    command: list[str] = field(default_factory=list)
    exit_code: int = 0
    stdout_path: str | None = None
    stderr_path: str | None = None
    trace_path: str | None = None
    duration_ms: int = 0
    timed_out: bool = False
    signal: str = ""
    memory_limit_hit: bool = False
    test_id: str = ""


@dataclass(slots=True)
class ComparisonResult:
    """Aggregated comparison result across test cases."""

    passed: bool
    raw_score: float
    failure_class: str = "none"
    notes: list[str] = field(default_factory=list)
    diff_path: str | None = None
    passed_test_ids: list[str] = field(default_factory=list)
    failed_test_ids: list[str] = field(default_factory=list)


class Plugin(Protocol):
    """Minimal runtime protocol for grading plugins."""

    plugin_id: str

    def validate(self, config: dict, exercise_manifest: dict) -> list[str]:
        """Return validation errors."""


@dataclass(slots=True)
class TestCase:
    """Declarative test case loaded from `tests.yml`."""

    test_id: str
    argv: list[str] = field(default_factory=list)
    stdin: str = ""
    expected_stdout: str | None = None
    expected_stderr: str = ""
    expected_exit_code: int = 0


@dataclass(slots=True)
class AttemptContext:
    """Resolved attempt data needed by the grading engine."""

    attempt_id: str
    session_id: str
    user_id: str
    exercise_id: str
    variant_id: str
    mode: str
    pool_id: str | None
    submission_root: Path
    attempt_index_for_exercise: int = 1
