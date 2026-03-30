"""Typed curriculum models for the canonical learner graph."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CurriculumNode:
    """One canonical curriculum node loaded from `datasets/curriculum/tree.yml`."""

    node_id: str
    title: str
    node_type: str
    track: str
    group: str
    summary: str
    prerequisites: list[str] = field(default_factory=list)
    learning_objectives: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    difficulty: int = 1
    estimated_effort: int = 0
    progression_order: int = 0
    unlock_conditions: dict[str, object] = field(default_factory=dict)
    grading_mode: str = "practice"
    expected_files: list[str] = field(default_factory=list)
    starter_files: list[str] = field(default_factory=list)
    reference_available: bool = False
    tests_available: bool = False
    status: str = "draft"
    exercise_ids: list[str] = field(default_factory=list)
    pool_ids: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.node_id,
            "title": self.title,
            "type": self.node_type,
            "track": self.track,
            "group": self.group,
            "summary": self.summary,
            "prerequisites": list(self.prerequisites),
            "learning_objectives": list(self.learning_objectives),
            "concepts": list(self.concepts),
            "difficulty": self.difficulty,
            "estimated_effort": self.estimated_effort,
            "progression_order": self.progression_order,
            "unlock_conditions": dict(self.unlock_conditions),
            "grading_mode": self.grading_mode,
            "expected_files": list(self.expected_files),
            "starter_files": list(self.starter_files),
            "reference_available": self.reference_available,
            "tests_available": self.tests_available,
            "status": self.status,
            "exercise_ids": list(self.exercise_ids),
            "pool_ids": list(self.pool_ids),
            "notices": list(self.notices),
        }


@dataclass(slots=True)
class CurriculumTree:
    """Loaded curriculum tree plus source-of-truth metadata."""

    source_of_truth: dict[str, str]
    nodes: list[CurriculumNode]

    def node_map(self) -> dict[str, CurriculumNode]:
        return {node.node_id: node for node in self.nodes}
