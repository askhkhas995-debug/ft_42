"""Dataset validation entrypoint backed by the catalog service."""

from __future__ import annotations

from pathlib import Path

from platform_catalog import CatalogService, CatalogValidationError


def _platform_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    catalog = CatalogService(_platform_root())
    try:
        exercises = catalog.list_exercises()
        pools = catalog.list_pools()
    except CatalogValidationError as exc:
        print("validate: catalog validation failed")
        for failure in exc.failures:
            print(f"- {failure.render()}")
        return 1

    print(f"validate: ok ({len(exercises)} exercise bundles, {len(pools)} pool bundles indexed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
