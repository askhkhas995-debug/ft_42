"""Strict pool dataset validation helpers."""

from __future__ import annotations

from pathlib import Path

from platform_catalog.models import PoolExerciseRef, PoolLevel, PoolSelectionConfig, PoolTimingConfig, PoolUnlockRule, SUPPORTED_TRACKS
from platform_catalog.validation import (
    CatalogValidationFailure,
    _expect_bool,
    _expect_int,
    _expect_list,
    _expect_mapping,
    _expect_str,
    _expect_string_list,
    _fail,
)


ALLOWED_SELECTION_STRATEGIES = {"random", "weighted", "ordered"}
ALLOWED_REPEAT_POLICIES = {"avoid_passed", "avoid_recent", "allow_review"}
ALLOWED_SEED_POLICIES = {"deterministic_per_session", "system_random"}
ALLOWED_COOLDOWN_SCOPES = {"pool", "level"}
ALLOWED_POOL_MODES = {"practice", "exam"}


def _normalize_int_list(value: object, *, location: str, failures: list[CatalogValidationFailure]) -> list[int]:
    items = _expect_list(value, location=location, failures=failures)
    normalized: list[int] = []
    for index, item in enumerate(items):
        normalized.append(_expect_int(item, location=f"{location}[{index}]", failures=failures))
    return normalized


