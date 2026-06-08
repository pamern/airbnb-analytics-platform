# -*- coding: utf-8 -*-
"""Load raw CSV vào schema bronze trên MotherDuck."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from duckdb import DuckDBPyConnection

from configs.paths import RAW_CITY_DATA_DIR
import os
from configs.settings import MOTHERDUCK
from utils.logger import get_logger
from utils.motherduck import close_connection, connect_motherduck, connect_duckdb
from utils.sql import query_dataframe


LOGGER = get_logger(__name__)
RAW_CITY_DIR = RAW_CITY_DATA_DIR

BRONZE_TABLES: dict[str, tuple[str, ...]] = {
    "bronze_listings": ("listings.csv", "listings.csv.gz"),
    "bronze_calendar": ("calendar.csv", "calendar.csv.gz"),
    "bronze_reviews": ("reviews.csv", "reviews.csv.gz"),
    "bronze_neighbourhoods": ("neighbourhoods.csv",),
}


def quote_identifier(identifier: str) -> str:
    """Quote tên schema hoặc bảng để tránh ghi nhầm do ký tự đặc biệt."""
    return '"' + identifier.replace('"', '""') + '"'


def resolve_source_file(candidates: tuple[str, ...], raw_dir: Path = RAW_CITY_DIR) -> Path:
    """Chọn file nguồn, ưu tiên .csv và fallback sang .csv.gz nếu cần."""
    for filename in candidates:
        file_path = raw_dir / filename
        if file_path.is_file():
            return file_path

    candidate_text = ", ".join(candidates)
    raise FileNotFoundError(f"Không tìm thấy file nguồn nào trong: {candidate_text}")


def create_schema(connection: DuckDBPyConnection, schema: str) -> None:
    """Tạo schema bronze nếu chưa tồn tại."""
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(schema)}")


def recreate_bronze_table(
    connection: DuckDBPyConnection,
    schema: str,
    table_name: str,
    source_path: Path,
) -> int:
    """Recreate một bảng bronze từ file CSV bằng read_csv_auto."""
    full_table_name = f"{quote_identifier(schema)}.{quote_identifier(table_name)}"
    source = source_path.as_posix().replace("'", "''")

    connection.execute(f"DROP TABLE IF EXISTS {full_table_name}")
    connection.execute(
        f"""
        CREATE TABLE {full_table_name} AS
        SELECT *
        FROM read_csv_auto('{source}', header = true)
        """
    )

    row_count = query_dataframe(
        connection,
        f"SELECT COUNT(*) AS row_count FROM {full_table_name}",
    ).loc[0, "row_count"]
    return int(row_count)


def load_raw_to_bronze(raw_dir: Path = RAW_CITY_DIR) -> None:
    """Load các file raw Bangkok vào đúng schema bronze trên MotherDuck hoặc DuckDB local."""
    token = os.getenv("MOTHERDUCK_TOKEN", "")
    if token.strip() != "":
        LOGGER.info("Phat hien MOTHERDUCK_TOKEN, dang ket noi den MotherDuck...")
        connection = connect_motherduck()
    else:
        local_path = os.getenv("DUCKDB_LOCAL_PATH", "airbnb_analytics.duckdb")
        LOGGER.warning("Khong tim thay MOTHERDUCK_TOKEN, dang fallback ve DuckDB local tai: %s", local_path)
        connection = connect_duckdb(local_path)
    try:
        create_schema(connection, MOTHERDUCK.schema)

        for table_name, candidates in BRONZE_TABLES.items():
            source_path = resolve_source_file(candidates, raw_dir=raw_dir)
            row_count = recreate_bronze_table(
                connection=connection,
                schema=MOTHERDUCK.schema,
                table_name=table_name,
                source_path=source_path,
            )
            LOGGER.info(
                "Đã load %s từ %s vào %s.%s | row count: %s",
                table_name,
                source_path.name,
                MOTHERDUCK.schema,
                table_name,
                row_count,
            )
    finally:
        close_connection(connection)


def main() -> None:
    """Chạy load raw data vào MotherDuck bronze."""
    load_raw_to_bronze()
    LOGGER.info("Load raw data vào MotherDuck bronze hoàn tất.")


if __name__ == "__main__":
    main()
