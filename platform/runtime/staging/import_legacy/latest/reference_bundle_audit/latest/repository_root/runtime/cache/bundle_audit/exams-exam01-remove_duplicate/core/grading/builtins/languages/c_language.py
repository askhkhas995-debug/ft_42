"""Builtin C language plugin for the prototype grading engine."""

from __future__ import annotations

from pathlib import Path


class CLanguagePlugin:
    """Compile and run C code under the sandbox contract."""

    plugin_id = "builtin.language.c"

    def validate(self, config: dict, exercise_manifest: dict) -> list[str]:
        errors: list[str] = []
        build = exercise_manifest.get("build", {})
        if build.get("compiler") not in {"gcc", "clang"}:
            errors.append("Unsupported compiler for prototype C language plugin.")
        if exercise_manifest.get("language") != "c":
            errors.append("C language plugin only supports language='c'.")
        return errors

    def harness_path(self, exercise_root: Path, manifest: dict) -> Path:
        """Resolve the harness source for a function-with-harness exercise."""
        tests_dir = manifest["files"]["tests_dir"]
        harness = exercise_root / tests_dir / "main.c"
        if harness.exists():
            return harness
        raise FileNotFoundError(f"Missing C harness: {harness}")

    def source_paths(self, root: Path, filenames: list[str]) -> list[Path]:
        """Resolve declared source files from a root directory."""
        paths = [root / name for name in filenames]
        missing = [str(path) for path in paths if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Missing source files: {', '.join(missing)}")
        return paths

    def compile_command(
        self,
        manifest: dict,
        source_files: list[Path],
        harness_path: Path | None,
        output_path: Path,
    ) -> list[str]:
        """Create a compile command from the manifest contract."""
        build = manifest["build"]
        command = [build["compiler"], f"-std={build['standard']}"]
        command.extend(build.get("flags", []))
        command.extend(str(path) for path in source_files)
        if harness_path is not None:
            command.append(str(harness_path))
        command.extend(build.get("link_flags", []))
        command.extend(["-o", str(output_path)])
        return command
