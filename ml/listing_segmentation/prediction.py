"""Local cluster-assignment API for fitted segmentation artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import joblib
import pandas as pd

from ml.listing_segmentation.profiles import build_cluster_assignments


def load_segmentation_model(path: Path) -> Any:
    """Load a locally persisted segmentation pipeline."""
    if not path.is_file():
        raise FileNotFoundError(f"Segmentation artifact does not exist: {path}")
    model = joblib.load(path)
    if not hasattr(model, "predict"):
        raise ValueError("Artifact does not contain a predictive segmentation model")
    return model


def validate_segmentation_input(data: dict[str, object] | pd.DataFrame, required_features: Sequence[str]) -> pd.DataFrame:
    """Normalize assignment input and validate the required raw schema."""
    frame = pd.DataFrame([data]) if isinstance(data, dict) else data.copy()
    required = ["listing_id", *required_features]
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"Assignment input is missing columns: {missing}")
    return frame


def assign_clusters(model: Any, data: dict[str, object] | pd.DataFrame, *, required_features: Sequence[str], model_version: str) -> pd.DataFrame:
    """Assign stable clusters without fitting or any database interaction."""
    frame = validate_segmentation_input(data, required_features)
    return build_cluster_assignments(model, frame, model_version=model_version)
