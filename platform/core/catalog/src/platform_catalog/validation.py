"""Strict exercise dataset validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_catalog.models import CatalogFile, ExerciseTestCase, SUPPORTED_TRACKS


ALLOWED_NEWLINE_POLICIES = {"exact", "flexible", "ignore"}
ALLOWED_OUTPUT_CHANNELS = {"stdout", "stderr"}
ALLOWED_COMPILERS = {"gcc", "clang"}
ALLOWED_COMPILE_MODES = {"function_with_harness", "standalone_program"}
ALLOWED_PASS_POLICY_MODES = {"all_tests", "threshold"}
ALLOWED_VARIANT_KINDS = {"normal", "prediction_prompt", "completion", "bug_injection"}


@dataclass(slots=True)
class CatalogValidationFailure:
    """One strict validation failure."""

    location: str
    message: str

    def render(self) -> str:
        return f"{self.location}: {self.message}"


class CatalogValidationError(ValueError):
    """Raised when an exercise bundle violates the catalog contract."""

    def __init__(self, failures: list[CatalogValidationFailure]) -> None:
        self.failures = failures
        super().__init__("\n".join(failure.render() for failure in failures))


def _fail(failures: list[CatalogValidationFailure], location: str, message: str) -> None:
    failures.append(CatalogValidationFailure(location=location, message=message))


def _expect_mapping(
    value: object,
    *,
    location: str,
    failures: list[CatalogValidationFailure],
    required: set[str] | None = None,
    optional: set[str] | None = None,
) -> dict:
    if not isinstance(value, dict):
        _fail(failures, location, "expected mapping")
        return {}
    required = required or set()
    optional = optional or set()
    allowed = required | optional
    for key in required:
        if key not in value:
            _fail(failures, f"{location}.{key}", "missing required key")
    for key in value:
        if key not in allowed:
            _fail(failures, f"{location}.{key}", "unexpected key")
    return value


def _expect_list(value: object, *, location: str, failures: list[CatalogValidationFailure]) -> list:
    if not isinstance(value, list):
        _fail(failures, location, "expected list")
        return []
    return value


def _expect_str(value: object, *, location: str, failures: list[CatalogValidationFailure], allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        _fail(failures, location, "expected string")
        return ""
    if not allow_empty and not value.strip():
        _fail(failures, location, "expected non-empty string")
    return value


def _expect_int(value: object, *, location: str, failures: list[CatalogValidationFailure]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(failures, location, "expected integer")
        return 0
    return value


def _expect_bool(value: object, *, location: str, failures: list[CatalogValidationFailure]) -> bool:
    if not isinstance(value, bool):
        _fail(failures, location, "expected boolean")
        return False
    return value


def _expect_number(value: object, *, location: str, failures: list[CatalogValidationFailure]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(failures, location, "expected number")
        return 0.0
    return float(value)


def _expect_string_list(
    value: object,
    *,
    location: str,
    failures: list[CatalogValidationFailure],
    allow_empty_items: bool = False,
) -> list[str]:
    items = _expect_list(value, location=location, failures=failures)
    normalized: list[str] = []
    for index, item in enumerate(items):
        normalized.append(
            _expect_str(
                item,
                location=f"{location}[{index}]",
                failures=failures,
                allow_empty=allow_empty_items,
            )
        )
    return normalized


def _expect_optional_int(
    value: object,
    *,
    location: str,
    failures: list[CatalogValidationFailure],
) -> int | None:
    if value is None:
        return None
    return _expect_int(value, location=location, failures=failures)


def _validate_relative_path(path_value: str, *, location: str, failures: list[CatalogValidationFailure]) -> None:
    path = Path(path_value)
    if path.is_absolute():
        _fail(failures, location, "must be a relative path")
        return
    if ".." in path.parts:
        _fail(failures, location, "must not escape the exercise root")


def validate_manifest(manifest: dict, manifest_path: Path, declared_track: str) -> list[CatalogValidationFailure]:
    """Validate the canonical exercise manifest."""
    failures: list[CatalogValidationFailure] = []
    manifest = _expect_mapping(
        manifest,
        location="exercise",
        failures=failures,
        required={
            "schema_version",
            "id",
            "slug",
            "title",
            "summary",
            "track",
            "group",
            "source",
            "language",
            "difficulty",
            "pedagogy",
            "files",
            "student_contract",
            "build",
            "runtime",
            "grading",
            "variants",
            "metadata",
        },
        optional={"tracking", "learning"},
    )

    if _expect_int(manifest.get("schema_version"), location="exercise.schema_version", failures=failures) != 1:
        _fail(failures, "exercise.schema_version", "must be 1")

    track = _expect_str(manifest.get("track"), location="exercise.track", failures=failures)
    if track and track not in SUPPORTED_TRACKS:
        _fail(failures, "exercise.track", f"unsupported track {track!r}")
    if track and track != declared_track:
        _fail(failures, "exercise.track", f"track does not match directory segment {declared_track!r}")

    _expect_str(manifest.get("id"), location="exercise.id", failures=failures)
    _expect_str(manifest.get("slug"), location="exercise.slug", failures=failures)
    _expect_str(manifest.get("title"), location="exercise.title", failures=failures)
    _expect_str(manifest.get("summary"), location="exercise.summary", failures=failures)
    _expect_str(manifest.get("group"), location="exercise.group", failures=failures)
    _expect_str(manifest.get("language"), location="exercise.language", failures=failures)

    source = _expect_mapping(
        manifest.get("source"),
        location="exercise.source",
        failures=failures,
        required={"kind", "origin_id", "origin_path", "copyright_status"},
    )
    for key in ("kind", "origin_id", "origin_path", "copyright_status"):
        _expect_str(source.get(key), location=f"exercise.source.{key}", failures=failures)

    difficulty = _expect_mapping(
        manifest.get("difficulty"),
        location="exercise.difficulty",
        failures=failures,
        required={"level", "category"},
    )
    _expect_int(difficulty.get("level"), location="exercise.difficulty.level", failures=failures)
    _expect_str(difficulty.get("category"), location="exercise.difficulty.category", failures=failures)

    pedagogy = _expect_mapping(
        manifest.get("pedagogy"),
        location="exercise.pedagogy",
        failures=failures,
        required={
            "modes",
            "concepts",
            "skills",
            "misconceptions",
            "prerequisite_ids",
            "followup_ids",
            "estimated_minutes",
        },
    )
    for key in ("modes", "concepts", "skills", "misconceptions", "prerequisite_ids", "followup_ids"):
        _expect_string_list(pedagogy.get(key), location=f"exercise.pedagogy.{key}", failures=failures)
    _expect_int(
        pedagogy.get("estimated_minutes"),
        location="exercise.pedagogy.estimated_minutes",
        failures=failures,
    )

    files = _expect_mapping(
        manifest.get("files"),
        location="exercise.files",
        failures=failures,
        required={"statement", "starter_dir", "reference_dir", "tests_dir"},
        optional={"fixtures_dir", "hints_dir", "assets_dir"},
    )
    for key in ("statement", "starter_dir", "reference_dir", "tests_dir", "fixtures_dir", "hints_dir", "assets_dir"):
        if key in files:
            value = _expect_str(files.get(key), location=f"exercise.files.{key}", failures=failures)
            if value:
                _validate_relative_path(value, location=f"exercise.files.{key}", failures=failures)

    student_contract = _expect_mapping(
        manifest.get("student_contract"),
        location="exercise.student_contract",
        failures=failures,
        required={
            "expected_files",
            "allowed_functions",
            "forbidden_functions",
            "required_headers",
            "output_contract",
            "norm",
        },
    )
    expected_files = _expect_string_list(
        student_contract.get("expected_files"),
        location="exercise.student_contract.expected_files",
        failures=failures,
    )
    for index, filename in enumerate(expected_files):
        _validate_relative_path(
            filename,
            location=f"exercise.student_contract.expected_files[{index}]",
            failures=failures,
        )
    for key in ("allowed_functions", "forbidden_functions", "required_headers"):
        _expect_string_list(student_contract.get(key), location=f"exercise.student_contract.{key}", failures=failures)

    output_contract = _expect_mapping(
        student_contract.get("output_contract"),
        location="exercise.student_contract.output_contract",
        failures=failures,
        required={"channel", "newline_policy"},
    )
    channel = _expect_str(
        output_contract.get("channel"),
        location="exercise.student_contract.output_contract.channel",
        failures=failures,
    )
    if channel and channel not in ALLOWED_OUTPUT_CHANNELS:
        _fail(
            failures,
            "exercise.student_contract.output_contract.channel",
            f"unsupported channel {channel!r}",
        )
    newline_policy = _expect_str(
        output_contract.get("newline_policy"),
        location="exercise.student_contract.output_contract.newline_policy",
        failures=failures,
    )
    if newline_policy and newline_policy not in ALLOWED_NEWLINE_POLICIES:
        _fail(
            failures,
            "exercise.student_contract.output_contract.newline_policy",
            f"unsupported newline policy {newline_policy!r}",
        )

    norm = _expect_mapping(
        student_contract.get("norm"),
        location="exercise.student_contract.norm",
        failures=failures,
        required={"enabled"},
        optional={"profile"},
    )
    enabled = _expect_bool(norm.get("enabled"), location="exercise.student_contract.norm.enabled", failures=failures)
    if enabled and "profile" not in norm:
        _fail(failures, "exercise.student_contract.norm.profile", "missing required key")
    if "profile" in norm:
        _expect_str(norm.get("profile"), location="exercise.student_contract.norm.profile", failures=failures)

    build = _expect_mapping(
        manifest.get("build"),
        location="exercise.build",
        failures=failures,
        required={"compiler", "standard", "flags", "link_flags", "compile_mode", "entry_files"},
    )
    compiler = _expect_str(build.get("compiler"), location="exercise.build.compiler", failures=failures)
    if compiler and compiler not in ALLOWED_COMPILERS:
        _fail(failures, "exercise.build.compiler", f"unsupported compiler {compiler!r}")
    _expect_str(build.get("standard"), location="exercise.build.standard", failures=failures)
    _expect_string_list(build.get("flags"), location="exercise.build.flags", failures=failures)
    _expect_string_list(build.get("link_flags"), location="exercise.build.link_flags", failures=failures)
    compile_mode = _expect_str(build.get("compile_mode"), location="exercise.build.compile_mode", failures=failures)
    if compile_mode and compile_mode not in ALLOWED_COMPILE_MODES:
        _fail(failures, "exercise.build.compile_mode", f"unsupported compile mode {compile_mode!r}")
    entry_files = _expect_string_list(build.get("entry_files"), location="exercise.build.entry_files", failures=failures)
    for index, filename in enumerate(entry_files):
        _validate_relative_path(filename, location=f"exercise.build.entry_files[{index}]", failures=failures)
        if filename and filename not in expected_files:
            _fail(
                failures,
                f"exercise.build.entry_files[{index}]",
                "must be listed in student_contract.expected_files",
            )

    runtime = _expect_mapping(
        manifest.get("runtime"),
        location="exercise.runtime",
        failures=failures,
        required={
            "argv_policy",
            "stdin_policy",
            "timeout_seconds",
            "memory_limit_mb",
            "file_write_policy",
            "network_access",
        },
    )
    _expect_str(runtime.get("argv_policy"), location="exercise.runtime.argv_policy", failures=failures)
    _expect_str(runtime.get("stdin_policy"), location="exercise.runtime.stdin_policy", failures=failures)
    _expect_int(runtime.get("timeout_seconds"), location="exercise.runtime.timeout_seconds", failures=failures)
    _expect_int(runtime.get("memory_limit_mb"), location="exercise.runtime.memory_limit_mb", failures=failures)
    _expect_str(runtime.get("file_write_policy"), location="exercise.runtime.file_write_policy", failures=failures)
    _expect_bool(runtime.get("network_access"), location="exercise.runtime.network_access", failures=failures)

    grading = _expect_mapping(
        manifest.get("grading"),
        location="exercise.grading",
        failures=failures,
        required={"strategy", "comparator", "rubric_id", "pass_policy", "edge_case_suite_id", "analyzer_ids"},
    )
    for key in ("strategy", "comparator", "rubric_id", "edge_case_suite_id"):
        _expect_str(grading.get(key), location=f"exercise.grading.{key}", failures=failures)
    _expect_string_list(grading.get("analyzer_ids"), location="exercise.grading.analyzer_ids", failures=failures)
    pass_policy = _expect_mapping(
        grading.get("pass_policy"),
        location="exercise.grading.pass_policy",
        failures=failures,
        required={"mode", "threshold"},
    )
    pass_policy_mode = _expect_str(
        pass_policy.get("mode"),
        location="exercise.grading.pass_policy.mode",
        failures=failures,
    )
    if pass_policy_mode and pass_policy_mode not in ALLOWED_PASS_POLICY_MODES:
        _fail(failures, "exercise.grading.pass_policy.mode", f"unsupported pass policy {pass_policy_mode!r}")
    _expect_number(
        pass_policy.get("threshold"),
        location="exercise.grading.pass_policy.threshold",
        failures=failures,
    )

    variants = _expect_mapping(
        manifest.get("variants"),
        location="exercise.variants",
        failures=failures,
        required={"default", "available"},
    )
    default_variant = _expect_str(variants.get("default"), location="exercise.variants.default", failures=failures)
    available_variants = _expect_list(variants.get("available"), location="exercise.variants.available", failures=failures)
    variant_ids: set[str] = set()
    for index, variant in enumerate(available_variants):
        variant_mapping = _expect_mapping(
            variant,
            location=f"exercise.variants.available[{index}]",
            failures=failures,
            required={"id", "kind", "description"},
            optional={"starter_dir", "reference_dir", "tests_dir"},
        )
        variant_id = _expect_str(
            variant_mapping.get("id"),
            location=f"exercise.variants.available[{index}].id",
            failures=failures,
        )
        if variant_id in variant_ids:
            _fail(failures, f"exercise.variants.available[{index}].id", "duplicate variant id")
        if variant_id:
            variant_ids.add(variant_id)
        kind = _expect_str(
            variant_mapping.get("kind"),
            location=f"exercise.variants.available[{index}].kind",
            failures=failures,
        )
        if kind and kind not in ALLOWED_VARIANT_KINDS:
            _fail(
                failures,
                f"exercise.variants.available[{index}].kind",
                f"unsupported variant kind {kind!r}",
            )
        _expect_str(
            variant_mapping.get("description"),
            location=f"exercise.variants.available[{index}].description",
            failures=failures,
        )
        for key in ("starter_dir", "reference_dir", "tests_dir"):
            if key in variant_mapping:
                value = _expect_str(
                    variant_mapping.get(key),
                    location=f"exercise.variants.available[{index}].{key}",
                    failures=failures,
                )
                if value:
                    _validate_relative_path(
                        value,
                        location=f"exercise.variants.available[{index}].{key}",
                        failures=failures,
                    )
    if default_variant and default_variant not in variant_ids:
        _fail(failures, "exercise.variants.default", "must reference one of variants.available[*].id")

    if "tracking" in manifest:
        tracking = _expect_mapping(
            manifest.get("tracking"),
            location="exercise.tracking",
            failures=failures,
            optional={"productivity_tags", "habit_tags", "timeline_tags"},
        )
        for key in ("productivity_tags", "habit_tags", "timeline_tags"):
            if key in tracking:
                _expect_string_list(tracking.get(key), location=f"exercise.tracking.{key}", failures=failures)

    if "learning" in manifest:
        learning = _expect_mapping(
            manifest.get("learning"),
            location="exercise.learning",
            failures=failures,
            optional={"visible_edge_cases", "hints", "observation"},
        )
        if "visible_edge_cases" in learning:
            visible_edge_cases = _expect_list(
                learning.get("visible_edge_cases"),
                location="exercise.learning.visible_edge_cases",
                failures=failures,
            )
            for index, item in enumerate(visible_edge_cases):
                edge_case = _expect_mapping(
                    item,
                    location=f"exercise.learning.visible_edge_cases[{index}]",
                    failures=failures,
                    required={"id", "prompt"},
                    optional={"reveal_before_submit"},
                )
                _expect_str(
                    edge_case.get("id"),
                    location=f"exercise.learning.visible_edge_cases[{index}].id",
                    failures=failures,
                )
                _expect_str(
                    edge_case.get("prompt"),
                    location=f"exercise.learning.visible_edge_cases[{index}].prompt",
                    failures=failures,
                )
                if "reveal_before_submit" in edge_case:
                    _expect_bool(
                        edge_case.get("reveal_before_submit"),
                        location=f"exercise.learning.visible_edge_cases[{index}].reveal_before_submit",
                        failures=failures,
                    )
        if "hints" in learning:
            hints = _expect_list(
                learning.get("hints"),
                location="exercise.learning.hints",
                failures=failures,
            )
            for index, item in enumerate(hints):
                hint = _expect_mapping(
                    item,
                    location=f"exercise.learning.hints[{index}]",
                    failures=failures,
                    required={"id", "prompt"},
                    optional={"unlock_after_attempts"},
                )
                _expect_str(
                    hint.get("id"),
                    location=f"exercise.learning.hints[{index}].id",
                    failures=failures,
                )
                _expect_str(
                    hint.get("prompt"),
                    location=f"exercise.learning.hints[{index}].prompt",
                    failures=failures,
                )
                if "unlock_after_attempts" in hint:
                    _expect_optional_int(
                        hint.get("unlock_after_attempts"),
                        location=f"exercise.learning.hints[{index}].unlock_after_attempts",
                        failures=failures,
                    )
        if "observation" in learning:
            observation = _expect_mapping(
                learning.get("observation"),
                location="exercise.learning.observation",
                failures=failures,
                optional={"enabled", "prompts", "capture"},
            )
            if "enabled" in observation:
                _expect_bool(
                    observation.get("enabled"),
                    location="exercise.learning.observation.enabled",
                    failures=failures,
                )
            if "prompts" in observation:
                _expect_string_list(
                    observation.get("prompts"),
                    location="exercise.learning.observation.prompts",
                    failures=failures,
                )
            if "capture" in observation:
                capture = _expect_mapping(
                    observation.get("capture"),
                    location="exercise.learning.observation.capture",
                    failures=failures,
                    optional={"stdout_preview", "stdin_echo", "argv_echo"},
                )
                for key in ("stdout_preview", "stdin_echo", "argv_echo"):
                    if key in capture:
                        _expect_bool(
                            capture.get(key),
                            location=f"exercise.learning.observation.capture.{key}",
                            failures=failures,
                        )

    metadata = _expect_mapping(
        manifest.get("metadata"),
        location="exercise.metadata",
        failures=failures,
        required={"author", "reviewers", "created_at", "updated_at", "status"},
    )
    _expect_str(metadata.get("author"), location="exercise.metadata.author", failures=failures)
    _expect_string_list(metadata.get("reviewers"), location="exercise.metadata.reviewers", failures=failures)
    _expect_str(metadata.get("created_at"), location="exercise.metadata.created_at", failures=failures)
    _expect_str(metadata.get("updated_at"), location="exercise.metadata.updated_at", failures=failures)
    _expect_str(metadata.get("status"), location="exercise.metadata.status", failures=failures)

    if manifest_path.name != "exercise.yml":
        _fail(failures, str(manifest_path), "manifest filename must be exercise.yml")

    return failures


def validate_tests_payload(tests_payload: dict) -> tuple[list[CatalogValidationFailure], list[ExerciseTestCase]]:
    """Validate and normalize `tests/tests.yml`."""
    failures: list[CatalogValidationFailure] = []
    tests_payload = _expect_mapping(
        tests_payload,
        location="tests",
        failures=failures,
        required={"cases"},
    )
    raw_cases = _expect_list(tests_payload.get("cases"), location="tests.cases", failures=failures)
    cases: list[ExerciseTestCase] = []
    seen_ids: set[str] = set()
    for index, case in enumerate(raw_cases):
        case_mapping = _expect_mapping(
            case,
            location=f"tests.cases[{index}]",
            failures=failures,
            required={"id"},
            optional={"argv", "stdin", "expected_stdout", "expected_stderr", "expected_exit_code"},
        )
        test_id = _expect_str(case_mapping.get("id"), location=f"tests.cases[{index}].id", failures=failures)
        if test_id in seen_ids:
            _fail(failures, f"tests.cases[{index}].id", "duplicate testcase id")
        if test_id:
            seen_ids.add(test_id)
        argv = _expect_string_list(
            case_mapping.get("argv", []),
            location=f"tests.cases[{index}].argv",
            failures=failures,
            allow_empty_items=True,
        )
        stdin = _expect_str(
            case_mapping.get("stdin", ""),
            location=f"tests.cases[{index}].stdin",
            failures=failures,
            allow_empty=True,
        )
        expected_stdout_raw = case_mapping.get("expected_stdout")
        expected_stdout: str | None
        if expected_stdout_raw is None:
            expected_stdout = None
        else:
            expected_stdout = _expect_str(
                expected_stdout_raw,
                location=f"tests.cases[{index}].expected_stdout",
                failures=failures,
                allow_empty=True,
            )
        expected_stderr = _expect_str(
            case_mapping.get("expected_stderr", ""),
            location=f"tests.cases[{index}].expected_stderr",
            failures=failures,
            allow_empty=True,
        )
        expected_exit_code = _expect_int(
            case_mapping.get("expected_exit_code", 0),
            location=f"tests.cases[{index}].expected_exit_code",
            failures=failures,
        )
        cases.append(
            ExerciseTestCase(
                test_id=test_id,
                argv=argv,
                stdin=stdin,
                expected_stdout=expected_stdout,
                expected_stderr=expected_stderr,
                expected_exit_code=expected_exit_code,
            )
        )
    if not raw_cases:
        _fail(failures, "tests.cases", "must contain at least one testcase")
    return failures, cases


def validate_bundle_assets(
    manifest: dict,
    *,
    statement_markdown: str,
    harness_path: Path | None,
    starter_files: list[CatalogFile],
    reference_files: list[CatalogFile],
) -> list[CatalogValidationFailure]:
    """Validate statement, harness, and expected starter/reference assets."""
    failures: list[CatalogValidationFailure] = []
    if not statement_markdown.strip():
        _fail(failures, "statement.md", "statement must not be empty")

    compile_mode = manifest.get("build", {}).get("compile_mode")
    if compile_mode == "function_with_harness" and harness_path is None:
        _fail(failures, "tests/main.c", "missing harness for function_with_harness exercise")

    expected_files = set(manifest.get("student_contract", {}).get("expected_files", []))
    starter_index = {item.relative_path for item in starter_files}
    reference_index = {item.relative_path for item in reference_files}
    for filename in sorted(expected_files):
        if filename not in starter_index:
            _fail(failures, f"starter/{filename}", "missing expected starter file")
        if filename not in reference_index:
            _fail(failures, f"reference/{filename}", "missing expected reference file")

    return failures
