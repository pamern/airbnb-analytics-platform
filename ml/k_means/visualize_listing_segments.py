"""Visulize lại cluster theo gold + giá"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from duckdb import DuckDBPyConnection

PROJECT_ROOT = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "pyproject.toml").exists()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from configs.paths import ML_OUTPUTS_DIR  # noqa: E402
from utils.motherduck import connect_duckdb, connect_motherduck  # noqa: E402


INPUT_TABLE = "gold.gold_listing_segments"


def get_connection(read_only: bool = True) -> DuckDBPyConnection:
    target = os.getenv("AIRBNB_DB_TARGET", "local").lower()
    if target == "motherduck":
        return connect_motherduck(read_only=read_only)
    return connect_duckdb(PROJECT_ROOT / "airbnb_analytics.duckdb", read_only=read_only)


def load_segments(connection: DuckDBPyConnection) -> pd.DataFrame:
    return connection.execute(f"SELECT * FROM {INPUT_TABLE}").fetchdf()


def build_cluster_summary(segments: pd.DataFrame) -> pd.DataFrame:
    return (
        segments.groupby(["cluster", "segment_name"], dropna=False)
        .agg(
            listing_count=("listing_id", "count"),
            room_type_top=("room_type", lambda series: series.mode().iloc[0]),
            property_base_group_top=("property_base_group", lambda series: series.mode().iloc[0]),
            median_accommodates=("accommodates", "median"),
            median_bedrooms=("bedrooms", "median"),
            median_bathrooms=("bathrooms", "median"),
            median_beds=("beds", "median"),
            median_amenities_count=("amenities_count", "median"),
            median_minimum_nights=("minimum_nights", "median"),
        )
        .reset_index()
        .sort_values("cluster")
    )


def build_cluster_price_summary(segments: pd.DataFrame) -> pd.DataFrame:
    return (
        segments.groupby(["cluster", "segment_name"], dropna=False)
        .agg(
            listing_count=("listing_id", "count"),
            median_price=("price", "median"),
            p25_price=("price", lambda series: series.quantile(0.25)),
            p75_price=("price", lambda series: series.quantile(0.75)),
            mean_price=("price", "mean"),
        )
        .reset_index()
        .sort_values("cluster")
    )


def main() -> None:
    connection = get_connection(read_only=True)
    try:
        segments = load_segments(connection)
    finally:
        connection.close()

    cluster_summary = build_cluster_summary(segments)
    price_summary = build_cluster_price_summary(segments)

    ML_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    cluster_summary.to_csv(ML_OUTPUTS_DIR / "cluster_summary.csv", index=False)
    price_summary.to_csv(ML_OUTPUTS_DIR / "cluster_price_summary.csv", index=False)

    print("Cluster summary")
    print(cluster_summary.to_string(index=False))
    print("\nPrice summary")
    print(price_summary.to_string(index=False))


if __name__ == "__main__":
    main()
