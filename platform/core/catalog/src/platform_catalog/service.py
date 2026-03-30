"""Dataset catalog service for strict exercise and pool bundle loading and indexing."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from platform_catalog.models import (
    CatalogFile,
    ExerciseDataset,
    ExerciseIndexEntry,
    PoolDataset,
    PoolIndexEntry,
    SUPPORTED_TRACKS,
)
from platform_catalog.pool_validation import build_pool_models, validate_pool_manifest
from platform_catalog.validation import (
    CatalogValidationError,
    CatalogValidationFailure,
    validate_bundle_assets,
    validate_manifest,
    validate_tests_payload,
)


@dataclass(slots=True)
class CatalogService:
    """Resolve and index canonical exercise datasets from the repository tree."""

    repository_root: Path
    _index_cache: dict[str, ExerciseIndexEntry] = field(default_factory=dict, init=False)
    _dataset_cache: dict[str, ExerciseDataset] = field(default_factory=dict, init=False)
    _pool_index_cache: dict[str, PoolIndexEntry] = field(default_factory=dict, init=False)
    _pool_dataset_cache: dict[str, PoolDataset] = field(default_factory=dict, init=False)

    def resolve(self, relative_path: str | Path) -> Path:
        """Resolve a repository-relative path."""
        return self.repository_root / Path(relative_path)

    def load_manifest(self, relative_path: str | Path) -> dict:
        """Load a YAML manifest by repository-relative path."""
        manifest_path = self.resolve(relative_path)
        with manifest_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def supported_tracks(self) -> tuple[str, ...]:
        """Return canonical dataset tracks supported by the catalog."""
        return SUPPORTED_TRACKS

    def exercises_root(self) -> Path:
        """Return the repository root for canonical exercise bundles."""
        return self.resolve("datasets/exercises")

    def pools_root(self) -> Path:
        """Return the repository root for canonical pool bundles."""
        return self.resolve("datasets/pools")

    def _load_yaml(self, path: Path) -> dict:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _read_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def _exercise_manifest_paths(self) -> list[Path]:
        manifests: list[Path] = []
        base = self.exercises_root()
        for track in self.supported_tracks():
            track_root = base / track
            if not track_root.exists():
                continue
            manifests.extend(sorted(track_root.rglob("exercise.yml")))
        return manifests

    def _pool_manifest_paths(self) -> list[Path]:
        manifests: list[Path] = []
        base = self.pools_root()
        for track in self.supported_tracks():
            track_root = base / track
            if not track_root.exists():
                continue
            manifests.extend(sorted(track_root.rglob("pool.yml")))
        return manifests

    def _track_for_manifest(self, manifest_path: Path) -> str:
        dataset_root = self.exercises_root()
        if manifest_path.is_relative_to(self.pools_root()):
            dataset_root = self.pools_root()
        relative = manifest_path.relative_to(dataset_root)
        return relative.parts[0]

    def _directory_inventory(self, directory: Path) -> list[CatalogFile]:
        if not directory.exists() or not directory.is_dir():
            return []
        files: list[CatalogFile] = []
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            files.append(CatalogFile(relative_path=str(path.relative_to(directory)), absolute_path=path))
        return files

    def _build_dataset(self, manifest_path: Path) -> ExerciseDataset:
        manifest = self._load_yaml(manifest_path)
        declared_track = self._track_for_manifest(manifest_path)
        failures: list[CatalogValidationFailure] = validate_manifest(manifest, manifest_path, declared_track)

        root_path = manifest_path.parent
        files = manifest.get("files", {})
        statement_path = root_path / files.get("statement", "statement.md")
        tests_dir = root_path / files.get("tests_dir", "tests")
        tests_path = tests_dir / "tests.yml"
        starter_dir = root_path / files.get("starter_dir", "starter")
        reference_dir = root_path / files.get("reference_dir", "reference")

        if not statement_path.exists():
            failures.append(CatalogValidationFailure(location=str(statement_path), message="missing statement file"))
            statement_markdown = ""
        else:
            statement_markdown = self._read_text(statement_path)

        if not tests_path.exists():
            failures.append(CatalogValidationFailure(location=str(tests_path), message="missing tests manifest"))
            tests_payload = {}
            test_failures: list[CatalogValidationFailure] = []
            tests = []
        else:
            tests_payload = self._load_yaml(tests_path)
            test_failures, tests = validate_tests_payload(tests_payload)
        failures.extend(test_failures)

        harness_path = tests_dir / "main.c"
        if not harness_path.exists():
            harness = None
        else:
            harness = harness_path

        starter_files = self._directory_inventory(starter_dir)
        reference_files = self._directory_inventory(reference_dir)
        if not starter_dir.exists():
            failures.append(CatalogValidationFailure(location=str(starter_dir), message="missing starter directory"))
        if not reference_dir.exists():
            failures.append(CatalogValidationFailure(location=str(reference_dir), message="missing reference directory"))

        failures.extend(
            validate_bundle_assets(
                manifest,
                statement_markdown=statement_markdown,
                harness_path=harness,
                starter_files=starter_files,
                reference_files=reference_files,
            )
        )

        if failures:
            raise CatalogValidationError(failures)

        entry = ExerciseIndexEntry(
            exercise_id=manifest["id"],
            track=manifest["track"],
            group=manifest["group"],
            slug=manifest["slug"],
            title=manifest["title"],
            language=manifest["language"],
            difficulty_level=manifest["difficulty"]["level"],
            manifest_path=manifest_path,
            root_path=root_path,
        )
        return ExerciseDataset(
            entry=entry,
            manifest=manifest,
            manifest_path=manifest_path,
            root_path=root_path,
            statement_path=statement_path,
            statement_markdown=statement_markdown,
            tests_path=tests_path,
            harness_path=harness,
            tests=tests,
            starter_dir=starter_dir,
            starter_files=starter_files,
            reference_dir=reference_dir,
            reference_files=reference_files,
        )

    def _build_pool_dataset(self, manifest_path: Path) -> PoolDataset:
        manifest = self._load_yaml(manifest_path)
        declared_track = self._track_for_manifest(manifest_path)
        failures = validate_pool_manifest(manifest, manifest_path, declared_track)
        root_path = manifest_path.parent

        if failures:
            raise CatalogValidationError(failures)

        self.build_index()
        for level_index, level in enumerate(manifest["levels"]):
            for ref_index, ref in enumerate(level["exercise_refs"]):
                exercise_id = ref["exercise_id"]
                variant_id = ref.get("variant", "normal")
                if exercise_id not in self._dataset_cache:
                    failures.append(
                        CatalogValidationFailure(
                            location=f"pool.levels[{level_index}].exercise_refs[{ref_index}].exercise_id",
                            message=f"unknown exercise id {exercise_id!r}",
                        )
                    )
                    continue
                exercise = self._dataset_cache[exercise_id]
                available_variants = {item["id"] for item in exercise.manifest["variants"]["available"]}
                if variant_id not in available_variants:
                    failures.append(
                        CatalogValidationFailure(
                            location=f"pool.levels[{level_index}].exercise_refs[{ref_index}].variant",
                            message=f"unknown variant {variant_id!r} for exercise {exercise_id!r}",
                        )
                    )
        if failures:
            raise CatalogValidationError(failures)

        selection, timing, levels = build_pool_models(manifest)
        entry = PoolIndexEntry(
            pool_id=manifest["id"],
            track=manifest["track"],
            slug=root_path.name,
            title=manifest["title"],
            mode=manifest["mode"],
            manifest_path=manifest_path,
            root_path=root_path,
        )
        return PoolDataset(
            entry=entry,
            manifest=manifest,
            manifest_path=manifest_path,
            root_path=root_path,
            selection=selection,
            timing=timing,
            levels=levels,
        )

    def build_index(self, refresh: bool = False) -> dict[str, ExerciseIndexEntry]:
        """Validate and index all canonical exercise bundles."""
        if self._index_cache and not refresh:
            return dict(self._index_cache)

        index: dict[str, ExerciseIndexEntry] = {}
        datasets: dict[str, ExerciseDataset] = {}
        failures: list[CatalogValidationFailure] = []
        for manifest_path in self._exercise_manifest_paths():
            try:
                dataset = self._build_dataset(manifest_path)
            except CatalogValidationError as exc:
                failures.extend(exc.failures)
                continue
            if dataset.exercise_id in index:
                failures.append(
                    CatalogValidationFailure(
                        location=str(manifest_path),
                        message=f"duplicate exercise id {dataset.exercise_id!r}",
                    )
                )
                continue
            index[dataset.exercise_id] = dataset.entry
            datasets[dataset.exercise_id] = dataset

        if failures:
            raise CatalogValidationError(failures)

        self._index_cache = index
        self._dataset_cache = datasets
        return dict(self._index_cache)

    def build_pool_index(self, refresh: bool = False) -> dict[str, PoolIndexEntry]:
        """Validate and index all canonical pool bundles."""
        if self._pool_index_cache and not refresh:
            return dict(self._pool_index_cache)

        self.build_index()
        index: dict[str, PoolIndexEntry] = {}
        datasets: dict[str, PoolDataset] = {}
        failures: list[CatalogValidationFailure] = []
        for manifest_path in self._pool_manifest_paths():
            try:
                dataset = self._build_pool_dataset(manifest_path)
            except CatalogValidationError as exc:
                failures.extend(exc.failures)
                continue
            if dataset.pool_id in index:
                failures.append(
                    CatalogValidationFailure(
                        location=str(manifest_path),
                        message=f"duplicate pool id {dataset.pool_id!r}",
                    )
                )
                continue
            index[dataset.pool_id] = dataset.entry
            datasets[dataset.pool_id] = dataset

        if failures:
            raise CatalogValidationError(failures)

        self._pool_index_cache = index
        self._pool_dataset_cache = datasets
        return dict(self._pool_index_cache)

    def list_exercises(self, track: str | None = None) -> list[ExerciseIndexEntry]:
        """Return indexed exercises, optionally filtered by track."""
        entries = list(self.build_index().values())
        if track is not None:
            entries = [entry for entry in entries if entry.track == track]
        return sorted(entries, key=lambda entry: (entry.track, entry.group, entry.slug))

    def list_pools(self, track: str | None = None) -> list[PoolIndexEntry]:
        """Return indexed pools, optionally filtered by track."""
        entries = list(self.build_pool_index().values())
        if track is not None:
            entries = [entry for entry in entries if entry.track == track]
        return sorted(entries, key=lambda entry: (entry.track, entry.slug))

    def find_exercise_manifest(self, exercise_id: str) -> Path:
        """Return the manifest path for a canonical exercise id."""
        self.build_index()
        try:
            return self._index_cache[exercise_id].manifest_path
        except KeyError as exc:
            raise FileNotFoundError(f"Unable to resolve exercise id: {exercise_id}") from exc

    def load_exercise(self, exercise_id: str) -> ExerciseDataset:
        """Load a fully validated exercise dataset by id."""
        self.build_index()
        try:
            return self._dataset_cache[exercise_id]
        except KeyError as exc:
            raise FileNotFoundError(f"Unable to resolve exercise id: {exercise_id}") from exc

    def load_pool(self, pool_id: str) -> PoolDataset:
        """Load a fully validated pool dataset by id."""
        self.build_pool_index()
        try:
            return self._pool_dataset_cache[pool_id]
        except KeyError as exc:
            raise FileNotFoundError(f"Unable to resolve pool id: {pool_id}") from exc

    def resolve_from_manifest(self, manifest_path: Path, relative_path: str) -> Path:
        """Resolve a path relative to a manifest directory."""
        return manifest_path.parent / relative_path
