from __future__ import annotations

import sys

from platform_dashboard.app import main


def test_dashboard_once_curriculum_preview(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["platform-dashboard", "--once", "/curriculum"])

    assert main() == 0
    output = capsys.readouterr().out

    assert "Nexus42 - Curriculum" in output
    assert "piscine.c00" in output
