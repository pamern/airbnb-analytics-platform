# -*- coding: utf-8 -*-
"""Helper kết nối MotherDuck/DuckDB."""

from pathlib import Path
import threading
import duckdb
from duckdb import DuckDBPyConnection

from configs.settings import MOTHERDUCK, validate_required_settings

_shared_connection = None
_lock = threading.Lock()

def connect_motherduck(read_only: bool = False) -> DuckDBPyConnection:
    """Kết nối MotherDuck bằng token từ biến môi trường."""
    global _shared_connection
    missing = validate_required_settings("motherduck")
    if missing:
        raise ValueError(f"Thiếu biến môi trường cho MotherDuck: {', '.join(missing)}")

    with _lock:
        if _shared_connection is not None:
            try:
                # Kiểm tra kết nối còn sống không
                _shared_connection.execute("SELECT 1")
            except Exception:
                _shared_connection = None

        if _shared_connection is None:
            connection_string = f"md:{MOTHERDUCK.database}?motherduck_token={MOTHERDUCK.token}"
            # Luôn dùng cùng một cấu hình cho connection chính để tránh conflict cấu hình
            _shared_connection = duckdb.connect(connection_string, read_only=False)

        return _shared_connection.cursor()


def connect_duckdb(database_path: str | Path = ":memory:", read_only: bool = False) -> DuckDBPyConnection:
    """Kết nối DuckDB local, hữu ích cho test nhanh và demo offline."""
    return duckdb.connect(str(database_path), read_only=read_only)


def close_connection(connection: DuckDBPyConnection) -> None:
    """Đóng kết nối DuckDB/MotherDuck."""
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass

