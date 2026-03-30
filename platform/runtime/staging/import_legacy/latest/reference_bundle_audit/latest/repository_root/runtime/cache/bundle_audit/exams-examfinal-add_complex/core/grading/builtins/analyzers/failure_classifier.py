"""Builtin failure classifier for the prototype grading engine."""

from __future__ import annotations


class FailureClassifier:
    """Classify build and runtime failures into normalized categories."""

    plugin_id = "builtin.analyzer.failure_classifier"

    def validate(self, config: dict, exercise_manifest: dict) -> list[str]:
        return []

    def classify(self, build_status: str, run_statuses: list[str], comparison_passed: bool) -> str:
        """Classify the overall attempt outcome."""
        if build_status != "success":
            return "compile_error"
        if any(status == "timeout" for status in run_statuses):
            return "timeout"
        if any(status == "crash" for status in run_statuses):
            return "crash"
        if not comparison_passed:
            return "wrong_output"
        return "none"
