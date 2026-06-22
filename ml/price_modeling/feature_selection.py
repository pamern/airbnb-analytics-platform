"""Research-only feature selection retaining the notebook acceptance rule."""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from ml.price_modeling.evaluation import cross_validate_model


def evaluate_feature_subset(model, X_train: pd.DataFrame, y_train: pd.Series, features: Sequence[str], *, n_splits: int, random_seed: int) -> pd.DataFrame:
    """Evaluate a supplied feature subset with train-only CV RMSE."""
    return cross_validate_model(model, X_train.loc[:, list(features)], y_train, n_splits=n_splits, random_seed=random_seed)


def select_accepted_feature_set(summary: pd.DataFrame, *, max_rmse_degradation_pct: float = 0.01) -> list[str]:
    """Select the smallest eligible subset within 1% of Full-set RMSE."""
    full = summary.loc[summary["feature_set"].eq("Full")]
    if full.empty: raise ValueError("Feature-selection summary requires a Full feature set")
    threshold = float(full.iloc[0]["rmse_mean"]) * (1 + max_rmse_degradation_pct)
    eligible = summary.loc[summary["rmse_mean"].le(threshold)].sort_values(["n_features", "rmse_mean"])
    if eligible.empty: return list(full.iloc[0]["features"])
    return list(eligible.iloc[0]["features"])


def run_feature_selection(candidate_sets: dict[str, Sequence[str]], model_factory, X_train: pd.DataFrame, y_train: pd.Series, *, n_splits: int, random_seed: int) -> tuple[list[str], pd.DataFrame]:
    """Evaluate caller-supplied subsets and apply the existing 1% acceptance criterion."""
    rows = []
    for name, features in candidate_sets.items():
        folds = evaluate_feature_subset(model_factory(features), X_train, y_train, features, n_splits=n_splits, random_seed=random_seed)
        rows.append({"feature_set": name, "features": list(features), "n_features": len(features), "rmse_mean": folds["rmse"].mean(), "rmse_std": folds["rmse"].std()})
    summary = pd.DataFrame(rows)
    return select_accepted_feature_set(summary), summary
