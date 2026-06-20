"""Optuna tuning for the accepted XGBoost champion only."""

from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.model_selection import KFold

from ml.price_modeling.config import PriceModelConfig
from ml.price_modeling.evaluation import _rmse
from ml.price_modeling.preprocessing import build_preprocessor
from ml.price_modeling.training import build_champion_estimator


def build_optuna_objective(X_train: pd.DataFrame, y_train: pd.Series, config: PriceModelConfig):
    """Build a train-only CV objective using the existing XGBoost search space."""
    import optuna
    cv = KFold(n_splits=config.n_splits, shuffle=True, random_state=config.random_seed)
    def objective(trial: optuna.Trial) -> float:
        params = {"learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True), "max_depth": trial.suggest_int("max_depth", 3, 10), "min_child_weight": trial.suggest_int("min_child_weight", 1, 15), "subsample": trial.suggest_float("subsample", 0.60, 1.00), "colsample_bytree": trial.suggest_float("colsample_bytree", 0.60, 1.00), "gamma": trial.suggest_float("gamma", 0.0, 5.0), "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True), "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 20.0, log=True)}
        scores = []
        for fold, (train_idx, valid_idx) in enumerate(cv.split(X_train), 1):
            preprocessor = build_preprocessor(config.selected_features); estimator = build_champion_estimator(config.__class__(**{**config.__dict__, "best_parameters": params}))
            transformed_train = preprocessor.fit_transform(X_train.iloc[train_idx]); transformed_valid = preprocessor.transform(X_train.iloc[valid_idx])
            estimator.fit(transformed_train, y_train.iloc[train_idx]); scores.append(_rmse(y_train.iloc[valid_idx], estimator.predict(transformed_valid)))
            trial.report(sum(scores) / len(scores), fold)
            if trial.should_prune(): raise optuna.TrialPruned()
        return float(sum(scores) / len(scores))
    return objective


def tune_model(X_train: pd.DataFrame, y_train: pd.Series, config: PriceModelConfig, *, n_trials: int = 30) -> tuple[dict[str, Any], float, pd.DataFrame]:
    """Tune only XGBRegressor and return parameters, CV RMSE and trials."""
    import optuna
    if config.champion_algorithm != "XGBRegressor": raise ValueError("Only the accepted XGBRegressor champion can be tuned")
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=config.random_seed), pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=2))
    study.optimize(build_optuna_objective(X_train, y_train, config), n_trials=n_trials, n_jobs=1)
    trials = pd.DataFrame([{ "trial_number": trial.number, "state": trial.state.name, "value": trial.value, **trial.params } for trial in study.trials])
    return study.best_params, float(study.best_value), trials
