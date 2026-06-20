"""Lazy, environment-backed MotherDuck resource for Dagster assets."""

from __future__ import annotations

import os
import re
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import duckdb
import pandas as pd
from dagster import ConfigurableResource

_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


class MotherDuckResource(ConfigurableResource):
    """Open MotherDuck connections only while an asset is executing."""

    database: str = "airbnb_analytics"
    token_env_var: str = "MOTHERDUCK_TOKEN"

    def _connect(self):
        token = os.getenv(self.token_env_var)
        if not token:
            raise RuntimeError(f"{self.token_env_var} must be set before a MotherDuck asset can run")
        return duckdb.connect(f"md:{self.database}?motherduck_token={token}")

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        """Yield a connection with commit/rollback semantics."""
        connection = self._connect()
        try:
            connection.execute("BEGIN TRANSACTION")
            yield connection
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def query_df(self, sql: str, parameters: Sequence[Any] | None = None) -> pd.DataFrame:
        """Execute a query and return its results as a DataFrame."""
        with self._connect() as connection:
            return connection.execute(sql, parameters or []).fetchdf()

    def execute(self, sql: str, parameters: Sequence[Any] | None = None) -> None:
        """Execute one statement without returning rows."""
        with self._connect() as connection:
            connection.execute(sql, parameters or [])

    def append_dataframe(self, table_name: str, dataframe: pd.DataFrame, *, connection: Any | None = None) -> None:
        """Append a non-empty DataFrame to a validated schema-qualified table."""
        if dataframe.empty:
            raise ValueError(f"Refusing to append an empty DataFrame to {table_name}")
        if not _TABLE_NAME.fullmatch(table_name):
            raise ValueError(f"Unsafe table name: {table_name}")
        owns_connection = connection is None
        active_connection = connection or self._connect()
        temporary_name = "dagster_frame_" + uuid.uuid4().hex
        try:
            active_connection.register(temporary_name, dataframe)
            active_connection.execute(f"INSERT INTO {table_name} SELECT * FROM {temporary_name}")
        finally:
            try:
                active_connection.unregister(temporary_name)
            except Exception:
                pass
            if owns_connection:
                active_connection.close()
