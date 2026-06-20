"""High-level local entry points for price-model training, evaluation and inference."""

from __future__ import annotations

import argparse
import logging
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from ml.common.artifact_manager import create_versioned_artifact_dir, save_model_artifact, write_json
from ml.common.run_metadata import build_model_metric_records, build_model_registry_record, build_training_run_record
from ml.price_modeling.config import PriceModelConfig, TrainingMode
from ml.price_modeling.data import load_local_price_data, validate_input_schema
from ml.price_modeling.error_analysis import build_prediction_error_frame
from ml.price_modeling.evaluation import build_metrics_long_format, evaluate_regression_model
from ml.price_modeling.explainability import calculate_native_importance
from ml.price_modeling.prediction import predict_price
from ml.price_modeling.preprocessing import build_preprocessor, prepare_modeling_frame, split_train_test
from ml.price_modeling.training import build_price_pipeline, train_price_model
from ml.price_modeling.tuning import tune_model

LOGGER = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    """Outputs from one local training run, with no warehouse side effects."""

    model: object
    model_version: str
    metrics: dict[str, float]
    artifact_paths: dict[str, Path]
    predictions: pd.DataFrame
    metric_records: pd.DataFrame
    run: dict[str, object]
    registry: dict[str, object]


def _new_version() -> str:
    return "price_v" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def _write_analysis_outputs(config: PriceModelConfig, version: str, predictions: pd.DataFrame, importance: pd.DataFrame | None) -> None:
    """Write new analysis outputs without changing historical files."""
    root = Path(config.output_root)
    error_path = root / "error_analysis" / f"{version}_prediction_errors.csv"
    error_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(error_path, index=False)
    if importance is not None:
        importance_path = root / "explainability" / f"{version}_native_importance.csv"
        importance_path.parent.mkdir(parents=True, exist_ok=True)
        importance.to_csv(importance_path, index=False)


def run_price_training_pipeline(data: pd.DataFrame, config: PriceModelConfig | None = None, training_mode: TrainingMode | None = None) -> TrainingResult:
    """Train locally from a caller-supplied frame; never connects to a warehouse."""
    config = config or PriceModelConfig(); mode = training_mode or config.training_mode
    if mode not in {"retrain", "tune", "research"}: raise ValueError(f"Unsupported training mode: {mode}")
    required = [config.price_column, *[feature for feature in config.selected_features if feature != "property_base_group"]]
    if "property_base_group" in config.selected_features and "property_base_group" not in data.columns:
        required.append("property_type")
    validate_input_schema(data, required)
    frame = prepare_modeling_frame(data, price_column=config.price_column, target_column=config.target_column)
    if frame.empty: raise ValueError("No positive-price rows remain after target preparation")
    X_train, X_test, y_train, y_test, meta_train, meta_test = split_train_test(frame, config.selected_features, target_column=config.target_column, test_size=config.test_size, random_seed=config.random_seed)
    effective_config = config
    tuning_trials: pd.DataFrame | None = None
    if mode == "tune":
        params, score, tuning_trials = tune_model(X_train, y_train, config)
        effective_config = PriceModelConfig(**{**asdict(config), "best_parameters": params})
        LOGGER.info("Tuning completed with train-only CV RMSE %.6f", score)
    preprocessor = build_preprocessor(effective_config.selected_features)
    model = train_price_model(build_price_pipeline(preprocessor, effective_config), X_train, y_train)
    metrics, predicted_log = evaluate_regression_model(model, X_test, y_test)
    version = _new_version(); artifact_dir = create_versioned_artifact_dir(Path(effective_config.artifact_root), version)
    model_path = save_model_artifact(model, artifact_dir)
    feature_schema_path = write_json(artifact_dir / "feature_schema.json", {"features": list(effective_config.selected_features), "target_column": effective_config.target_column, "feature_set_version": effective_config.feature_set_version})
    config_path = write_json(artifact_dir / "training_config.json", asdict(effective_config))
    metrics_path = write_json(artifact_dir / "metrics.json", metrics)
    prediction_inputs = X_test.reset_index(drop=True).join(meta_test.reset_index(drop=True), rsuffix="_metadata")
    errors = build_prediction_error_frame(prediction_inputs, y_test.reset_index(drop=True), predicted_log)
    importance = calculate_native_importance(model) if effective_config.run_explainability else None
    if effective_config.run_error_analysis or effective_config.run_explainability:
        _write_analysis_outputs(effective_config, version, errors, importance)
    if tuning_trials is not None:
        trials_path = Path(effective_config.output_root) / "csv" / f"{version}_xgb_optuna_trials.csv"; trials_path.parent.mkdir(parents=True, exist_ok=True); tuning_trials.to_csv(trials_path, index=False)
    metric_records = build_metrics_long_format(metrics, model_version=version, dataset_type="test")
    run_id = version.removeprefix("price_v")
    run = build_training_run_record(run_id=run_id, model_version=version, training_mode=mode, model_name=effective_config.champion_algorithm, status="success")
    registry = build_model_registry_record(model_version=version, model_name=effective_config.champion_algorithm, artifact_path=str(model_path))
    LOGGER.info("Price training succeeded run=%s version=%s rows=%d features=%d rmse=%.6f artifact=%s", run_id, version, len(frame), len(effective_config.selected_features), metrics["rmse"], model_path)
    return TrainingResult(model=model, model_version=version, metrics=metrics, artifact_paths={"model": model_path, "feature_schema": feature_schema_path, "training_config": config_path, "metrics": metrics_path}, predictions=errors, metric_records=metric_records, run=run, registry=registry)


