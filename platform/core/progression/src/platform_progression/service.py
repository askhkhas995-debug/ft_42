"""Learner-facing progression read model."""

from __future__ import annotations

from pathlib import Path

from platform_curriculum import CurriculumNode, CurriculumService
from platform_storage.service import StorageService


class ProgressionService:
    """Build learner progress snapshots from curriculum, storage, and reports."""

    def __init__(
        self,
        repository_root: Path,
        *,
        curriculum: CurriculumService | None = None,
        storage: StorageService | None = None,
    ) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.curriculum = curriculum or CurriculumService(self.repository_root)
        self.storage = storage or StorageService(self.repository_root)

    def build_snapshot(
        self, user_id: str = "local.user", *, limit: int = 10
    ) -> dict[str, object]:
        nodes = self.curriculum.load_tree().nodes
        sessions = self.session_history(user_id)
        attempt_history = self.attempt_history(user_id, limit=limit)
        report_history = self.report_history(user_id, limit=limit)
        passed_exercises = self._passed_exercises(report_history)
        completed_nodes = self._completed_nodes(nodes, passed_exercises, sessions)
        unlocked_nodes = self._unlocked_nodes(nodes, completed_nodes)
        current_node = self._resolve_current_node(
            nodes, sessions, unlocked_nodes, report_history
        )
        return {
            "user_id": user_id,
            "current_module": current_node.to_dict()
            if current_node is not None
            else None,
            "unlocked_next_nodes": [node.to_dict() for node in unlocked_nodes[:5]],
            "completed_nodes": [node.to_dict() for node in completed_nodes],
            "attempt_history": attempt_history,
            "recent_reports": report_history,
            "exam_readiness_summary": self.exam_readiness_summary(completed_nodes),
            "missing_content_notices": self.missing_content_notices(unlocked_nodes),
            "active_sessions": [
                session for session in sessions if session.get("state") == "active"
            ],
        }

    def session_history(self, user_id: str = "local.user") -> list[dict]:
        sessions_root = self.repository_root / "storage/sessions"
        if not sessions_root.exists():
            return []
        sessions: list[dict] = []
        for path in sessions_root.glob("*.yml"):
            relative = str(path.relative_to(self.repository_root))
            session = self.storage.read_yaml(relative)
            if session and session.get("user_id") == user_id:
                sessions.append(session)
        sessions.sort(
            key=lambda item: (
                item.get("updated_at") or item.get("started_at") or "",
                item.get("session_id", ""),
            ),
            reverse=True,
        )
        return sessions

    def attempt_history(
        self, user_id: str = "local.user", *, limit: int = 10
    ) -> list[dict[str, object]]:
        attempts_root = self.repository_root / "storage/attempts"
        if not attempts_root.exists():
            return []
        graded: list[dict[str, object]] = []
        for path in attempts_root.glob("*.jsonl"):
            relative = str(path.relative_to(self.repository_root))
            for record in self.storage.read_jsonl(relative):
                if record.get("user_id") != user_id or record.get("state") != "graded":
                    continue
                result = dict(record.get("result", {}))
                graded.append(
                    {
                        "attempt_id": record.get("attempt_id"),
                        "session_id": record.get("session_id"),
                        "exercise_id": record.get("exercise_id"),
                        "mode": record.get("mode"),
                        "pool_id": record.get("pool_id"),
                        "created_at": record.get("created_at"),
                        "passed": bool(result.get("passed", False)),
                        "score": result.get("normalized_score", 0.0),
                        "failure_class": result.get("failure_class", "unknown"),
                        "report_id": result.get("report_id"),
                    }
                )
        graded.sort(
            key=lambda item: (
                str(item.get("created_at", "")),
                str(item.get("attempt_id", "")),
            ),
            reverse=True,
        )
        return graded[:limit]

    def report_history(
        self, user_id: str = "local.user", *, limit: int = 10
    ) -> list[dict[str, object]]:
        reports_root = self.repository_root / "runtime/reports"
        if not reports_root.exists():
            return []
        reports: list[dict[str, object]] = []
        for path in reports_root.glob("*.yml"):
            relative = str(path.relative_to(self.repository_root))
            report = self.storage.read_yaml(relative)
            if not report or report.get("user_id") != user_id:
                continue
            evaluation = dict(report.get("evaluation", {}))
            reports.append(
                {
                    "report_id": report.get("report_id"),
                    "attempt_id": report.get("attempt_id"),
                    "session_id": report.get("session_id"),
                    "exercise_id": report.get("exercise_id"),
                    "pool_id": report.get("pool_id"),
                    "mode": report.get("mode"),
                    "finished_at": report.get("finished_at"),
                    "passed": bool(evaluation.get("passed", False)),
                    "score": evaluation.get("normalized_score", 0.0),
                    "failure_class": evaluation.get("failure_class", "unknown"),
                    "summary": dict(report.get("feedback", {})).get("summary", ""),
                }
            )
        reports.sort(
            key=lambda item: (
                str(item.get("finished_at", "")),
                str(item.get("report_id", "")),
            ),
            reverse=True,
        )
        return reports[:limit]

    def exam_readiness_summary(
        self, completed_nodes: list[CurriculumNode]
    ) -> list[dict[str, object]]:
        completed_ids = {node.node_id for node in completed_nodes}
        summary: list[dict[str, object]] = []
        for node in self.curriculum.list_nodes(track="exams"):
            blockers = []
            missing_prereqs = [
                item for item in node.prerequisites if item not in completed_ids
            ]
            if missing_prereqs:
                blockers.append(f"missing prerequisites: {', '.join(missing_prereqs)}")
            if node.status != "ready":
                blockers.append(f"canonical status is {node.status}")
            if not node.pool_ids:
                blockers.append("no canonical exam pool is linked yet")
            summary.append(
                {
                    "node_id": node.node_id,
                    "title": node.title,
                    "ready": len(blockers) == 0,
                    "pool_ids": list(node.pool_ids),
                    "blockers": blockers,
                }
            )
        return summary

    def missing_content_notices(
        self, unlocked_nodes: list[CurriculumNode]
    ) -> list[str]:
        notices: list[str] = []
        for node in unlocked_nodes:
            if node.status != "ready":
                notices.append(f"{node.node_id}: status is {node.status}")
            if not node.reference_available:
                notices.append(
                    f"{node.node_id}: reference solution is not canonical yet"
                )
            if not node.tests_available:
                notices.append(f"{node.node_id}: tests are not canonical yet")
            for note in node.notices:
                notices.append(f"{node.node_id}: {note}")
        return notices[:10]

    def _passed_exercises(self, reports: list[dict[str, object]]) -> set[str]:
        return {
            str(report["exercise_id"]) for report in reports if report.get("passed")
        }

    def _completed_nodes(
        self,
        nodes: list[CurriculumNode],
        passed_exercises: set[str],
        sessions: list[dict],
    ) -> list[CurriculumNode]:
        completed: list[CurriculumNode] = []
        finished_pools = {
            str(session.get("pool_id"))
            for session in sessions
            if session.get("state") in {"completed", "finished"}
        }
        for node in nodes:
            exercise_complete = bool(node.exercise_ids) and all(
                item in passed_exercises for item in node.exercise_ids
            )
            pool_complete = bool(node.pool_ids) and any(
                pool_id in finished_pools for pool_id in node.pool_ids
            )
            if exercise_complete or pool_complete:
                completed.append(node)
        completed.sort(key=lambda item: (item.progression_order, item.node_id))
        return completed

    def _unlocked_nodes(
        self, nodes: list[CurriculumNode], completed_nodes: list[CurriculumNode]
    ) -> list[CurriculumNode]:
        completed_ids = {node.node_id for node in completed_nodes}
        unlocked = [
            node
            for node in nodes
            if node.node_id not in completed_ids
            and all(dep in completed_ids for dep in node.prerequisites)
        ]
        unlocked.sort(key=lambda item: (item.progression_order, item.node_id))
        return unlocked

    def _resolve_current_node(
        self,
        nodes: list[CurriculumNode],
        sessions: list[dict],
        unlocked_nodes: list[CurriculumNode],
        reports: list[dict[str, object]],
    ) -> CurriculumNode | None:
        node_by_pool = {pool_id: node for node in nodes for pool_id in node.pool_ids}
        node_by_exercise = {
            exercise_id: node for node in nodes for exercise_id in node.exercise_ids
        }
        for session in sessions:
            if session.get("state") != "active":
                continue
            pool_id = str(session.get("pool_id") or "")
            current = dict(session.get("current_assignment") or {})
            exercise_id = str(current.get("exercise_id") or "")
            if pool_id in node_by_pool:
                return node_by_pool[pool_id]
            if exercise_id in node_by_exercise:
                return node_by_exercise[exercise_id]
        if unlocked_nodes:
            return unlocked_nodes[0]
        for report in reports:
            exercise_id = str(report.get("exercise_id") or "")
            if exercise_id in node_by_exercise:
                return node_by_exercise[exercise_id]
        return None
