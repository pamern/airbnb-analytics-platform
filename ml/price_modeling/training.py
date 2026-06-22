"""Champion-model construction and fitting."""

from __future__ import annotations

import pandas as pd
from sklearn.pipeline import Pipeline

from ml.price_modeling.config import PriceModelConfig


def build_champion_estimator(config: PriceModelConfig):
    """Create the notebook's accepted XGBoost champion with fixed parameters."""
    if config.champion_algorithm != "XGBRegressor":
        raise ValueError(f"Unsupported champion algorithm: {config.champion_algorithm}")
    from xgboost import XGBRegressor
    return XGBRegressor(objective="reg:squarederror", eval_metric="rmse", tree_method="hist", n_estimators=config.xgb_n_estimators, random_state=config.random_seed, n_jobs=config.n_jobs, **config.best_parameters)


def build_price_pipeline(preprocessor, config: PriceModelConfig) -> Pipeline:
    """Build one fitted-unit-compatible sklearn pipeline."""
    return Pipeline([( "preprocessor", preprocessor), ("model", build_champion_estimator(config))])


def train_price_model(pipeline: Pipeline, X_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    """Fit the supplied complete model pipeline on training data only."""
    return pipeline.fit(X_train, y_train)
