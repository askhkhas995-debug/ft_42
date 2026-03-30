"""Canonical curriculum service."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import CurriculumNode, CurriculumTree


class CurriculumService:
    """Load and query the canonical learner curriculum graph."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = Path(repository_root).resolve()
        self._tree: CurriculumTree | None = None

    @property
    def curriculum_path(self) -> Path:
        return self.repository_root / "datasets/curriculum/tree.yml"

    def load_tree(self, *, refresh: bool = False) -> CurriculumTree:
        if self._tree is not None and not refresh:
            return self._tree
        payload = yaml.safe_load(self.curriculum_path.read_text(encoding="utf-8")) or {}
        nodes_payload = payload.get("nodes", [])
        nodes = [self._load_node(item) for item in nodes_payload]
        nodes.sort(key=lambda item: (item.progression_order, item.node_id))
        self._tree = CurriculumTree(
            source_of_truth=dict(payload.get("source_of_truth", {})),
            nodes=nodes,
        )
        return self._tree

    def list_nodes(
        self,
        *,
        track: str | None = None,
        status: str | None = None,
        node_type: str | None = None,
    ) -> list[CurriculumNode]:
        nodes = self.load_tree().nodes
        if track is not None:
            nodes = [node for node in nodes if node.track == track]
        if status is not None:
            nodes = [node for node in nodes if node.status == status]
        if node_type is not None:
            nodes = [node for node in nodes if node.node_type == node_type]
        return nodes

    def get_node(self, node_id: str) -> CurriculumNode:
        tree = self.load_tree()
        node = tree.node_map().get(node_id)
        if node is None:
            raise KeyError(f"Unknown curriculum node: {node_id}")
        return node

    def grouped_nodes(self) -> dict[str, list[CurriculumNode]]:
        groups = {
            "piscine": [],
            "rushes": [],
            "exams": [],
        }
        for node in self.load_tree().nodes:
            if node.track == "piscine":
                groups["piscine"].append(node)
            elif node.track == "exams":
                groups["exams"].append(node)
            else:
                groups["rushes"].append(node)
        return groups

    def source_of_truth_summary(self) -> dict[str, str]:
        return dict(self.load_tree().source_of_truth)

    def _load_node(self, payload: dict[str, object]) -> CurriculumNode:
        return CurriculumNode(
            node_id=str(payload["id"]),
            title=str(payload["title"]),
            node_type=str(payload["type"]),
            track=str(payload["track"]),
            group=str(payload["group"]),
            summary=str(payload.get("summary", "")),
            prerequisites=[str(item) for item in payload.get("prerequisites", [])],
            learning_objectives=[
                str(item) for item in payload.get("learning_objectives", [])
            ],
            concepts=[str(item) for item in payload.get("concepts", [])],
            difficulty=int(payload.get("difficulty", 1)),
            estimated_effort=int(payload.get("estimated_effort", 0)),
            progression_order=int(payload.get("progression_order", 0)),
            unlock_conditions=dict(payload.get("unlock_conditions", {})),
            grading_mode=str(payload.get("grading_mode", "practice")),
            expected_files=[str(item) for item in payload.get("expected_files", [])],
            starter_files=[str(item) for item in payload.get("starter_files", [])],
            reference_available=bool(payload.get("reference_available", False)),
            tests_available=bool(payload.get("tests_available", False)),
            status=str(payload.get("status", "draft")),
            exercise_ids=[str(item) for item in payload.get("exercise_ids", [])],
            pool_ids=[str(item) for item in payload.get("pool_ids", [])],
            notices=[str(item) for item in payload.get("notices", [])],
        )