def validate_pool_manifest(manifest: dict, manifest_path: Path, declared_track: str) -> list[CatalogValidationFailure]:
    """Validate the canonical pool manifest."""
    failures: list[CatalogValidationFailure] = []
    manifest = _expect_mapping(
        manifest,
        location="pool",
        failures=failures,
        required={
            "schema_version",
            "id",
            "title",
            "track",
            "mode",
            "description",
            "selection",
            "timing",
            "levels",
            "metadata",
        },
    )

    if _expect_int(manifest.get("schema_version"), location="pool.schema_version", failures=failures) != 1:
        _fail(failures, "pool.schema_version", "must be 1")

    track = _expect_str(manifest.get("track"), location="pool.track", failures=failures)
    if track and track not in SUPPORTED_TRACKS:
        _fail(failures, "pool.track", f"unsupported track {track!r}")
    if track and track != declared_track:
        _fail(failures, "pool.track", f"track does not match directory segment {declared_track!r}")

    for key in ("id", "title", "mode", "description"):
        _expect_str(manifest.get(key), location=f"pool.{key}", failures=failures)
    mode = _expect_str(manifest.get("mode"), location="pool.mode", failures=failures)
    if mode and mode not in ALLOWED_POOL_MODES:
        _fail(failures, "pool.mode", f"unsupported mode {mode!r}")

    selection = _expect_mapping(
        manifest.get("selection"),
        location="pool.selection",
        failures=failures,
        required={"strategy", "repeat_policy"},
        optional={"recent_window", "seed_policy"},
    )
    strategy = _expect_str(selection.get("strategy"), location="pool.selection.strategy", failures=failures)
    if strategy and strategy not in ALLOWED_SELECTION_STRATEGIES:
        _fail(failures, "pool.selection.strategy", f"unsupported strategy {strategy!r}")
    repeat_policy = _expect_str(
        selection.get("repeat_policy"),
        location="pool.selection.repeat_policy",
        failures=failures,
    )
    if repeat_policy and repeat_policy not in ALLOWED_REPEAT_POLICIES:
        _fail(failures, "pool.selection.repeat_policy", f"unsupported repeat policy {repeat_policy!r}")
    if "recent_window" in selection:
        recent_window = _expect_int(
            selection.get("recent_window"),
            location="pool.selection.recent_window",
            failures=failures,
        )
        if recent_window < 0:
            _fail(failures, "pool.selection.recent_window", "must be >= 0")
    if repeat_policy == "avoid_recent" and "recent_window" not in selection:
        _fail(failures, "pool.selection.recent_window", "required when repeat_policy=avoid_recent")
    if "seed_policy" in selection:
        seed_policy = _expect_str(
            selection.get("seed_policy"),
            location="pool.selection.seed_policy",
            failures=failures,
        )
        if seed_policy and seed_policy not in ALLOWED_SEED_POLICIES:
            _fail(failures, "pool.selection.seed_policy", f"unsupported seed policy {seed_policy!r}")

    timing = _expect_mapping(
        manifest.get("timing"),
        location="pool.timing",
        failures=failures,
        required={"total_time_seconds", "per_level_time_seconds", "cooldown"},
    )
    for key in ("total_time_seconds", "per_level_time_seconds"):
        value = _expect_int(timing.get(key), location=f"pool.timing.{key}", failures=failures)
        if value <= 0:
            _fail(failures, f"pool.timing.{key}", "must be > 0")
    cooldown = _expect_mapping(
        timing.get("cooldown"),
        location="pool.timing.cooldown",
        failures=failures,
        required={"enabled", "seconds", "scope"},
    )
    _expect_bool(cooldown.get("enabled"), location="pool.timing.cooldown.enabled", failures=failures)
    cooldown_seconds = _expect_int(
        cooldown.get("seconds"),
        location="pool.timing.cooldown.seconds",
        failures=failures,
    )
    if cooldown_seconds < 0:
        _fail(failures, "pool.timing.cooldown.seconds", "must be >= 0")
    cooldown_scope = _expect_str(
        cooldown.get("scope"),
        location="pool.timing.cooldown.scope",
        failures=failures,
    )
    if cooldown_scope and cooldown_scope not in ALLOWED_COOLDOWN_SCOPES:
        _fail(failures, "pool.timing.cooldown.scope", f"unsupported cooldown scope {cooldown_scope!r}")

    metadata = _expect_mapping(
        manifest.get("metadata"),
        location="pool.metadata",
        failures=failures,
        required={"created_at", "updated_at", "status"},
    )
    for key in ("created_at", "updated_at", "status"):
        _expect_str(metadata.get(key), location=f"pool.metadata.{key}", failures=failures)

    raw_levels = _expect_list(manifest.get("levels"), location="pool.levels", failures=failures)
    if not raw_levels:
        _fail(failures, "pool.levels", "must contain at least one level")

    level_ids: set[int] = set()
    for index, level in enumerate(raw_levels):
        level_mapping = _expect_mapping(
            level,
            location=f"pool.levels[{index}]",
            failures=failures,
            required={"level", "title", "min_picks", "unlock_if", "exercise_refs"},
            optional={"max_picks", "time_limit_seconds"},
        )
        level_number = _expect_int(level_mapping.get("level"), location=f"pool.levels[{index}].level", failures=failures)
        if level_number in level_ids:
            _fail(failures, f"pool.levels[{index}].level", "duplicate level number")
        else:
            level_ids.add(level_number)
        min_picks = _expect_int(
            level_mapping.get("min_picks"),
            location=f"pool.levels[{index}].min_picks",
            failures=failures,
        )
        if min_picks <= 0:
            _fail(failures, f"pool.levels[{index}].min_picks", "must be > 0")
        if "max_picks" in level_mapping:
            max_picks = _expect_int(
                level_mapping.get("max_picks"),
                location=f"pool.levels[{index}].max_picks",
                failures=failures,
            )
            if max_picks <= 0:
                _fail(failures, f"pool.levels[{index}].max_picks", "must be > 0")
            if max_picks < min_picks:
                _fail(failures, f"pool.levels[{index}].max_picks", "must be >= min_picks")
        if "time_limit_seconds" in level_mapping:
            time_limit_seconds = _expect_int(
                level_mapping.get("time_limit_seconds"),
                location=f"pool.levels[{index}].time_limit_seconds",
                failures=failures,
            )
            if time_limit_seconds <= 0:
                _fail(failures, f"pool.levels[{index}].time_limit_seconds", "must be > 0")
        _expect_str(level_mapping.get("title"), location=f"pool.levels[{index}].title", failures=failures)

        unlock_if = _expect_mapping(
            level_mapping.get("unlock_if"),
            location=f"pool.levels[{index}].unlock_if",
            failures=failures,
            required={"all_of", "any_of"},
        )
        all_of = _normalize_int_list(unlock_if.get("all_of"), location=f"pool.levels[{index}].unlock_if.all_of", failures=failures)
        any_of = _normalize_int_list(unlock_if.get("any_of"), location=f"pool.levels[{index}].unlock_if.any_of", failures=failures)
        for unlock_level in all_of + any_of:
            if unlock_level >= level_number:
                _fail(
                    failures,
                    f"pool.levels[{index}].unlock_if",
                    "unlock references must point to lower level numbers",
                )

        exercise_refs = _expect_list(
            level_mapping.get("exercise_refs"),
            location=f"pool.levels[{index}].exercise_refs",
            failures=failures,
        )
        if not exercise_refs:
            _fail(failures, f"pool.levels[{index}].exercise_refs", "must contain at least one exercise reference")
        seen_refs: set[tuple[str, str]] = set()
        seen_order_values: set[int] = set()
        for ref_index, ref in enumerate(exercise_refs):
            ref_mapping = _expect_mapping(
                ref,
                location=f"pool.levels[{index}].exercise_refs[{ref_index}]",
                failures=failures,
                required={"exercise_id"},
                optional={"variant", "weight", "order"},
            )
            exercise_id = _expect_str(
                ref_mapping.get("exercise_id"),
                location=f"pool.levels[{index}].exercise_refs[{ref_index}].exercise_id",
                failures=failures,
            )
            variant_id = _expect_str(
                ref_mapping.get("variant", "normal"),
                location=f"pool.levels[{index}].exercise_refs[{ref_index}].variant",
                failures=failures,
            )
            ref_key = (exercise_id, variant_id)
            if exercise_id and ref_key in seen_refs:
                _fail(
                    failures,
                    f"pool.levels[{index}].exercise_refs[{ref_index}]",
                    "duplicate exercise_id/variant pair in level",
                )
            seen_refs.add(ref_key)
            if "weight" in ref_mapping:
                weight = _expect_int(
                    ref_mapping.get("weight"),
                    location=f"pool.levels[{index}].exercise_refs[{ref_index}].weight",
                    failures=failures,
                )
                if weight <= 0:
                    _fail(
                        failures,
                        f"pool.levels[{index}].exercise_refs[{ref_index}].weight",
                        "must be > 0",
                    )
            if "order" in ref_mapping:
                order = _expect_int(
                    ref_mapping.get("order"),
                    location=f"pool.levels[{index}].exercise_refs[{ref_index}].order",
                    failures=failures,
                )
                if order <= 0:
                    _fail(
                        failures,
                        f"pool.levels[{index}].exercise_refs[{ref_index}].order",
                        "must be > 0",
                    )
                elif order in seen_order_values:
                    _fail(
                        failures,
                        f"pool.levels[{index}].exercise_refs[{ref_index}].order",
                        "duplicate ordered rank in level",
                    )
                else:
                    seen_order_values.add(order)
            if strategy == "ordered" and "order" not in ref_mapping:
                _fail(
                    failures,
                    f"pool.levels[{index}].exercise_refs[{ref_index}].order",
                    "required when selection.strategy=ordered",
                )

    defined_levels = {level["level"] for level in raw_levels if isinstance(level, dict) and isinstance(level.get("level"), int)}
    for index, level in enumerate(raw_levels):
        if not isinstance(level, dict):
            continue
        unlock_if = level.get("unlock_if", {})
        if not isinstance(unlock_if, dict):
            continue
        for location_key in ("all_of", "any_of"):
            unlock_levels = unlock_if.get(location_key, [])
            if not isinstance(unlock_levels, list):
                continue
            for unlock_index, unlock_level in enumerate(unlock_levels):
                if isinstance(unlock_level, bool) or not isinstance(unlock_level, int):
                    continue
                if unlock_level not in defined_levels:
                    _fail(
                        failures,
                        f"pool.levels[{index}].unlock_if.{location_key}[{unlock_index}]",
                        "references undefined level",
                    )

    if manifest_path.name != "pool.yml":
        _fail(failures, str(manifest_path), "pool filename must be pool.yml")

    return failures


