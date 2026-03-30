"""Dataset-driven pool engine and session exercise selector."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random

import yaml

from platform_catalog import CatalogService, PoolDataset, PoolExerciseRef, PoolLevel


@dataclass(slots=True)
class SessionExerciseRecord:
    """Observed exercise attempt inside a session."""

    attempt_id: str
    exercise_id: str
    variant_id: str
    pool_id: str | None
    created_at: str
    passed: bool

    @property
    def candidate_key(self) -> tuple[str, str]:
        return (self.exercise_id, self.variant_id)


@dataclass(slots=True)
class CandidateExercise:
    """Eligible candidate resolved from a pool level."""

    exercise_id: str
    variant_id: str
    level: int
    title: str
    weight: int
    order: int | None
    declaration_index: int

    @property
    def candidate_key(self) -> tuple[str, str]:
        return (self.exercise_id, self.variant_id)


@dataclass(slots=True)
class PoolEngineService:
    """Load pools, resolve candidates, and select the next exercise for a session."""

    repository_root: Path
    catalog: CatalogService = field(init=False)

    def __post_init__(self) -> None:
        self.catalog = CatalogService(self.repository_root)

    def load_pool(self, pool_id: str) -> PoolDataset:
        """Return a validated pool dataset."""
        return self.catalog.load_pool(pool_id)

    def _attempts_root(self) -> Path:
        return self.repository_root / "storage/attempts"

    def _reports_root(self) -> Path:
        return self.repository_root / "runtime/reports"

    def _latest_report_pass_map(self) -> dict[str, bool]:
        report_map: dict[str, tuple[float, bool]] = {}
        reports_root = self._reports_root()
        if not reports_root.exists():
            return {}
        for report_path in reports_root.glob("report.*.yml"):
            try:
                with report_path.open("r", encoding="utf-8") as handle:
                    payload = yaml.safe_load(handle) or {}
            except FileNotFoundError:
                continue
            attempt_id = payload.get("attempt_id")
            if not attempt_id:
                continue
            modified = report_path.stat().st_mtime
            passed = bool(payload.get("evaluation", {}).get("passed", False))
            existing = report_map.get(attempt_id)
            if existing is None or modified >= existing[0]:
                report_map[attempt_id] = (modified, passed)
        return {attempt_id: item[1] for attempt_id, item in report_map.items()}

    def load_session_history(self, session_id: str, pool_id: str | None = None) -> list[SessionExerciseRecord]:
        """Load session attempt history from local storage and reports."""
        history: list[SessionExerciseRecord] = []
        attempts_root = self._attempts_root()
        if not attempts_root.exists():
            return history
        report_map = self._latest_report_pass_map()
        for attempt_path in sorted(attempts_root.glob("*.jsonl")):
            records = []
            with attempt_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    records.append(yaml.safe_load(line))
            if not records:
                continue
            record = records[-1]
            if record.get("session_id") != session_id:
                continue
            if pool_id is not None and record.get("pool_id") != pool_id:
                continue
            attempt_id = record["attempt_id"]
            passed = bool(record.get("result", {}).get("passed", False))
            if attempt_id in report_map:
                passed = report_map[attempt_id]
            history.append(
                SessionExerciseRecord(
                    attempt_id=attempt_id,
                    exercise_id=record["exercise_id"],
                    variant_id=record.get("variant_id", "normal"),
                    pool_id=record.get("pool_id"),
                    created_at=record.get("created_at", ""),
                    passed=passed,
                )
            )
        history.sort(key=lambda item: (item.created_at, item.attempt_id))
        return history

    def _passed_candidates(self, history: list[SessionExerciseRecord]) -> set[tuple[str, str]]:
        return {item.candidate_key for item in history if item.passed}

    def _recent_candidates(self, history: list[SessionExerciseRecord], window: int) -> set[tuple[str, str]]:
        if window <= 0:
            return set()
        return {item.candidate_key for item in history[-window:]}

    def _level_seen_count(self, level: PoolLevel, history: list[SessionExerciseRecord]) -> int:
        level_candidate_keys = {item.candidate_key for item in level.exercise_refs}
        return sum(1 for item in history if item.candidate_key in level_candidate_keys)

    def _level_passed_count(self, level: PoolLevel, history: list[SessionExerciseRecord]) -> int:
        level_candidate_keys = {item.candidate_key for item in level.exercise_refs}
        return len({item.candidate_key for item in history if item.passed and item.candidate_key in level_candidate_keys})

    def _level_completed(self, level: PoolLevel, history: list[SessionExerciseRecord]) -> bool:
        return self._level_passed_count(level, history) >= level.min_picks

    def _level_unlocked(self, pool: PoolDataset, level: PoolLevel, history: list[SessionExerciseRecord]) -> bool:
        requirements = level.unlock_if
        if not requirements.all_of and not requirements.any_of:
            return True
        by_number = {item.level: item for item in pool.levels}
        all_passed = all(self._level_completed(by_number[number], history) for number in requirements.all_of)
        any_passed = True
        if requirements.any_of:
            any_passed = any(self._level_completed(by_number[number], history) for number in requirements.any_of)
        return all_passed and any_passed

    def _candidate_from_ref(self, level: PoolLevel, ref: PoolExerciseRef) -> CandidateExercise:
        exercise = self.catalog.load_exercise(ref.exercise_id)
        return CandidateExercise(
            exercise_id=ref.exercise_id,
            variant_id=ref.variant_id,
            level=level.level,
            title=exercise.entry.title,
            weight=ref.weight,
            order=ref.order,
            declaration_index=ref.declaration_index,
        )

    def _apply_repeat_policy(
        self,
        pool: PoolDataset,
        level: PoolLevel,
        candidates: list[CandidateExercise],
        history: list[SessionExerciseRecord],
    ) -> list[CandidateExercise]:
        repeat_policy = pool.selection.repeat_policy
        if level.max_picks is not None and self._level_seen_count(level, history) >= level.max_picks:
            return []
        if repeat_policy == "allow_review":
            return candidates
        if repeat_policy == "avoid_passed":
            passed = self._passed_candidates(history)
            return [candidate for candidate in candidates if candidate.candidate_key not in passed]
        recent = self._recent_candidates(history, pool.selection.recent_window)
        return [candidate for candidate in candidates if candidate.candidate_key not in recent]

    def resolve_candidates(
        self,
        pool_id: str,
        session_history: list[SessionExerciseRecord] | None = None,
        level: int | None = None,
        session_id: str | None = None,
    ) -> list[CandidateExercise]:
        """Resolve eligible exercises for the requested or active pool level."""
        return self.resolve_candidate_exercises(
            pool_id,
            session_history=session_history,
            level=level,
            session_id=session_id,
        )

    def resolve_candidate_exercises(
        self,
        pool_id: str,
        session_history: list[SessionExerciseRecord] | None = None,
        level: int | None = None,
        session_id: str | None = None,
    ) -> list[CandidateExercise]:
        """Resolve eligible exercises for the requested or active pool level."""
        pool = self.load_pool(pool_id)
        history = session_history if session_history is not None else self.load_session_history(session_id or "", pool_id)

        if level is not None:
            selected_level = next((item for item in pool.levels if item.level == level), None)
            if selected_level is None:
                raise LookupError(f"Unknown pool level: {level}")
            if not self._level_unlocked(pool, selected_level, history):
                return []
            candidates = [self._candidate_from_ref(selected_level, ref) for ref in selected_level.exercise_refs]
            return self._apply_repeat_policy(pool, selected_level, candidates, history)

        for selected_level in pool.levels:
            if not self._level_unlocked(pool, selected_level, history):
                continue
            candidates = [self._candidate_from_ref(selected_level, ref) for ref in selected_level.exercise_refs]
            eligible = self._apply_repeat_policy(pool, selected_level, candidates, history)
            if eligible:
                return eligible
        return []

    def _seed(self, pool: PoolDataset, session_id: str, history: list[SessionExerciseRecord]) -> random.Random:
        if pool.selection.seed_policy == "system_random":
            return random.Random()
        seed = f"{pool.pool_id}:{session_id}:{len(history)}"
        return random.Random(seed)

    def _select_candidate(
        self,
        pool: PoolDataset,
        candidates: list[CandidateExercise],
        session_id: str,
        history: list[SessionExerciseRecord],
    ) -> CandidateExercise:
        if not candidates:
            raise LookupError(f"No eligible exercises available for pool {pool.pool_id}")
        strategy = pool.selection.strategy
        if strategy == "ordered":
            return sorted(
                candidates,
                key=lambda item: (
                    item.order if item.order is not None else 10**9,
                    item.declaration_index,
                ),
            )[0]
        rng = self._seed(pool, session_id, history)
        if strategy == "weighted":
            return rng.choices(candidates, weights=[item.weight for item in candidates], k=1)[0]
        return rng.choice(candidates)

    def select_next(
        self,
        pool_id: str,
        session_id: str,
        session_history: list[SessionExerciseRecord] | None = None,
    ) -> dict:
        """Select the next exercise assignment for a session."""
        pool = self.load_pool(pool_id)
        history = session_history if session_history is not None else self.load_session_history(session_id, pool_id)
        candidates = self.resolve_candidate_exercises(pool_id, session_history=history, session_id=session_id)
        selected = self._select_candidate(pool, candidates, session_id, history)
        selected_level = next(level for level in pool.levels if level.level == selected.level)
        return {
            "pool_id": pool.pool_id,
            "session_id": session_id,
            "track": pool.entry.track,
            "exercise_id": selected.exercise_id,
            "variant_id": selected.variant_id,
            "level": selected.level,
            "selection_strategy": pool.selection.strategy,
            "repeat_policy": pool.selection.repeat_policy,
            "timing": {
                "total_time_seconds": pool.timing.total_time_seconds,
                "per_level_time_seconds": pool.timing.per_level_time_seconds,
                "effective_level_time_seconds": selected_level.time_limit_seconds or pool.timing.per_level_time_seconds,
                "cooldown": {
                    "enabled": pool.timing.cooldown_enabled,
                    "seconds": pool.timing.cooldown_seconds,
                    "scope": pool.timing.cooldown_scope,
                },
            },
            "candidate_count": len(candidates),
        }


SchedulerService = PoolEngineService
