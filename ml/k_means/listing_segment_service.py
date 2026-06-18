""" file backend
user nhập listing
→ xử lý feature
→ load model
→ predict cluster
→ query giá trong cluster
→ trả kết quả
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from duckdb import DuckDBPyConnection

PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.k_means.feature_utils import prepare_listing_cluster_features  # noqa: E402
from ml.k_means.train_listing_segments import MODEL_FEATURES, SEGMENT_MAP  # noqa: E402
from utils.motherduck import connect_duckdb, connect_motherduck  # noqa: E402


ARTIFACT_PATH = PROJECT_ROOT / "ml" / "artifacts" / "cluster_segment_model_v1.joblib"
ARTIFACT_TABLE = "ml.model_artifacts"
SEGMENT_TABLE = "gold.gold_listing_segments"


def get_connection(read_only: bool = True) -> DuckDBPyConnection:
    target = os.getenv("AIRBNB_DB_TARGET", "local").lower()
    if target == "motherduck":
        return connect_motherduck(read_only=read_only)
    return connect_duckdb(PROJECT_ROOT / "airbnb_analytics.duckdb", read_only=read_only)


def load_model(connection: DuckDBPyConnection | None = None) -> Any:
    if ARTIFACT_PATH.exists():
        return joblib.load(ARTIFACT_PATH)

    owns_connection = connection is None
    if connection is None:
        connection = get_connection(read_only=True)
    try:
        row = connection.execute(
            f"""
            SELECT artifact_blob
            FROM {ARTIFACT_TABLE}
            WHERE model_name = 'listing_segment_kmeans' AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        if owns_connection and connection is not None:
            connection.close()

    if row is None:
        raise FileNotFoundError("No local model artifact or active database model artifact found.")

    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as temp_file:
        temp_file.write(row[0])
        temp_path = Path(temp_file.name)
    try:
        return joblib.load(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def build_user_listing_frame(user_listing: dict[str, Any]) -> pd.DataFrame:
    current_price = user_listing.get("current_price")
    row = {
        "room_type": user_listing.get("room_type"),
        "property_type": user_listing.get("property_type"),
        "accommodates": user_listing.get("accommodates"),
        "bedrooms": user_listing.get("bedrooms"),
        "bathrooms": user_listing.get("bathrooms"),
        "beds": user_listing.get("beds"),
        "amenities_count": user_listing.get("amenities_count"),
        "minimum_nights": user_listing.get("minimum_nights"),
        "price": current_price,
    }
    listing = prepare_listing_cluster_features(pd.DataFrame([row]), drop_invalid_price=False)
    missing = [column for column in MODEL_FEATURES if column not in listing.columns]
    if missing:
        raise ValueError(f"User listing cannot produce model features: {missing}")
    return listing


def query_segment_prices(connection: DuckDBPyConnection, cluster: int, current_price: float) -> dict[str, float]:
    prices = connection.execute(
        f"SELECT price FROM {SEGMENT_TABLE} WHERE cluster = ? AND price IS NOT NULL",
        [int(cluster)],
    ).fetchdf()["price"]
    if prices.empty:
        raise ValueError(f"No reference prices found for cluster {cluster}")

    return {
        "segment_median_price": float(prices.median()),
        "segment_p25_price": float(prices.quantile(0.25)),
        "segment_p75_price": float(prices.quantile(0.75)),
        "segment_mean_price": float(prices.mean()),
        "price_percentile_in_segment": float((prices <= current_price).mean()),
    }


def analyze_user_listing(user_listing: dict[str, Any]) -> dict[str, Any]:
    listing = build_user_listing_frame(user_listing)
    current_price = float(listing.loc[0, "price"])

    connection = get_connection(read_only=True)
    try:
        model = load_model(connection)
        cluster = int(model.predict(listing[MODEL_FEATURES])[0])
        price_stats = query_segment_prices(connection, cluster, current_price)
    finally:
        connection.close()

    price_vs_segment_median = (
        current_price / price_stats["segment_median_price"] - 1
        if price_stats["segment_median_price"]
        else None
    )
    if current_price < price_stats["segment_p25_price"]:
        price_position = "Below segment range"
    elif current_price > price_stats["segment_p75_price"]:
        price_position = "Above segment range"
    else:
        price_position = "Within segment range"

    return {
        "cluster": cluster,
        "segment_name": SEGMENT_MAP.get(cluster, "Unknown"),
        "current_price": current_price,
        "segment_median_price": price_stats["segment_median_price"],
        "segment_p25_price": price_stats["segment_p25_price"],
        "segment_p75_price": price_stats["segment_p75_price"],
        "segment_mean_price": price_stats["segment_mean_price"],
        "price_vs_segment_median": price_vs_segment_median,
        "price_percentile_in_segment": price_stats["price_percentile_in_segment"],
        "price_position": price_position,
    }
