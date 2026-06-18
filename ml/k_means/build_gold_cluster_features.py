"""
Lấy dữ liệu từ Silver để tạo ra bảng Gold phục vụ cho KMeans.

File này chỉ làm:
1. Kết nối database
2. Xác định bảng nguồn Silver
3. Đọc các cột cần thiết
4. Gọi hàm xử lý feature trong feature_utils.py
5. Ghi kết quả ra bảng Gold

Toàn bộ logic clean/lọc/fill median nằm trong feature_utils.py.
"""

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

from ml.k_means.feature_utils import build_gold_cluster_feature_frame  # noqa: E402
from utils.motherduck import connect_duckdb, connect_motherduck  # noqa: E402


SOURCE_TABLE_CANDIDATES = [
    "silver.silver_listings",
    "silver.silver_listings_cleaned",
]

OUTPUT_TABLE = "gold.gold_listing_cluster_features"

READ_COLUMNS = [
    "listing_id",
    "price",
    "room_type",
    "property_type",
    "accommodates",
    "bedrooms",
    "bathrooms",
    "beds",
    "amenities",
    "minimum_nights",
]


def get_connection() -> DuckDBPyConnection:
    target = os.getenv("AIRBNB_DB_TARGET", "local").lower()

    if target == "motherduck":
        if os.getenv("ALLOW_MOTHERDUCK_WRITE") != "1":
            raise RuntimeError("Set ALLOW_MOTHERDUCK_WRITE=1 before writing to MotherDuck.")

        return connect_motherduck(read_only=False)

    return connect_duckdb(PROJECT_ROOT / "airbnb_analytics.duckdb", read_only=False)


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


def resolve_source_table(connection: DuckDBPyConnection) -> str:
    for table_name in SOURCE_TABLE_CANDIDATES:
        if table_exists(connection, table_name):
            return table_name

    raise RuntimeError(f"Cannot find any source table: {SOURCE_TABLE_CANDIDATES}")


def read_silver_listings(connection: DuckDBPyConnection, source_table: str) -> pd.DataFrame:
    column_sql = ", ".join(READ_COLUMNS)

    return connection.execute(
        f"""
        SELECT {column_sql}
        FROM {source_table}
        """
    ).fetchdf()


def write_gold_cluster_features(
    connection: DuckDBPyConnection,
    features: pd.DataFrame,
) -> None:
    connection.execute("CREATE SCHEMA IF NOT EXISTS gold")

    connection.register("gold_cluster_features_df", features)

    connection.execute(
        f"""
        CREATE OR REPLACE TABLE {OUTPUT_TABLE} AS
        SELECT *
        FROM gold_cluster_features_df
        """
    )

    connection.unregister("gold_cluster_features_df")


def build_gold_cluster_features(connection: DuckDBPyConnection) -> pd.DataFrame:
    source_table = resolve_source_table(connection)

    listings_raw = read_silver_listings(
        connection=connection,
        source_table=source_table,
    )

    features = build_gold_cluster_feature_frame(listings_raw)

    write_gold_cluster_features(
        connection=connection,
        features=features,
    )

    return features


def main() -> None:
    connection = get_connection()

    try:
        features = build_gold_cluster_features(connection)

        print(f"Created {OUTPUT_TABLE}")
        print(f"Rows: {len(features):,}")
        print(features.head().to_string(index=False))

    finally:
        connection.close()


if __name__ == "__main__":
    main()