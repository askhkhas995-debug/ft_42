"""Typed catalog models for dataset-driven exercises."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_TRACKS = (
    "piscine",
    "exams",
    "knr",
    "theory_to_practice",
    "bug_injection",
    "completion",
    "prediction",
)


@dataclass(slots=True)
class CatalogFile:
    """One file inside a starter/reference directory bundle."""

    relative_path: str
    absolute_path: Path


@dataclass(slots=True)
class ExerciseTestCase:
    """Typed testcase loaded from `tests.yml`."""

    test_id: str
    argv: list[str] = field(default_factory=list)
    stdin: str = ""
    expected_stdout: str | None = None
    expected_stderr: str = ""
    expected_exit_code: int = 0


@dataclass(slots=True)
class ExerciseIndexEntry:
    """Catalog summary entry for one exercise."""

    exercise_id: str
    track: str
    group: str
    slug: str
    title: str
    language: str
    difficulty_level: int
    manifest_path: Path
    root_path: Path


@dataclass(slots=True)
class ExerciseDataset:
    """Fully loaded dataset bundle for one exercise."""

    entry: ExerciseIndexEntry
    manifest: dict
    manifest_path: Path
    root_path: Path
    statement_path: Path
    statement_markdown: str
    tests_path: Path
    harness_path: Path | None
    tests: list[ExerciseTestCase]
    starter_dir: Path
    starter_files: list[CatalogFile]
    reference_dir: Path
    reference_files: list[CatalogFile]

    @property
    def exercise_id(self) -> str:
        return self.entry.exercise_id

    @property
    def track(self) -> str:
        return self.entry.track

    @property
    def expected_files(self) -> list[str]:
        return list(self.manifest["student_contract"]["expected_files"])


@dataclass(slots=True)
class PoolExerciseRef:
    """One exercise reference declared inside a pool level."""

    exercise_id: str
    variant_id: str = "normal"
    weight: int = 1
    order: int | None = None
    declaration_index: int = 0

    @property
    def candidate_key(self) -> tuple[str, str]:
        return (self.exercise_id, self.variant_id)


@dataclass(slots=True)
class PoolUnlockRule:
    """Unlock prerequisites for a level."""

    all_of: list[int] = field(default_factory=list)
    any_of: list[int] = field(default_factory=list)


@dataclass(slots=True)
class PoolLevel:
    """One level inside a level-based pool."""

    level: int
    title: str
    min_picks: int
    max_picks: int | None
    time_limit_seconds: int | None
    unlock_if: PoolUnlockRule
    exercise_refs: list[PoolExerciseRef]


@dataclass(slots=True)
class PoolSelectionConfig:
    """Selection and repeat policies for a pool."""

    strategy: str
    repeat_policy: str
    recent_window: int
    seed_policy: str


@dataclass(slots=True)
class PoolTimingConfig:
    """Time and cooldown metadata for a pool."""

    total_time_seconds: int
    per_level_time_seconds: int
    cooldown_enabled: bool
    cooldown_seconds: int
    cooldown_scope: str


@dataclass(slots=True)
class PoolIndexEntry:
    """Catalog summary entry for one pool dataset."""

    pool_id: str
    track: str
    slug: str
    title: str
    mode: str
    manifest_path: Path
    root_path: Path


@dataclass(slots=True)
class PoolDataset:
    """Fully loaded and validated pool dataset bundle."""

    entry: PoolIndexEntry
    manifest: dict
    manifest_path: Path
    root_path: Path
    selection: PoolSelectionConfig
    timing: PoolTimingConfig
    levels: list[PoolLevel]

    @property
    def pool_id(self) -> str:
        return self.entry.pool_id
