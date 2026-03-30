from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

for relative in (
    "apps/cli/src",
    "apps/dashboard/src",
    "core/catalog/src",
    "core/curriculum/src",
    "core/exams/src",
    "core/grading/src",
    "core/progression/src",
    "core/sandbox/src",
    "core/scheduler/src",
    "core/sessions/src",
    "core/storage/src",
    "tooling",
):
    path = str(ROOT / relative)
    if path not in sys.path:
        sys.path.insert(0, path)


def pytest_collection_modifyitems(config, items) -> None:
    if os.environ.get("NEXUS42_RUN_HEAVY_TESTS") == "1":
        return

    skip_heavy = pytest.mark.skip(
        reason="disabled by default for the minimal stable test run; set NEXUS42_RUN_HEAVY_TESTS=1 to enable"
    )
    heavy_nodeids = {
        "tests/test_exam_integration_curated.py::test_curated_exam_integration_real_staged_data",
    }
    for item in items:
        if item.nodeid in heavy_nodeids:
            item.add_marker(skip_heavy)
