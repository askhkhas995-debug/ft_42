from __future__ import annotations

from pathlib import Path

from platform_curriculum import CurriculumService


PLATFORM_ROOT = Path(__file__).resolve().parents[1]


def test_curriculum_tree_loads_and_links_ready_content() -> None:
    service = CurriculumService(PLATFORM_ROOT)

    tree = service.load_tree(refresh=True)
    c00 = service.get_node("piscine.c00")
    exam01 = service.get_node("exams.exam01")

    assert tree.source_of_truth["curriculum"] == "datasets/curriculum"
    assert c00.status == "ready"
    assert "piscine.c00.ft_putchar" in c00.exercise_ids
    assert "piscine.c00.foundations" in c00.pool_ids
    assert exam01.status == "draft"
