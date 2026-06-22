"""Local-only input loading and schema validation for price modeling."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pandas as pd


def load_local_price_data(path: Path) -> pd.DataFrame:
    """Load a CSV or Parquet input explicitly supplied by the caller."""
    if not path.is_file():
        raise FileNotFoundError(f"Local input file does not exist: {path}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("Supported local inputs are CSV and Parquet files")


def validate_input_schema(df: pd.DataFrame, required_columns: Sequence[str]) -> None:
    """Validate a non-empty frame with unique names and required columns."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if df.empty:
        raise ValueError("Input DataFrame must not be empty")
    duplicates = df.columns[df.columns.duplicated()].tolist()
    if duplicates:
        raise ValueError(f"Input has duplicate columns: {duplicates}")
    missing = sorted(set(required_columns).difference(df.columns))
    if missing:
        raise ValueError(f"Input is missing required columns: {missing}")
