from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from platform_catalog import CatalogService
from platform_catalog.models import (
    PoolDataset,
    PoolExerciseRef,
    PoolIndexEntry,
    PoolLevel,
    PoolSelectionConfig,
    PoolTimingConfig,
    PoolUnlockRule,
)
from platform_catalog.pool_validation import validate_pool_manifest
from platform_scheduler import PoolEngineService, SessionExerciseRecord


PLATFORM_ROOT = Path(__file__).resolve().parents[1]


def _session_record(
    *,
    exercise_id: str,
    variant_id: str = "normal",
    passed: bool = False,
    pool_id: str = "custom.pool",
    attempt_id: str = "attempt.1",
    created_at: str = "2026-03-06T00:00:00Z",
) -> SessionExerciseRecord:
    return SessionExerciseRecord(
        attempt_id=attempt_id,
        exercise_id=exercise_id,
        variant_id=variant_id,
        pool_id=pool_id,
        created_at=created_at,
        passed=passed,
    )


def _build_pool(
    *,
    strategy: str,
    repeat_policy: str,
    recent_window: int = 0,
    refs: list[PoolExerciseRef] | None = None,
) -> PoolDataset:
    exercise_refs = refs or [
        PoolExerciseRef(exercise_id="piscine.c00.ft_putchar", variant_id="normal", order=10, declaration_index=0),
        PoolExerciseRef(exercise_id="piscine.c00.ft_putchar", variant_id="prediction", order=20, declaration_index=1),
    ]
    return PoolDataset(
        entry=PoolIndexEntry(
            pool_id="custom.pool",
            track="piscine",
            slug="custom-pool",
            title="Custom Pool",
            mode="practice",
            manifest_path=PLATFORM_ROOT / "datasets/pools/piscine/c00-foundations/pool.yml",
            root_path=PLATFORM_ROOT / "datasets/pools/piscine/c00-foundations",
        ),
        manifest={},
        manifest_path=PLATFORM_ROOT / "datasets/pools/piscine/c00-foundations/pool.yml",
        root_path=PLATFORM_ROOT / "datasets/pools/piscine/c00-foundations",
        selection=PoolSelectionConfig(
            strategy=strategy,
            repeat_policy=repeat_policy,
            recent_window=recent_window,
            seed_policy="deterministic_per_session",
        ),
        timing=PoolTimingConfig(
            total_time_seconds=1800,
            per_level_time_seconds=900,
            cooldown_enabled=False,
            cooldown_seconds=0,
            cooldown_scope="pool",
        ),
        levels=[
            PoolLevel(
                level=0,
                title="Level 0",
                min_picks=1,
                max_picks=None,
                time_limit_seconds=600,
                unlock_if=PoolUnlockRule(all_of=[], any_of=[]),
                exercise_refs=exercise_refs,
            )
        ],
    )


def test_catalog_loads_sample_pools() -> None:
    catalog = CatalogService(PLATFORM_ROOT)

    pool_ids = {entry.pool_id for entry in catalog.list_pools()}

    assert "piscine.c00.foundations" in pool_ids
    assert "exams.exam00.starter" in pool_ids

    piscine_pool = catalog.load_pool("piscine.c00.foundations")
    exams_pool = catalog.load_pool("exams.exam00.starter")

    assert piscine_pool.levels[0].time_limit_seconds == 600
    assert piscine_pool.levels[1].time_limit_seconds == 600
    assert piscine_pool.levels[3].time_limit_seconds == 900
    assert exams_pool.selection.strategy == "weighted"
    assert exams_pool.levels[0].time_limit_seconds == 600


def test_catalog_loads_imported_c00_exercises() -> None:
    catalog = CatalogService(PLATFORM_ROOT)

    print_numbers = catalog.load_exercise("piscine.c00.ft_print_numbers")
    countdown = catalog.load_exercise("piscine.c00.ft_countdown")

    assert print_numbers.entry.group == "c00"
    assert print_numbers.harness_path is not None
    assert countdown.entry.group == "c00"
    assert countdown.harness_path is None


