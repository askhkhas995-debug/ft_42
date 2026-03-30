"""Builtin output comparator for stdout-focused C exercises."""

from __future__ import annotations

import difflib


class OutputDiffComparator:
    """Compare expected and actual output artifacts."""

    plugin_id = "builtin.comparator.output_diff"

    def validate(self, config: dict, exercise_manifest: dict) -> list[str]:
        return []

    def compare(self, expected: str, actual: str, newline_policy: str = "exact") -> dict:
        """Compare expected and actual output under the declared newline policy."""
        normalized_expected = expected
        normalized_actual = actual
        if newline_policy == "flexible":
            normalized_expected = expected.rstrip("\n")
            normalized_actual = actual.rstrip("\n")
        elif newline_policy == "ignore":
            normalized_expected = expected.replace("\n", "")
            normalized_actual = actual.replace("\n", "")
        passed = normalized_expected == normalized_actual
        diff_lines = []
        if not passed:
            diff_lines = list(
                difflib.unified_diff(
                    normalized_expected.splitlines(),
                    normalized_actual.splitlines(),
                    fromfile="expected",
                    tofile="actual",
                    lineterm="",
                )
            )
        return {
            "passed": passed,
            "raw_score": 1.0 if passed else 0.0,
            "diff": "\n".join(diff_lines),
        }
