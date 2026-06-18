"""Train listing segment KMeans model and publish Gold segment outputs."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from duckdb import DuckDBPyConnection
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.motherduck import connect_duckdb, connect_motherduck  # noqa: E402


INPUT_TABLE = "gold.gold_listing_cluster_features"
OUTPUT_TABLE = "gold.gold_listing_segments"
ARTIFACT_TABLE = "ml.model_artifacts"
ARTIFACT_PATH = PROJECT_ROOT / "ml" / "artifacts" / "cluster_segment_model_v1.joblib"

CATEGORICAL_FEATURES = ["room_type", "property_base_group"]
NUMERIC_FEATURES = [
    "accommodates",
    "bedrooms",
    "bathrooms",
    "beds",
    "amenities_count",
    "minimum_nights_log",
]
MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

SEGMENT_MAP = {
    0: "Standard short-stay listings",
    1: "Long-stay standard apartments",
    2: "Large short-stay group homes",
}


def get_connection() -> DuckDBPyConnection:
    target = os.getenv("AIRBNB_DB_TARGET", "local").lower()
    if target == "motherduck":
        if os.getenv("ALLOW_MOTHERDUCK_WRITE") != "1":
            raise RuntimeError("Set ALLOW_MOTHERDUCK_WRITE=1 before writing to MotherDuck.")
        return connect_motherduck(read_only=False)
    return connect_duckdb(PROJECT_ROOT / "airbnb_analytics.duckdb", read_only=False)


def build_model() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("numeric", StandardScaler(), NUMERIC_FEATURES),
        ]
    )
    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("kmeans", KMeans(n_clusters=3, random_state=42, n_init=10)),
        ]
    )


def load_training_data(connection: DuckDBPyConnection) -> pd.DataFrame:
    listings = connection.execute(f"SELECT * FROM {INPUT_TABLE}").fetchdf()
    missing = [column for column in MODEL_FEATURES + ["listing_id", "price"] if column not in listings]
    if missing:
        raise ValueError(f"Missing training columns: {missing}")
    return listings.dropna(subset=MODEL_FEATURES + ["listing_id", "price"]).copy()


def train_listing_segments(connection: DuckDBPyConnection) -> tuple[pd.DataFrame, Pipeline]:
    listings = load_training_data(connection)
    model = build_model()
    listings["cluster"] = model.fit_predict(listings[MODEL_FEATURES])
    listings["segment_name"] = listings["cluster"].map(SEGMENT_MAP).fillna("Unknown")

    output_columns = [
        "listing_id",
        "price",
        "room_type",
        "property_type",
        "property_base_group",
        "accommodates",
        "bedrooms",
        "bathrooms",
        "beds",
        "amenities_count",
        "minimum_nights",
        "minimum_nights_log",
        "cluster",
        "segment_name",
    ]
    gold_segments = listings[output_columns].copy()

    connection.execute("CREATE SCHEMA IF NOT EXISTS gold")
    connection.register("gold_listing_segments_df", gold_segments)
    connection.execute(
        f"CREATE OR REPLACE TABLE {OUTPUT_TABLE} AS SELECT * FROM gold_listing_segments_df"
    )
    connection.unregister("gold_listing_segments_df")

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACT_PATH)
    save_model_artifact_to_database(connection, ARTIFACT_PATH)
    return gold_segments, model


def save_model_artifact_to_database(connection: DuckDBPyConnection, artifact_path: Path) -> None:
    connection.execute("CREATE SCHEMA IF NOT EXISTS ml")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ARTIFACT_TABLE} (
            model_name VARCHAR,
            model_version VARCHAR,
            artifact_type VARCHAR,
            artifact_blob BLOB,
            feature_schema_json VARCHAR,
            created_at TIMESTAMP,
            is_active BOOLEAN
        )
        """
    )
    feature_schema = {
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "model_features": MODEL_FEATURES,
        "excluded_from_model": [
            "price",
            "review",
            "host",
            "superhost",
            "instant_bookable",
            "neighbourhood",
            "latitude",
            "longitude",
        ],
    }
    model_name = "listing_segment_kmeans"
    model_version = "v1"
    artifact_type = "sklearn_pipeline_joblib"
    connection.execute(
        f"""
        UPDATE {ARTIFACT_TABLE}
        SET is_active = FALSE
        WHERE model_name = ? AND is_active = TRUE
        """,
        [model_name],
    )
    connection.execute(
        f"INSERT INTO {ARTIFACT_TABLE} VALUES (?, ?, ?, ?, ?, ?, TRUE)",
        [
            model_name,
            model_version,
            artifact_type,
            artifact_path.read_bytes(),
            json.dumps(feature_schema),
            datetime.now(timezone.utc).replace(tzinfo=None),
        ],
    )


def main() -> None:
    connection = get_connection()
    try:
        gold_segments, _ = train_listing_segments(connection)
        print(f"Created {OUTPUT_TABLE}")
        print(f"Rows: {len(gold_segments):,}")
        print(f"Saved model: {ARTIFACT_PATH}")
        print(gold_segments[["listing_id", "cluster", "segment_name"]].head().to_string(index=False))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
