"""Leakage-safe split conformal intervals for price-model predictions."""

from __future__ import annotations

import numpy as np


def compute_conformal_quantile(
    actual_price: np.ndarray,
    predicted_price: np.ndarray,
    coverage: float = 0.90,
) -> float:
    """Return the finite-sample corrected absolute-residual quantile."""
    if not 0 < coverage < 1:
        raise ValueError("coverage must be strictly between 0 and 1")
    actual = np.asarray(actual_price, dtype=float).reshape(-1)
    predicted = np.asarray(predicted_price, dtype=float).reshape(-1)
    if actual.size != predicted.size:
        raise ValueError("actual_price and predicted_price must have equal length")
    scores = np.abs(actual - predicted)
    scores = scores[np.isfinite(scores)]
    if scores.size == 0:
        raise ValueError("calibration scores must contain at least one finite value")
    level = min(float(np.ceil((scores.size + 1) * coverage) / scores.size), 1.0)
    try:
        result = float(np.quantile(scores, level, method="higher"))
    except TypeError:  # NumPy < 1.22
        result = float(np.quantile(scores, level, interpolation="higher"))
    if not np.isfinite(result) or result < 0:
        raise ValueError("conformal quantile must be finite and non-negative")
    return result


def build_prediction_interval(predicted_price: np.ndarray | float, q_hat: float) -> tuple[np.ndarray, np.ndarray]:
    """Build non-negative symmetric intervals on the original price scale."""
    prediction = np.asarray(predicted_price, dtype=float)
    if not np.isfinite(prediction).all() or (prediction < 0).any():
        raise ValueError("predicted_price must be finite and non-negative")
    if not np.isfinite(q_hat) or q_hat < 0:
        raise ValueError("q_hat must be finite and non-negative")
    return np.maximum(0.0, prediction - q_hat), prediction + q_hat