def build_pool_models(manifest: dict) -> tuple[PoolSelectionConfig, PoolTimingConfig, list[PoolLevel]]:
    """Convert a validated pool manifest into typed models."""
    selection_raw = manifest["selection"]
    selection = PoolSelectionConfig(
        strategy=selection_raw["strategy"],
        repeat_policy=selection_raw["repeat_policy"],
        recent_window=selection_raw.get("recent_window", 0),
        seed_policy=selection_raw.get("seed_policy", "deterministic_per_session"),
    )

    cooldown_raw = manifest["timing"]["cooldown"]
    timing = PoolTimingConfig(
        total_time_seconds=manifest["timing"]["total_time_seconds"],
        per_level_time_seconds=manifest["timing"]["per_level_time_seconds"],
        cooldown_enabled=cooldown_raw["enabled"],
        cooldown_seconds=cooldown_raw["seconds"],
        cooldown_scope=cooldown_raw["scope"],
    )

    levels: list[PoolLevel] = []
    for level_raw in sorted(manifest["levels"], key=lambda item: item["level"]):
        exercise_refs: list[PoolExerciseRef] = []
        for declaration_index, ref_raw in enumerate(level_raw["exercise_refs"]):
            exercise_refs.append(
                PoolExerciseRef(
                    exercise_id=ref_raw["exercise_id"],
                    variant_id=ref_raw.get("variant", "normal"),
                    weight=ref_raw.get("weight", 1),
                    order=ref_raw.get("order"),
                    declaration_index=declaration_index,
                )
            )
        levels.append(
            PoolLevel(
                level=level_raw["level"],
                title=level_raw["title"],
                min_picks=level_raw["min_picks"],
                max_picks=level_raw.get("max_picks"),
                time_limit_seconds=level_raw.get("time_limit_seconds"),
                unlock_if=PoolUnlockRule(
                    all_of=list(level_raw["unlock_if"]["all_of"]),
                    any_of=list(level_raw["unlock_if"]["any_of"]),
                ),
                exercise_refs=exercise_refs,
            )
        )
    return selection, timing, levels