def test_validate_pool_manifest_rejects_unknown_keys() -> None:
    catalog = CatalogService(PLATFORM_ROOT)
    dataset = catalog.load_pool("piscine.c00.foundations")
    manifest = deepcopy(dataset.manifest)
    manifest["selection"]["unexpected"] = True

    failures = validate_pool_manifest(manifest, dataset.manifest_path, dataset.entry.track)

    assert any(failure.location == "pool.selection.unexpected" for failure in failures)


def test_pool_engine_avoid_passed_is_variant_aware(monkeypatch) -> None:
    engine = PoolEngineService(PLATFORM_ROOT)
    pool = _build_pool(strategy="ordered", repeat_policy="avoid_passed")

    monkeypatch.setattr(PoolEngineService, "load_pool", lambda self, pool_id: pool)

    candidates = engine.resolve_candidates(
        "custom.pool",
        session_history=[
            _session_record(
                exercise_id="piscine.c00.ft_putchar",
                variant_id="normal",
                passed=True,
            )
        ],
        session_id="session.variant-aware",
    )

    assert [(candidate.exercise_id, candidate.variant_id) for candidate in candidates] == [
        ("piscine.c00.ft_putchar", "prediction")
    ]


def test_pool_engine_avoid_recent_is_variant_aware(monkeypatch) -> None:
    engine = PoolEngineService(PLATFORM_ROOT)
    pool = _build_pool(strategy="ordered", repeat_policy="avoid_recent", recent_window=1)

    monkeypatch.setattr(PoolEngineService, "load_pool", lambda self, pool_id: pool)

    candidates = engine.resolve_candidates(
        "custom.pool",
        session_history=[
            _session_record(
                exercise_id="piscine.c00.ft_putchar",
                variant_id="normal",
                passed=False,
            )
        ],
        session_id="session.recent-aware",
    )

    assert [(candidate.exercise_id, candidate.variant_id) for candidate in candidates] == [
        ("piscine.c00.ft_putchar", "prediction")
    ]


def test_random_strategy_selects_from_eligible_candidates(monkeypatch) -> None:
    engine = PoolEngineService(PLATFORM_ROOT)
    pool = _build_pool(strategy="random", repeat_policy="allow_review")

    monkeypatch.setattr(PoolEngineService, "load_pool", lambda self, pool_id: pool)

    selection = engine.select_next("custom.pool", "session.random")

    assert selection["selection_strategy"] == "random"
    assert (selection["exercise_id"], selection["variant_id"]) in {
        ("piscine.c00.ft_putchar", "normal"),
        ("piscine.c00.ft_putchar", "prediction"),
    }
    assert selection["timing"]["effective_level_time_seconds"] == 600


def test_sample_piscine_pool_unlocks_next_level_after_pass() -> None:
    engine = PoolEngineService(PLATFORM_ROOT)

    selection = engine.select_next(
        "piscine.c00.foundations",
        "session.piscine.progression",
        session_history=[
            _session_record(
                exercise_id="piscine.c00.ft_putchar",
                variant_id="normal",
                passed=True,
                pool_id="piscine.c00.foundations",
            )
        ],
    )

    assert selection["exercise_id"] == "piscine.c00.ft_print_numbers"
    assert selection["level"] == 1
    assert selection["selection_strategy"] == "ordered"
    assert selection["timing"]["effective_level_time_seconds"] == 600


def test_sample_exam_pool_allow_review_keeps_candidates_available() -> None:
    engine = PoolEngineService(PLATFORM_ROOT)

    candidates = engine.resolve_candidates(
        "exams.exam00.starter",
        session_history=[
            _session_record(
                exercise_id="exams.exam00.ft_putchar",
                variant_id="normal",
                passed=True,
                pool_id="exams.exam00.starter",
            ),
            _session_record(
                exercise_id="exams.exam00.ft_putstr",
                variant_id="normal",
                passed=False,
                pool_id="exams.exam00.starter",
                attempt_id="attempt.2",
                created_at="2026-03-06T00:01:00Z",
            ),
        ],
        session_id="session.exam.review",
    )

    assert {(candidate.exercise_id, candidate.variant_id) for candidate in candidates} == {
        ("exams.exam00.ft_putchar", "normal"),
        ("exams.exam00.ft_putstr", "normal"),
    }
