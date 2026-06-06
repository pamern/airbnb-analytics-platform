# -*- coding: utf-8 -*-
"""Helper chạy SQL trên DuckDB/MotherDuck."""

from pathlib import Path
from typing import Any

import pandas as pd
from duckdb import DuckDBPyConnection


def read_sql_file(path: str | Path) -> str:
    """Đọc nội dung file SQL."""
    return Path(path).read_text(encoding="utf-8")


def execute_sql(
    connection: DuckDBPyConnection,
    sql: str,
    parameters: dict[str, Any] | list[Any] | None = None,
) -> None:
    """Chạy SQL không cần trả về kết quả."""
    if parameters is None:
        connection.execute(sql)
    else:
        connection.execute(sql, parameters)


def query_dataframe(
    connection: DuckDBPyConnection,
    sql: str,
    parameters: dict[str, Any] | list[Any] | None = None,
) -> pd.DataFrame:
    """Chạy SQL và trả về kết quả dạng DataFrame."""
    if parameters is None:
        return connection.execute(sql).fetchdf()
    return connection.execute(sql, parameters).fetchdf()


def execute_sql_file(
    connection: DuckDBPyConnection,
    path: str | Path,
    parameters: dict[str, Any] | list[Any] | None = None,
) -> None:
    """Đọc và chạy một file SQL."""
    execute_sql(connection, read_sql_file(path), parameters=parameters)
