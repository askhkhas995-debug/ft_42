"""Canonical piscine session engine."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path
import uuid

from platform_catalog import CatalogService
from platform_grading import GradingEngine
from platform_grading.contracts import AttemptContext
from platform_scheduler import PoolEngineService
from platform_storage.service import StorageService


SUPPORTED_PISCINE_GROUPS = (
    "shell00",
    "shell01",
    "c00",
    "c01",
    "c02",
    "c03",
    "c04",
    "c05",
    "c06",
    "c07",
    "c08",
    "c09",
    "c10",
    "c11",
    "c12",
    "c13",
)


class PiscineSessionService:
    """Run file-backed piscine sessions on top of canonical piscine pools."""

    def __init__(
        self,
        repository_root: Path,
        *,
        catalog: CatalogService | None = None,
        pool_engine: PoolEngineService | None = None,
        grading_engine: GradingEngine | None = None,
        storage: StorageService | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.catalog = catalog or CatalogService(self.repository_root)
        self.pool_engine = pool_engine or PoolEngineService(self.repository_root)
        self.grading_engine = grading_engine or GradingEngine(self.repository_root)
        self.storage = storage or StorageService(self.repository_root)

    def supported_groups(self) -> tuple[str, ...]:
        """Return the piscine curriculum groups supported by this service contract."""
        return SUPPORTED_PISCINE_GROUPS

    def _now(self) -> str:
        return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _new_session_id(self, pool_id: str) -> str:
        return f"piscine.{pool_id.replace('.', '-')}.{uuid.uuid4().hex[:8]}"

    def _new_attempt_id(self, session_id: str, attempt_index: int) -> str:
        return f"{session_id}.attempt.{attempt_index:03d}"

    def _session_path(self, session_id: str) -> str:
        return f"storage/sessions/{session_id}.yml"

    def _attempt_path(self, attempt_id: str) -> str:
        return f"storage/attempts/{attempt_id}.jsonl"

    def _report_path(self, report_id: str) -> str:
        return f"runtime/reports/{report_id}.yml"

    def load_session(self, session_id: str) -> dict:
        """Load one persisted piscine session."""
        return self.storage.read_yaml(self._session_path(session_id))

    def load_or_start(
        self,
        pool_id: str,
        *,
        user_id: str = "local.user",
        level: int | None = None,
    ) -> dict:
        """Load an active piscine session for this user/pool or start one."""
        existing = self._find_active_session(pool_id, user_id)
        if existing is not None:
            return self._resume_existing_session(existing["session_id"])
        return self.start_session(pool_id, user_id=user_id, level=level)

    def start_track(self, pool_id: str, user_id: str = "local.user") -> dict:
        """Start or load a piscine track session."""
        return self.load_or_start(pool_id, user_id=user_id)

    def start_level(self, pool_id: str, *, level: int, user_id: str = "local.user") -> dict:
        """Start a piscine session pinned to a requested level."""
        return self.start_session(pool_id, user_id=user_id, level=level)

    def start_session(self, pool_id: str, user_id: str = "local.user", level: int | None = None) -> dict:
        """Start a canonical piscine session from a piscine pool."""
        pool = self.catalog.load_pool(pool_id)
        self._validate_pool_contract(pool_id, pool)

        session_id = self._new_session_id(pool_id)
        selection = self._select_next_assignment(pool_id, session_id, history=[], level=level)
        now = self._now()
        session = {
            "schema_version": 1,
            "session_id": session_id,
            "user_id": user_id,
            "mode": "piscine",
            "state": "active",
            "started_at": now,
            "updated_at": now,
            "finished_at": None,
            "pool_id": pool_id,
            "track": pool.entry.track,
            "selection_strategy": pool.selection.strategy,
            "repeat_policy": pool.selection.repeat_policy,
            "timing": selection["timing"],
            "progress": {
                "attempts_total": 0,
                "completed_exercise_ids": [],
                "passed_exercise_ids": [],
                "failed_attempts_total": 0,
                "current_level": selection["level"],
                "highest_unlocked_level": selection["level"],
                "completed_levels": [],
                "available_exercise_ids": self._available_exercise_ids(pool_id, session_id, history=[]),
                "last_completed_exercise_id": None,
                "completion_ratio": 0.0,
                "finished_at": None,
            },
            "current_assignment": self._assignment_payload(selection, assigned_at=now),
            "resume_policy": {
                "reuse_active_session": True,
                "resume_current_assignment_first": True,
            },
            "analytics_policy": {
                "update_on_submission": True,
                "update_on_grade": True,
            },
        }
        self._save_session(session)
        return session

    def select_next(self, session_id: str) -> dict:
        """Resolve and persist the next piscine assignment for an active session."""
        session = self.load_session(session_id)
        if not session:
            raise FileNotFoundError(f"Unknown session id: {session_id}")
        if session["state"] == "finished":
            raise ValueError(f"Session {session_id!r} is not selectable.")
        if session["state"] == "completed":
            raise LookupError(f"Session {session_id!r} has no eligible next exercise.")
        resumed = self._resume_existing_session(session_id)
        current = resumed.get("current_assignment")
        if current is None:
            raise LookupError(f"Session {session_id!r} has no eligible next exercise.")
        return current

    def submit_submission(self, session_id: str, submission_root: str | Path) -> dict:
        """Grade one submission and advance piscine progression state."""
        session = self.load_session(session_id)
        if not session:
            raise FileNotFoundError(f"Unknown session id: {session_id}")
        if session["state"] != "active":
            raise ValueError(f"Session {session_id!r} is not active.")
        current = session.get("current_assignment")
        if not current:
            raise ValueError(f"Session {session_id!r} has no active assignment.")

        exercise = self.catalog.load_exercise(current["exercise_id"])
        attempt_index_for_session = int(session["progress"]["attempts_total"]) + 1
        attempt_index_for_exercise = int(current["attempt_count"]) + 1
        attempt_id = self._new_attempt_id(session_id, attempt_index_for_session)
        now = self._now()

        attempt_opened = {
            "schema_version": 1,
            "attempt_id": attempt_id,
            "session_id": session_id,
            "user_id": session["user_id"],
            "exercise_id": current["exercise_id"],
            "variant_id": current["variant_id"],
            "mode": session["mode"],
            "pool_id": session["pool_id"],
            "attempt_index_for_session": attempt_index_for_session,
            "attempt_index_for_exercise": attempt_index_for_exercise,
            "created_at": now,
            "state": "opened",
            "workspace": self._workspace_payload(attempt_id, Path(submission_root), exercise.expected_files),
            "timing": {
                "active_seconds": 0,
                "idle_seconds": 0,
                "focus_blocks": [],
            },
            "result": {},
            "notes": {
                "level": current["level"],
            },
        }
        self.storage.append_jsonl(self._attempt_path(attempt_id), attempt_opened)

        report = self.grading_engine.grade_submission(
            AttemptContext(
                attempt_id=attempt_id,
                session_id=session_id,
                user_id=session["user_id"],
                exercise_id=current["exercise_id"],
                variant_id=current["variant_id"],
                mode=session["mode"],
                pool_id=session["pool_id"],
                submission_root=Path(submission_root),
                attempt_index_for_exercise=attempt_index_for_exercise,
            )
        )
        report["artifacts"]["report_path"] = self._report_path(report["report_id"])
        self.storage.write_yaml(report["artifacts"]["report_path"], report)

        attempt_graded = {
            **attempt_opened,
            "state": "graded",
            "result": {
                "passed": bool(report["evaluation"]["passed"]),
                "failure_class": report["evaluation"]["failure_class"],
                "normalized_score": report["evaluation"]["normalized_score"],
                "report_id": report["report_id"],
            },
            "notes": {
                "level": current["level"],
                "report_path": report["artifacts"]["report_path"],
            },
        }
        self.storage.append_jsonl(self._attempt_path(attempt_id), attempt_graded)

        session["progress"]["attempts_total"] = attempt_index_for_session
        current["attempt_count"] = attempt_index_for_exercise
        current["last_attempt_id"] = attempt_id
        current["last_report_id"] = report["report_id"]
        session["updated_at"] = report["finished_at"]

        if report["evaluation"]["passed"]:
            next_session = self._advance_after_success(session, current, report)
        else:
            next_session = self._retain_after_failure(session, current, report)

        self._save_session(next_session)
        return {
            "session": next_session,
            "attempt_id": attempt_id,
            "report_id": report["report_id"],
            "passed": bool(report["evaluation"]["passed"]),
        }

    def finish_session(self, session_id: str) -> dict:
        """Finish a piscine session explicitly."""
        session = self.load_session(session_id)
        if not session:
            raise FileNotFoundError(f"Unknown session id: {session_id}")
        if session["state"] == "finished":
            return session
        session["state"] = "finished"
        session["finished_at"] = self._now()
        session["updated_at"] = session["finished_at"]
        session["current_assignment"] = None
        session["progress"]["finished_at"] = session["progress"].get("finished_at") or session["finished_at"]
        self._save_session(session)
        return session

    def exercise_learning_hooks(self, exercise_id: str) -> dict:
        """Return optional beginner-learning hooks for a piscine exercise."""
        exercise = self.catalog.load_exercise(exercise_id)
        return dict(exercise.manifest.get("learning", {}))

    def _validate_pool_contract(self, pool_id: str, pool) -> None:
        if pool.entry.track != "piscine":
            raise ValueError(f"Pool {pool_id!r} is not a piscine track pool.")
        if pool.entry.mode != "practice":
            raise ValueError(f"Pool {pool_id!r} is not a piscine practice pool.")
        segments = pool_id.split(".")
        if len(segments) < 2 or segments[1] not in SUPPORTED_PISCINE_GROUPS:
            supported = ", ".join(SUPPORTED_PISCINE_GROUPS)
            raise ValueError(f"Pool {pool_id!r} is outside the supported piscine groups: {supported}")

    def _find_active_session(self, pool_id: str, user_id: str) -> dict | None:
        sessions_root = self.repository_root / "storage/sessions"
        if not sessions_root.exists():
            return None
        candidates: list[dict] = []
        for path in sessions_root.glob("*.yml"):
            try:
                session = self.storage.read_yaml(str(path.relative_to(self.repository_root)))
            except FileNotFoundError:
                continue
            if not session:
                continue
            if session.get("mode") != "piscine":
                continue
            if session.get("pool_id") != pool_id or session.get("user_id") != user_id:
                continue
            if session.get("state") != "active":
                continue
            candidates.append(session)
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item.get("updated_at", ""), item["session_id"]), reverse=True)
        return candidates[0]

    def _resume_existing_session(self, session_id: str) -> dict:
        session = self.load_session(session_id)
        if not session:
            raise FileNotFoundError(f"Unknown session id: {session_id}")
        if session["state"] != "active":
            return session
        current = session.get("current_assignment")
        completed = set(session["progress"].get("completed_exercise_ids", []))
        if current and current.get("exercise_id") not in completed:
            return session

        history = self.pool_engine.load_session_history(session_id, session["pool_id"])
        try:
            selection = self._select_next_assignment(session["pool_id"], session_id, history=history)
        except LookupError:
            completed_at = session["progress"].get("finished_at") or self._now()
            session["state"] = "completed"
            session["current_assignment"] = None
            session["finished_at"] = None
            session["updated_at"] = completed_at
            session["progress"]["finished_at"] = completed_at
            session["progress"]["available_exercise_ids"] = []
            session["progress"]["completion_ratio"] = self._completion_ratio(
                session["pool_id"],
                session["progress"]["completed_exercise_ids"],
            )
            self._save_session(session)
            return session

        session["timing"] = selection["timing"]
        session["current_assignment"] = self._assignment_payload(selection, assigned_at=self._now())
        session["finished_at"] = None
        self._update_progress_state(session, history)
        self._save_session(session)
        return session

    def _select_next_assignment(
        self,
        pool_id: str,
        session_id: str,
        *,
        history: list | None = None,
        level: int | None = None,
    ) -> dict:
        if level is not None:
            candidates = self.pool_engine.resolve_candidate_exercises(
                pool_id,
                session_history=history or [],
                session_id=session_id,
                level=level,
            )
            pool = self.pool_engine.load_pool(pool_id)
            selected = self.pool_engine._select_candidate(pool, candidates, session_id, history or [])
            selected_level = next(item for item in pool.levels if item.level == selected.level)
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
        return self.pool_engine.select_next(pool_id, session_id, session_history=history or [])

    def _assignment_payload(self, selection: dict, *, assigned_at: str) -> dict:
        return {
            "exercise_id": selection["exercise_id"],
            "variant_id": selection["variant_id"],
            "level": selection["level"],
            "assigned_at": assigned_at,
            "attempt_count": 0,
            "failure_count": 0,
            "last_attempt_id": None,
            "last_report_id": None,
            "status": "active",
        }

    def _advance_after_success(self, session: dict, current: dict, report: dict) -> dict:
        completed = sorted(set(session["progress"]["completed_exercise_ids"]) | {current["exercise_id"]})
        passed = sorted(set(session["progress"]["passed_exercise_ids"]) | {current["exercise_id"]})
        session["progress"]["completed_exercise_ids"] = completed
        session["progress"]["passed_exercise_ids"] = passed
        session["progress"]["last_completed_exercise_id"] = current["exercise_id"]
        current["status"] = "completed"

        history = self.pool_engine.load_session_history(session["session_id"], session["pool_id"])
        self._update_progress_state(session, history)

        try:
            selection = self._select_next_assignment(session["pool_id"], session["session_id"], history=history)
        except LookupError:
            session["state"] = "completed"
            session["updated_at"] = report["finished_at"]
            session["progress"]["finished_at"] = report["finished_at"]
            session["current_assignment"] = None
            session["finished_at"] = None
            session["progress"]["completion_ratio"] = self._completion_ratio(
                session["pool_id"],
                completed,
            )
            session["progress"]["available_exercise_ids"] = []
            return session

        session["timing"] = selection["timing"]
        session["current_assignment"] = self._assignment_payload(selection, assigned_at=report["finished_at"])
        session["state"] = "active"
        session["finished_at"] = None
        session["progress"]["finished_at"] = None
        session["updated_at"] = report["finished_at"]
        return session

    def _retain_after_failure(self, session: dict, current: dict, report: dict) -> dict:
        session["progress"]["failed_attempts_total"] = int(session["progress"]["failed_attempts_total"]) + 1
        session["progress"]["current_level"] = current["level"]
        current["failure_count"] = int(current["failure_count"]) + 1
        current["status"] = "retrying"
        session["updated_at"] = report["finished_at"]
        return session

    def _update_progress_state(self, session: dict, history: list) -> None:
        pool = self.pool_engine.load_pool(session["pool_id"])
        session["progress"]["completed_levels"] = [
            level.level for level in pool.levels if self.pool_engine._level_completed(level, history)
        ]
        session["progress"]["highest_unlocked_level"] = max(
            (
                level.level
                for level in pool.levels
                if self.pool_engine._level_unlocked(pool, level, history)
            ),
            default=session["progress"].get("current_level", 0),
        )
        current = session.get("current_assignment")
        if current is not None:
            session["progress"]["current_level"] = current["level"]
        session["progress"]["available_exercise_ids"] = self._available_exercise_ids(
            session["pool_id"],
            session["session_id"],
            history=history,
        )
        session["progress"]["completion_ratio"] = self._completion_ratio(
            session["pool_id"],
            session["progress"]["completed_exercise_ids"],
        )

    def _available_exercise_ids(self, pool_id: str, session_id: str, history: list | None = None) -> list[str]:
        candidates = self.pool_engine.resolve_candidate_exercises(
            pool_id,
            session_history=history or [],
            session_id=session_id,
        )
        return sorted({item.exercise_id for item in candidates})

    def _completion_ratio(self, pool_id: str, completed_exercise_ids: list[str]) -> float:
        pool = self.pool_engine.load_pool(pool_id)
        all_exercises = {
            ref.exercise_id
            for level in pool.levels
            for ref in level.exercise_refs
        }
        if not all_exercises:
            return 0.0
        done = len(all_exercises & set(completed_exercise_ids))
        return round(done / len(all_exercises), 4)

    def _workspace_payload(self, attempt_id: str, submission_root: Path, expected_files: list[str]) -> dict:
        resolved_submission_root = submission_root.resolve()
        submitted_files = [name for name in expected_files if (resolved_submission_root / name).exists()]
        return {
            "root_path": f"runtime/workspaces/{attempt_id}",
            "submitted_files": submitted_files,
            "file_hashes": [
                {
                    "path": name,
                    "sha256": self._sha256(resolved_submission_root / name),
                }
                for name in submitted_files
            ],
        }

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(path.read_bytes())
        return digest.hexdigest()

    def _save_session(self, session: dict) -> None:
        self.storage.write_yaml(self._session_path(session["session_id"]), session)
