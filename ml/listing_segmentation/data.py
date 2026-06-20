"""Local-only data loading and validation for listing segmentation."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from ml.listing_segmentation.config import N_CLUSTERS


def load_local_segmentation_data(path: Path) -> pd.DataFrame:
    """Load an explicitly supplied CSV or Parquet file."""
    if not path.is_file():
        raise FileNotFoundError(f"Local segmentation input does not exist: {path}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("Supported local inputs are CSV and Parquet files")


def validate_segmentation_schema(df: pd.DataFrame, required_columns: Sequence[str]) -> None:
    """Validate the existing Gold-compatible feature contract without I/O."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if df.empty:
        raise ValueError("Segmentation input must not be empty")
    duplicates = df.columns[df.columns.duplicated()].tolist()
    if duplicates:
        raise ValueError(f"Input has duplicate columns: {duplicates}")
    missing = sorted(set(required_columns).difference(df.columns))
    if missing:
        raise ValueError(f"Input is missing required columns: {missing}")
    if df["listing_id"].isna().any() or df["listing_id"].duplicated().any():
        raise ValueError("listing_id must be present and unique")
    if df.loc[:, list(required_columns)].isna().any().any():
        raise ValueError("Required segmentation columns contain null values")
    numeric = df.loc[:, list(required_columns)].select_dtypes(include=[np.number])
    if not np.isfinite(numeric.to_numpy()).all():
        raise ValueError("Numeric segmentation features contain NaN or infinity")
    if len(df) < N_CLUSTERS:
        raise ValueError(f"Need at least {N_CLUSTERS} rows for KMeans")
