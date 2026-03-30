from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

from platform_catalog import CatalogService
from platform_cli.main import SESSION_FILE_NAME, main


PLATFORM_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(monkeypatch, capsys, *args: str) -> str:
    monkeypatch.setattr(sys, "argv", ["grademe", *args])
    assert main() == 0
    return capsys.readouterr().out


def test_curriculum_command_renders_modules(monkeypatch, capsys) -> None:
    output = _run_cli(monkeypatch, capsys, "curriculum")

    assert "Curriculum" in output
    assert "piscine.c00" in output
    assert "exams.exam00" in output


def test_practice_start_and_submit_smoke(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "practice"
    output = _run_cli(
        monkeypatch,
        capsys,
        "start",
        "--exercise-id",
        "piscine.c00.ft_putchar",
        "--workspace",
        str(workspace),
    )

    assert "Exercise Ready" in output
    session = yaml.safe_load(
        (workspace / SESSION_FILE_NAME).read_text(encoding="utf-8")
    )
    exercise = CatalogService(PLATFORM_ROOT).load_exercise(session["exercise_id"])
    shutil.copy2(exercise.reference_dir / "ft_putchar.c", workspace / "ft_putchar.c")

    output = _run_cli(monkeypatch, capsys, "submit", str(workspace))

    assert "Status: PASS" in output


def test_exam_start_and_submit_smoke(tmp_path: Path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "exam"
    output = _run_cli(
        monkeypatch, capsys, "exam", "start", "--workspace", str(workspace)
    )

    assert "Exam Started" in output
    session = yaml.safe_load(
        (workspace / SESSION_FILE_NAME).read_text(encoding="utf-8")
    )
    exercise = CatalogService(PLATFORM_ROOT).load_exercise(session["exercise_id"])
    for name in exercise.expected_files:
        shutil.copy2(exercise.reference_dir / name, workspace / name)

    output = _run_cli(monkeypatch, capsys, "exam", "submit", str(workspace))

    assert "Exam Submission" in output
    assert "Status: PASS" in output
