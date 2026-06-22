"""Load and validate Gold features for listing segmentation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from duckdb import DuckDBPyConnection

PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.listing_segmentation.config import (  # noqa: E402
    MODEL_FEATURES,
    N_CLUSTERS,
    OPTIONAL_PROFILE_COLUMNS,
    REQUIRED_COLUMNS,
    SOURCE_TABLE,
)
from utils.motherduck import connect_duckdb, connect_motherduck  # noqa: E402


def get_connection(read_only: bool = True) -> DuckDBPyConnection:
    """Return a DuckDB or MotherDuck connection based on AIRBNB_DB_TARGET."""
    target = os.getenv("AIRBNB_DB_TARGET", "local").lower()
    if target == "motherduck":
        return connect_motherduck(read_only=read_only)
    return connect_duckdb(PROJECT_ROOT / "airbnb_analytics.duckdb", read_only=read_only)


def table_exists(connection: DuckDBPyConnection, table_name: str) -> bool:
    schema_name, short_name = table_name.split(".", 1)
    row_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = ?
          AND table_name = ?
        """,
        [schema_name, short_name],
    ).fetchone()[0]
    return row_count > 0


def load_cluster_features(
    connection: DuckDBPyConnection,
    source_table: str = SOURCE_TABLE,
) -> pd.DataFrame:
    """Read the Gold cluster feature table and validate it."""
    if not table_exists(connection, source_table):
        raise RuntimeError(
            f"Required Gold feature table does not exist: {source_table}. "
            "Run dbt build for gold_cluster_model_features first."
        )

    available_columns = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info('{source_table}')").fetchall()
    }
    selected_columns = REQUIRED_COLUMNS + [
        column for column in OPTIONAL_PROFILE_COLUMNS if column in available_columns
    ]
    column_sql = ", ".join(selected_columns)
    features = connection.execute(f"SELECT {column_sql} FROM {source_table}").fetchdf()
    validate_cluster_features(features)
    return features


def validate_cluster_features(features: pd.DataFrame) -> None:
    """Fail fast if dbt Gold features are not ready for model training."""
    if features.empty:
        raise ValueError("Gold cluster feature table is empty.")

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in features.columns]
    if missing_columns:
        raise ValueError(f"Missing required cluster feature columns: {missing_columns}")

    duplicate_count = int(features["listing_id"].duplicated().sum())
    if duplicate_count:
        raise ValueError(f"listing_id must be unique; found {duplicate_count} duplicates.")

    null_columns = [
        column for column in REQUIRED_COLUMNS if features[column].isna().any()
    ]
    if null_columns:
        raise ValueError(f"Gold cluster features contain nulls in required columns: {null_columns}")

    numeric_values = features[MODEL_FEATURES].select_dtypes(include=[np.number])
    if not np.isfinite(numeric_values.to_numpy()).all():
        raise ValueError("Gold cluster features contain NaN or infinity in numeric features.")

    if len(features) < N_CLUSTERS:
        raise ValueError(
            f"Need at least {N_CLUSTERS} rows to train KMeans; found {len(features)}."
        )

    if N_CLUSTERS < 2:
        raise ValueError(f"N_CLUSTERS must be at least 2; got {N_CLUSTERS}.")
