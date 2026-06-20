"""Lightweight model importance helpers."""

from __future__ import annotations

import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.pipeline import Pipeline


def calculate_native_importance(model: Pipeline) -> pd.DataFrame:
    """Return native XGBoost importance aligned with transformed feature names."""
    estimator = model.named_steps["model"]; names = model.named_steps["preprocessor"].get_feature_names_out()
    importance = getattr(estimator, "feature_importances_", None)
    if importance is None: raise ValueError("Estimator has no native feature importance")
    return pd.DataFrame({"feature": names, "importance": importance}).sort_values("importance", ascending=False).reset_index(drop=True)


def calculate_permutation_importance(model: Pipeline, X: pd.DataFrame, y: pd.Series, *, random_seed: int, n_repeats: int = 5) -> pd.DataFrame:
    """Calculate raw-feature permutation importance without writing output."""
    result = permutation_importance(model, X, y, scoring="neg_root_mean_squared_error", n_repeats=n_repeats, random_state=random_seed)
    return pd.DataFrame({"feature": X.columns, "importance_mean": result.importances_mean, "importance_std": result.importances_std}).sort_values("importance_mean", ascending=False).reset_index(drop=True)
