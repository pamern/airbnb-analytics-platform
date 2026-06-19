"""Write listing segment assignments to MotherDuck."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from duckdb import DuckDBPyConnection

PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.listing_segmentation.config import (  # noqa: E402
    ASSIGNMENT_COLUMNS,
    N_CLUSTERS,
    SEGMENT_TABLE,
    SOURCE_TABLE,
)
from utils.motherduck import connect_motherduck  # noqa: E402


def get_motherduck_write_connection() -> DuckDBPyConnection:
    """Return a write-enabled MotherDuck connection after explicit guards pass."""
    target = os.getenv("AIRBNB_DB_TARGET", "local").lower()
    if target != "motherduck":
        raise RuntimeError(
            "Refusing to write listing segments because AIRBNB_DB_TARGET is not 'motherduck'."
        )
    if os.getenv("ALLOW_MOTHERDUCK_WRITE") != "1":
        raise RuntimeError(
            "Refusing to write listing segments. Set ALLOW_MOTHERDUCK_WRITE=1 to allow MotherDuck writes."
        )
    return connect_motherduck(read_only=False)


def validate_listing_segments_for_write(
    assignments: pd.DataFrame,
    expected_row_count: int,
) -> None:
    """Validate assignment DataFrame before replacing gold.gold_listing_segments."""
    columns = list(assignments.columns)
    if columns != ASSIGNMENT_COLUMNS:
        raise ValueError(
            f"Listing segment assignments must have columns {ASSIGNMENT_COLUMNS}; got {columns}"
        )
    if assignments.empty:
        raise ValueError("Listing segment assignments are empty.")
    if len(assignments) != expected_row_count:
        raise ValueError(
            f"Assignment row count {len(assignments)} does not match input row count {expected_row_count}."
        )
    if assignments["listing_id"].isna().any():
        raise ValueError("listing_id contains null values.")
    duplicate_count = int(assignments["listing_id"].duplicated().sum())
    if duplicate_count:
        raise ValueError(f"listing_id must be unique; found {duplicate_count} duplicates.")
    if assignments["cluster_id"].isna().any():
        raise ValueError("cluster_id contains null values.")

    invalid_clusters = sorted(
        set(assignments["cluster_id"].astype(int)) - set(range(N_CLUSTERS))
    )
    if invalid_clusters:
        raise ValueError(f"cluster_id contains invalid values: {invalid_clusters}")

    if "artifact_path" in assignments.columns:
        raise ValueError("artifact_path must not be written to MotherDuck.")


def write_listing_segments_to_motherduck(
    assignments: pd.DataFrame,
    expected_row_count: int,
    target_table: str = SEGMENT_TABLE,
    connection: DuckDBPyConnection | None = None,
) -> dict[str, Any]:
    """Replace gold.gold_listing_segments with validated model assignments."""
    validate_listing_segments_for_write(assignments, expected_row_count)
    owns_connection = connection is None
    if connection is None:
        connection = get_motherduck_write_connection()
    temp_name = "listing_segments_assignments_df"
    try:
        connection.execute("CREATE SCHEMA IF NOT EXISTS gold")
        connection.register(temp_name, assignments)
        connection.execute(
            f"""
            CREATE OR REPLACE TABLE {target_table} AS
            SELECT
                listing_id,
                CAST(cluster_id AS INTEGER) AS cluster_id,
                CAST(segment_name AS VARCHAR) AS segment_name,
                CAST(distance_to_centroid AS DOUBLE) AS distance_to_centroid,
                CAST(run_id AS VARCHAR) AS run_id,
                CAST(model_name AS VARCHAR) AS model_name,
                CAST(model_version AS VARCHAR) AS model_version,
                CAST(assigned_at AS TIMESTAMP) AS assigned_at
            FROM {temp_name}
            """
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to write {target_table} for run_id={assignments['run_id'].iloc[0]}: {exc}"
        ) from exc
    finally:
        try:
            connection.unregister(temp_name)
        except Exception:
            pass

    try:
        written_row_count = connection.execute(
            f"SELECT COUNT(*) FROM {target_table}"
        ).fetchone()[0]
        quality = connection.execute(
            f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT listing_id) AS unique_listings,
                COUNT(*) FILTER (WHERE listing_id IS NULL) AS null_listing_ids,
                COUNT(*) FILTER (WHERE cluster_id IS NULL) AS null_cluster_ids
            FROM {target_table}
            """
        ).fetchdf().iloc[0].to_dict()
        distribution = connection.execute(
            f"""
            SELECT
                cluster_id,
                segment_name,
                COUNT(*) AS listing_count
            FROM {target_table}
            GROUP BY cluster_id, segment_name
            ORDER BY cluster_id
            """
        ).fetchdf()
        join_count = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM {target_table} AS segments
            JOIN {SOURCE_TABLE} AS features
              ON segments.listing_id = features.listing_id
            """
        ).fetchone()[0]
    finally:
        if owns_connection:
            connection.close()

    if written_row_count != expected_row_count:
        raise RuntimeError(
            f"Wrote {written_row_count} rows to {target_table}, expected {expected_row_count}."
        )
    if int(quality["unique_listings"]) != expected_row_count:
        raise RuntimeError(
            f"Unique listing count after write is {quality['unique_listings']}, expected {expected_row_count}."
        )
    if join_count != expected_row_count:
        raise RuntimeError(
            f"Join count with {SOURCE_TABLE} is {join_count}, expected {expected_row_count}."
        )

    return {
        "target_table": target_table,
        "row_count": int(written_row_count),
        "quality": quality,
        "cluster_distribution": distribution.to_dict(orient="records"),
        "feature_join_count": int(join_count),
        "strategy": "CREATE OR REPLACE TABLE",
    }