def run_price_evaluation_pipeline(model: object, data: pd.DataFrame, config: PriceModelConfig | None = None) -> tuple[dict[str, float], pd.DataFrame]:
    """Evaluate an existing fitted pipeline against a caller-supplied local frame."""
    config = config or PriceModelConfig(); validate_input_schema(data, [config.price_column, *config.selected_features])
    frame = prepare_modeling_frame(data, price_column=config.price_column, target_column=config.target_column)
    metrics, predicted = evaluate_regression_model(model, frame.loc[:, list(config.selected_features)], frame[config.target_column])
    return metrics, pd.DataFrame({"actual_log_price": frame[config.target_column], "predicted_log_price": predicted})


def run_price_prediction_pipeline(model: object, data: dict[str, object] | pd.DataFrame, config: PriceModelConfig | None = None) -> pd.DataFrame:
    """Generate local predictions using the configured selected feature schema."""
    config = config or PriceModelConfig()
    return predict_price(model, data, config.selected_features)


def _synthetic_data(rows: int = 80) -> pd.DataFrame:
    """Create a schema-compatible frame for the isolated CLI smoke test."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({"price": rng.uniform(500, 3000, rows), "neighbourhood": rng.choice(["Sukhumvit", "Silom", "Sathon"], rows), "property_type": "Apartment", "room_type": rng.choice(["Entire home/apt", "Private room"], rows), "host_response_time": "within an hour", "bedrooms": rng.integers(1, 4, rows), "bathrooms": rng.uniform(1, 3, rows), "accommodates": rng.integers(1, 7, rows), "review_scores_location": rng.uniform(3, 5, rows), "host_response_rate": rng.uniform(50, 100, rows), "host_listings_count": rng.integers(1, 10, rows), "calculated_host_listings_count": rng.integers(1, 10, rows), "host_total_listings_count": rng.integers(1, 10, rows), "host_acceptance_rate": rng.uniform(50, 100, rows), "number_of_reviews_ltm": rng.integers(0, 30, rows), "minimum_nights": rng.integers(1, 10, rows)})


def main() -> None:
    """Run the explicit local CSV or synthetic smoke-test CLI."""
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path); parser.add_argument("--mode", choices=["retrain", "tune", "research"], default="retrain"); parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args(); logging.basicConfig(level=logging.INFO)
    if not args.smoke_test and args.input is None: parser.error("--input is required unless --smoke-test is used")
    if args.smoke_test:
        with tempfile.TemporaryDirectory() as directory:
            smoke_config = PriceModelConfig(artifact_root=directory, output_root=directory, xgb_n_estimators=10, n_jobs=1, run_error_analysis=False, run_explainability=False)
            result = run_price_training_pipeline(_synthetic_data(), smoke_config, training_mode=args.mode)
    else:
        result = run_price_training_pipeline(load_local_price_data(args.input), training_mode=args.mode)
    print(f"Training complete: {result.model_version}; RMSE={result.metrics['rmse']:.6f}")


if __name__ == "__main__":
    main()
