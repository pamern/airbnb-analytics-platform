"""Lazy, environment-backed MotherDuck resource for Dagster assets."""

from __future__ import annotations

import os
import re
import uuid
import logging
from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import duckdb
import pandas as pd
from dagster import ConfigurableResource

_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")
LOGGER = logging.getLogger(__name__)


def quote_identifier(identifier: str) -> str:
    """Quote one SQL identifier, escaping a literal double quote safely."""
    return '"' + identifier.replace('"', '""') + '"'


def quote_table_name(table_name: str) -> str:
    """Quote a validated one- or two-part table name component by component."""
    if not _TABLE_NAME.fullmatch(table_name):
        raise ValueError(f"Unsafe table name: {table_name}")
    return ".".join(quote_identifier(part) for part in table_name.split("."))


class MotherDuckResource(ConfigurableResource):
    """Open MotherDuck connections only while an asset is executing."""

    database: str = "airbnb_analytics"
    token_env_var: str = "MOTHERDUCK_TOKEN"

    def _connect(self):
        token = os.getenv(self.token_env_var)
        if not token:
            raise RuntimeError(f"{self.token_env_var} must be set before a MotherDuck asset can run")
        return duckdb.connect(f"md:{self.database}?motherduck_token={token}", read_only=False)

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

    def append_dataframe(self, table_name: str, dataframe: pd.DataFrame, *, connection: Any | None = None) -> int:
        """Append by column name after validating the DataFrame against target metadata."""
        if dataframe.empty:
            LOGGER.info("No rows to append to %s", table_name)
            return 0
        quoted_table = quote_table_name(table_name)
        dataframe_columns = list(dataframe.columns)
        if len(dataframe_columns) != len(set(dataframe_columns)):
            raise ValueError(f"Cannot append dataframe to {table_name}. Duplicate dataframe columns: {dataframe_columns}")
        schema_name, target_name = (table_name.split(".", 1) if "." in table_name else ("main", table_name))
        owns_connection = connection is None
        active_connection = connection or self._connect()
        temporary_name = "dagster_frame_" + uuid.uuid4().hex
        try:
            target_schema = active_connection.execute(
                "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
                [schema_name, target_name],
            ).fetchdf()
            if target_schema.empty:
                raise ValueError(f"Cannot append dataframe to {table_name}. Target table was not found in information_schema.")
            target_by_key = {str(column).casefold(): str(column) for column in target_schema["column_name"]}
            unknown = [column for column in dataframe_columns if str(column).casefold() not in target_by_key]
            required = target_schema.loc[target_schema["is_nullable"].eq("NO") & target_schema["column_default"].isna(), "column_name"].tolist()
            present = {str(column).casefold() for column in dataframe_columns}
            missing = [column for column in required if str(column).casefold() not in present]
            if unknown or missing:
                raise ValueError(f"Cannot append dataframe to {table_name}. Missing target columns: {missing}. Unknown dataframe columns: {unknown}. Dataframe columns: {dataframe_columns}. Target schema: {target_schema.loc[:, ['column_name', 'data_type', 'is_nullable']].to_dict(orient='records')}")
            quoted_columns = ", ".join(quote_identifier(column) for column in dataframe_columns)
            quoted_temporary = quote_identifier(temporary_name)
            LOGGER.info("Appending %d rows to %s; dataframe_columns=%s target_columns=%s", len(dataframe), table_name, dataframe_columns, target_schema["column_name"].tolist())
            active_connection.register(temporary_name, dataframe)
            active_connection.execute(f"INSERT INTO {quoted_table} ({quoted_columns}) SELECT {quoted_columns} FROM {quoted_temporary}")
            return len(dataframe)
        finally:
            try:
                active_connection.unregister(temporary_name)
            except Exception:
                pass
            if owns_connection:
                active_connection.close()
