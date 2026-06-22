"""Dagster assets that validate raw Airbnb files and materialize Bronze tables."""

from __future__ import annotations

from pathlib import Path

from dagster import asset

from configs.settings import MOTHERDUCK
from ingestion.load_to_motherduck import BRONZE_TABLES, RAW_CITY_DIR, recreate_bronze_table, resolve_source_file
from ingestion.validate_raw_data import validate_required_files
from orchestration.resources.motherduck import MotherDuckResource


@asset(group_name="ingestion")
def raw_source_validation() -> list[str]:
    """Fail before ingestion when any required raw source, including GeoJSON, is absent."""
    missing = validate_required_files(RAW_CITY_DIR)
    if missing:
        raise FileNotFoundError("Missing required raw files: " + ", ".join(str(path) for path in missing))
    return [str(RAW_CITY_DIR / filename) for filename in ("listings.csv", "calendar.csv", "reviews.csv", "neighbourhoods.csv", "neighbourhoods.geojson")]


def _load_bronze_table(context, *, table_name: str, raw_source_validation: list[str], motherduck: MotherDuckResource) -> int:
    """Reuse the ingestion loader's idempotent replace-table implementation."""
    del raw_source_validation  # Dependency guarantees source validation completed first.
    source_path = resolve_source_file(BRONZE_TABLES[table_name], raw_dir=RAW_CITY_DIR)
    with motherduck.transaction() as connection:
        row_count = recreate_bronze_table(connection, MOTHERDUCK.schema, table_name, source_path)
    context.log.info("Bronze ingestion table=%s source=%s rows=%d", table_name, source_path.name, row_count)
    return row_count


# The key prefix matches dbt's ``airbnb_bronze`` source asset keys, creating
# real Dagster lineage from ingestion into Silver models.
@asset(key_prefix="airbnb_bronze", group_name="ingestion")
def bronze_listings(context, raw_source_validation: list[str], motherduck: MotherDuckResource) -> int:
    return _load_bronze_table(context, table_name="bronze_listings", raw_source_validation=raw_source_validation, motherduck=motherduck)


@asset(key_prefix="airbnb_bronze", group_name="ingestion")
def bronze_calendar(context, raw_source_validation: list[str], motherduck: MotherDuckResource) -> int:
    return _load_bronze_table(context, table_name="bronze_calendar", raw_source_validation=raw_source_validation, motherduck=motherduck)


@asset(key_prefix="airbnb_bronze", group_name="ingestion")
def bronze_reviews(context, raw_source_validation: list[str], motherduck: MotherDuckResource) -> int:
    return _load_bronze_table(context, table_name="bronze_reviews", raw_source_validation=raw_source_validation, motherduck=motherduck)


@asset(key_prefix="airbnb_bronze", group_name="ingestion")
def bronze_neighbourhoods(context, raw_source_validation: list[str], motherduck: MotherDuckResource) -> int:
    return _load_bronze_table(context, table_name="bronze_neighbourhoods", raw_source_validation=raw_source_validation, motherduck=motherduck)
