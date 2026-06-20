"""Regression evaluation helpers."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold


def _rmse(y_true: pd.Series | np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate root mean squared error across sklearn versions."""
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def evaluate_regression_model(model: Any, X_test: pd.DataFrame, y_test: pd.Series) -> tuple[dict[str, float], np.ndarray]:
    """Predict once on held-out data and calculate supported metrics."""
    started = time.perf_counter(); predictions = model.predict(X_test); predict_time = time.perf_counter() - started
    n_features = model.named_steps["preprocessor"].transform(X_test).shape[1]
    r2 = float(r2_score(y_test, predictions)); n = len(y_test)
    adjusted = float("nan") if n <= n_features + 1 else 1 - (1 - r2) * (n - 1) / (n - n_features - 1)
    return {"rmse": _rmse(y_test, predictions), "mae": float(mean_absolute_error(y_test, predictions)), "r2": r2, "adjusted_r2": adjusted, "predict_time_seconds": predict_time}, np.asarray(predictions)


def cross_validate_model(model: Any, X_train: pd.DataFrame, y_train: pd.Series, *, n_splits: int, random_seed: int) -> pd.DataFrame:
    """Run train-only K-fold validation, fitting preprocessing within each fold."""
    rows: list[dict[str, float | int]] = []
    cv = KFold(n_splits=n_splits, shuffle=True, random_state=random_seed)
    for fold, (train_index, validation_index) in enumerate(cv.split(X_train), 1):
        fitted = clone(model); started = time.perf_counter()
        fitted.fit(X_train.iloc[train_index], y_train.iloc[train_index]); fit_time = time.perf_counter() - started
        metrics, _ = evaluate_regression_model(fitted, X_train.iloc[validation_index], y_train.iloc[validation_index])
        rows.append({"fold": fold, "fit_time_seconds": fit_time, **metrics})
    return pd.DataFrame(rows)


def build_metrics_long_format(metrics: dict[str, float], *, model_version: str, dataset_type: str, metric_std: dict[str, float] | None = None) -> pd.DataFrame:
    """Represent scalar metrics using the standard local long schema."""
    evaluated_at = datetime.now(timezone.utc).isoformat()
    return pd.DataFrame([{ "model_version": model_version, "dataset_type": dataset_type, "metric_name": key, "metric_value": value, "metric_std": (metric_std or {}).get(key), "evaluated_at": evaluated_at } for key, value in metrics.items()])
