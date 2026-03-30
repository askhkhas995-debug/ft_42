"""Canonical exam session engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import uuid

from platform_catalog import CatalogService
from platform_grading import GradingEngine
from platform_grading.contracts import AttemptContext
from platform_scheduler import PoolEngineService
from platform_storage.service import StorageService


class ExamSessionService:
    """Run file-backed exam sessions on top of canonical exam pools."""

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

    def _now(self) -> str:
        return (
            datetime.now(tz=timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def _new_session_id(self, pool_id: str) -> str:
        return f"exam.{pool_id.replace('.', '-')}.{uuid.uuid4().hex[:8]}"

    def _new_attempt_id(self, session_id: str, attempt_index: int) -> str:
        return f"{session_id}.attempt.{attempt_index:03d}"

    def _session_path(self, session_id: str) -> str:
        return f"storage/sessions/{session_id}.yml"

    def _attempt_path(self, attempt_id: str) -> str:
        return f"storage/attempts/{attempt_id}.jsonl"

    def _report_path(self, report_id: str) -> str:
        return f"runtime/reports/{report_id}.yml"

    def load_session(self, session_id: str) -> dict:
        """Load one persisted exam session."""
        return self.storage.read_yaml(self._session_path(session_id))

    def start_session(self, pool_id: str, user_id: str = "local.user") -> dict:
        """Start a canonical exam session from an exam pool."""
        pool = self.catalog.load_pool(pool_id)
        if pool.entry.track != "exams":
            raise ValueError(f"Pool {pool_id!r} is not an exam track pool.")
        if pool.entry.mode != "exam":
            raise ValueError(f"Pool {pool_id!r} is not an exam-mode pool.")

        session_id = self._new_session_id(pool_id)
        selection = self.pool_engine.select_next(pool_id, session_id, session_history=[])
        now = self._now()
        session = {
            "schema_version": 1,
            "session_id": session_id,
            "user_id": user_id,
            "mode": "exam",
            "state": "active",
            "started_at": now,
            "finished_at": None,
            "pool_id": pool_id,
            "track": pool.entry.track,
            "selection_strategy": pool.selection.strategy,
            "repeat_policy": pool.selection.repeat_policy,
            "timing": selection["timing"],
            "progress": {
                "attempts_total": 0,
                "passed_exercise_ids": [],
                "failed_attempts_total": 0,
                "current_level": selection["level"],
                "highest_unlocked_level": selection["level"],
                "completed_levels": [],
            },
            "current_assignment": {
                "exercise_id": selection["exercise_id"],
                "variant_id": selection["variant_id"],
                "level": selection["level"],
                "assigned_at": now,
                "attempt_count": 0,
                "failure_count": 0,
                "last_attempt_id": None,
                "last_report_id": None,
            },
            "cooldown": self._cooldown_payload(
                selection["timing"]["cooldown"],
                applied_at=None,
            ),
            "analytics_policy": {
                "update_on_submission": True,
                "update_on_grade": True,
            },
        }
        self._save_session(session)
        return session

    def submit_submission(self, session_id: str, submission_root: str | Path) -> dict:
        """Grade one submission and advance or retain exam state."""
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

        cooldown = self._cooldown_payload(
            session["timing"]["cooldown"],
            applied_at=report["finished_at"],
        )
        report["analytics"]["cooldown_seconds_applied"] = cooldown["seconds"] if cooldown["enabled"] else 0
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
        session["cooldown"] = cooldown

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
        """Finish a session explicitly."""
        session = self.load_session(session_id)
        if not session:
            raise FileNotFoundError(f"Unknown session id: {session_id}")
        if session["state"] == "finished":
            return session
        session["state"] = "finished"
        session["finished_at"] = self._now()
        session["current_assignment"] = None
        session["progress"]["finished_at"] = session["finished_at"]
        self._save_session(session)
        return session

    def _advance_after_success(self, session: dict, current: dict, report: dict) -> dict:
        session["progress"]["passed_exercise_ids"] = sorted(
            set(session["progress"]["passed_exercise_ids"]) | {current["exercise_id"]}
        )
        history = self.pool_engine.load_session_history(session["session_id"], session["pool_id"])
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
            default=current["level"],
        )

        try:
            selection = self.pool_engine.select_next(
                session["pool_id"],
                session["session_id"],
                session_history=history,
            )
        except LookupError:
            session["state"] = "finished"
            session["finished_at"] = report["finished_at"]
            session["progress"]["finished_at"] = report["finished_at"]
            session["progress"]["current_level"] = current["level"]
            session["current_assignment"] = None
            return session

        session["timing"] = selection["timing"]
        session["progress"]["current_level"] = selection["level"]
        session["current_assignment"] = {
            "exercise_id": selection["exercise_id"],
            "variant_id": selection["variant_id"],
            "level": selection["level"],
            "assigned_at": report["finished_at"],
            "attempt_count": 0,
            "failure_count": 0,
            "last_attempt_id": None,
            "last_report_id": None,
        }
        return session

    def _retain_after_failure(self, session: dict, current: dict, report: dict) -> dict:
        session["progress"]["failed_attempts_total"] = int(session["progress"]["failed_attempts_total"]) + 1
        session["progress"]["current_level"] = current["level"]
        current["failure_count"] = int(current["failure_count"]) + 1
        current["assigned_at"] = current["assigned_at"]
        return session

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

    def _cooldown_payload(self, cooldown: dict, applied_at: str | None) -> dict:
        enabled = bool(cooldown.get("enabled", False))
        seconds = int(cooldown.get("seconds", 0))
        scope = cooldown.get("scope", "pool")
        available_at = None
        if enabled and applied_at is not None:
            available_at = self._add_seconds(applied_at, seconds)
        return {
            "enabled": enabled,
            "scope": scope,
            "seconds": seconds,
            "last_applied_at": applied_at,
            "available_at": available_at,
        }

    def _add_seconds(self, timestamp: str, seconds: int) -> str:
        base = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        target = base + timedelta(seconds=seconds)
        return (
            target.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
