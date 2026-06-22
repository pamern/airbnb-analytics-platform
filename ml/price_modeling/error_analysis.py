"""Prediction-error frames and grouped summaries."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_prediction_error_frame(metadata: pd.DataFrame, actual_log_price: pd.Series, predicted_log_price: np.ndarray) -> pd.DataFrame:
    """Build listing-level errors with safe log-price inversion."""
    actual = np.expm1(actual_log_price.to_numpy()); predicted = np.maximum(np.expm1(predicted_log_price), 0)
    frame = metadata.reset_index(drop=True).copy(); frame["actual_log_price"] = actual_log_price.to_numpy(); frame["predicted_log_price"] = predicted_log_price
    frame["actual_price"] = actual; frame["predicted_price"] = predicted; frame["residual"] = actual - predicted; frame["absolute_error"] = np.abs(frame["residual"])
    frame["percentage_error"] = np.where(actual > 0, frame["absolute_error"] / actual * 100, np.nan)
    frame["error_direction"] = np.where(frame["residual"] >= 0, "underprediction", "overprediction")
    return frame


def summarize_errors_by_group(errors: pd.DataFrame, group_column: str) -> pd.DataFrame:
    """Summarize errors for a categorical grouping that exists in the frame."""
    if group_column not in errors:
        raise ValueError(f"Missing error-analysis group column: {group_column}")
    return errors.groupby(group_column, dropna=False).agg(listing_count=("absolute_error", "size"), mae=("absolute_error", "mean"), mean_residual=("residual", "mean"), mean_percentage_error=("percentage_error", "mean")).reset_index()
