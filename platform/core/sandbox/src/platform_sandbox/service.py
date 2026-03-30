"""Sandbox service for compile and runtime subprocess isolation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import time

import resource
import yaml


@dataclass(slots=True)
class CommandResult:
    """Result of a compile or run subprocess inside the sandbox."""

    status: str
    command: list[str]
    exit_code: int
    stdout_path: str
    stderr_path: str
    duration_ms: int
    timed_out: bool = False
    signal: str = ""
    memory_limit_hit: bool = False


@dataclass(slots=True)
class SandboxContext:
    """Prepared workspace and artifact directories for an attempt."""

    attempt_id: str
    workspace_root: Path
    submission_root: Path
    build_root: Path
    artifact_root: Path


@dataclass(slots=True)
class SandboxService:
    """Prepare isolated compile and runtime environments."""

    repository_root: Path

    def _profile_path(self, profile_id: str) -> Path:
        profile_name = profile_id.removeprefix("sandbox.").replace(".", "-")
        if not profile_name.endswith(".yml"):
            profile_name += ".yml"
        return self.repository_root / "core/sandbox/profiles" / profile_name

    def load_profile(self, profile_id: str) -> dict:
        """Load a sandbox profile YAML file."""
        profile_path = self._profile_path(profile_id)
        with profile_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def prepare(self, attempt_id: str, profile_id: str) -> SandboxContext:
        """Prepare a clean workspace for the given attempt."""
        workspace_root = self.repository_root / "runtime/workspaces" / attempt_id
        build_root = workspace_root / "build"
        submission_root = workspace_root / "submission"
        artifact_root = self.repository_root / "runtime/traces" / attempt_id
        if workspace_root.exists():
            shutil.rmtree(workspace_root)
        if artifact_root.exists():
            shutil.rmtree(artifact_root)
        build_root.mkdir(parents=True, exist_ok=True)
        submission_root.mkdir(parents=True, exist_ok=True)
        artifact_root.mkdir(parents=True, exist_ok=True)
        return SandboxContext(
            attempt_id=attempt_id,
            workspace_root=workspace_root,
            submission_root=submission_root,
            build_root=build_root,
            artifact_root=artifact_root,
        )

    def copy_submission(self, source_root: Path, destination_root: Path, expected_files: list[str]) -> list[Path]:
        """Copy expected files from a submission into the isolated workspace."""
        copied: list[Path] = []
        destination_root.mkdir(parents=True, exist_ok=True)
        for relative_name in expected_files:
            source_path = source_root / relative_name
            if not source_path.exists():
                raise FileNotFoundError(f"Expected submission file missing: {source_path}")
            target_path = destination_root / relative_name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            copied.append(target_path)
        return copied

    def run_command(
        self,
        command: list[str],
        cwd: Path,
        stdout_path: Path,
        stderr_path: Path,
        timeout_seconds: int,
        memory_limit_mb: int,
        stdin_text: str = "",
    ) -> CommandResult:
        """Run a command with timeout and memory limits."""
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        def limit_resources() -> None:
            memory_bytes = memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

        started = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                input=stdin_text,
                text=True,
                timeout=timeout_seconds,
                check=False,
                preexec_fn=limit_resources,
                env={"PATH": "/usr/bin:/bin"},
            )
            stdout_path.write_text(completed.stdout, encoding="utf-8")
            stderr_path.write_text(completed.stderr, encoding="utf-8")
            duration_ms = int((time.perf_counter() - started) * 1000)
            signal = ""
            if completed.returncode < 0:
                signal = str(-completed.returncode)
            return CommandResult(
                status="success" if completed.returncode == 0 else "failure",
                command=command,
                exit_code=completed.returncode,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                duration_ms=duration_ms,
                signal=signal,
            )
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text(exc.stderr or "", encoding="utf-8")
            duration_ms = int((time.perf_counter() - started) * 1000)
            return CommandResult(
                status="timeout",
                command=command,
                exit_code=124,
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
                duration_ms=duration_ms,
                timed_out=True,
            )
