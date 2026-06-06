# -*- coding: utf-8 -*-
"""Helper kết nối MotherDuck/DuckDB."""

from pathlib import Path

import duckdb
from duckdb import DuckDBPyConnection

from configs.settings import MOTHERDUCK, validate_required_settings


def connect_motherduck(read_only: bool = False) -> DuckDBPyConnection:
    """Kết nối MotherDuck bằng token từ biến môi trường."""
    missing = validate_required_settings("motherduck")
    if missing:
        raise ValueError(f"Thiếu biến môi trường cho MotherDuck: {', '.join(missing)}")

    connection_string = f"md:{MOTHERDUCK.database}?motherduck_token={MOTHERDUCK.token}"
    return duckdb.connect(connection_string, read_only=read_only)


def connect_duckdb(database_path: str | Path = ":memory:", read_only: bool = False) -> DuckDBPyConnection:
    """Kết nối DuckDB local, hữu ích cho test nhanh và demo offline."""
    return duckdb.connect(str(database_path), read_only=read_only)


def close_connection(connection: DuckDBPyConnection) -> None:
    """Đóng kết nối DuckDB/MotherDuck."""
    connection.close()
