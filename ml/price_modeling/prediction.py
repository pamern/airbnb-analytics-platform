"""Local prediction API for a future Streamlit consumer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd


def load_price_model(path: Path) -> Any:
    """Load a locally persisted price-model pipeline."""
    if not path.is_file(): raise FileNotFoundError(f"Model artifact does not exist: {path}")
    model = joblib.load(path)
    if not hasattr(model, "predict"): raise ValueError("Artifact does not contain a fitted predictive model")
    return model


def validate_prediction_input(data: dict[str, object] | pd.DataFrame, required_features: Sequence[str]) -> pd.DataFrame:
    """Normalize one or more records and validate required raw feature columns."""
    frame = pd.DataFrame([data]) if isinstance(data, dict) else data.copy()
    if frame.empty: raise ValueError("Prediction input must contain at least one record")
    missing = sorted(set(required_features).difference(frame.columns))
    if missing: raise ValueError(f"Prediction input is missing features: {missing}")
    return frame.loc[:, list(required_features)]


def predict_price(model: Any, data: dict[str, object] | pd.DataFrame, required_features: Sequence[str]) -> pd.DataFrame:
    """Predict log-price and safely return the matching original-price estimate."""
    frame = validate_prediction_input(data, required_features); log_values = np.asarray(model.predict(frame), dtype=float)
    if not np.isfinite(log_values).all(): raise ValueError("Model produced non-finite log-price predictions")
    prices = np.expm1(log_values)
    if not np.isfinite(prices).all() or (prices < 0).any(): raise ValueError("Model produced invalid price predictions")
    return pd.DataFrame({"predicted_log_price": log_values, "predicted_price": prices}, index=frame.index)
