"""Thin Dagster assets that call existing ML entry points and persist their results."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from dagster import AssetKey, asset

from ml.price_modeling.pipeline import TrainingResult as PriceTrainingResult
from ml.price_modeling.pipeline import run_price_training_pipeline
from ml.listing_segmentation.pipeline import TrainingResult as SegmentationTrainingResult
from ml.listing_segmentation.pipeline import run_segmentation_training_pipeline
from orchestration.resources.motherduck import MotherDuckResource
from orchestration.mlops import (
    PRICE_MODEL_NAME,
    PRICE_PREDICTIONS_TABLE,
    SEGMENT_ASSIGNMENTS_TABLE,
    SEGMENT_PROFILES_TABLE,
    SEGMENTATION_MODEL_NAME,
    ensure_mlops_tables,
)
from ml.common.paths import REPO_ROOT

PRICE_TABLE = "gold.gold_price_model_features"
SEGMENTATION_TABLE = "gold.gold_cluster_model_features"


@asset(deps=[AssetKey(["gold", "gold_price_model_features"])], group_name="price")
def price_training_result(context, motherduck: MotherDuckResource) -> PriceTrainingResult:
    """Read Gold price features and invoke champion-only ML retraining."""
    data = motherduck.query_df(f"SELECT * FROM {PRICE_TABLE}")
    if data.empty:
        raise ValueError("gold_price_model_features is empty")
    result = run_price_training_pipeline(data=data, training_mode="retrain")
    context.log.info("Price training run=%s version=%s rows=%d rmse=%s", result.run["run_id"], result.model_version, len(data), result.metrics["rmse"])
    return result


@asset(deps=[AssetKey(["gold", "gold_cluster_model_features"])], group_name="segmentation")
def segmentation_training_result(context, motherduck: MotherDuckResource) -> SegmentationTrainingResult:
    """Read Gold segmentation features and invoke the unchanged KMeans pipeline."""
    data = motherduck.query_df(f"SELECT * FROM {SEGMENTATION_TABLE}")
    if data.empty:
        raise ValueError("gold_cluster_model_features is empty")
    result = run_segmentation_training_pipeline(data=data)
    context.log.info("Segmentation training run=%s version=%s rows=%d silhouette=%s", result.run["run_id"], result.model_version, len(data), result.metrics.get("silhouette_score"))
    return result


@asset(group_name="price")
def price_model_artifact(price_training_result: PriceTrainingResult) -> dict[str, str]:
    """Verify that the ML-owned price artifact exists and can be loaded."""
    path = price_training_result.artifact_paths["model"]
    if not path.is_file() or not hasattr(joblib.load(path), "predict"):
        raise RuntimeError(f"Price artifact is unavailable or invalid: {path}")
    return {"model_version": price_training_result.model_version, "artifact_path": str(path)}


@asset(group_name="segmentation")
def segmentation_model_artifact(segmentation_training_result: SegmentationTrainingResult) -> dict[str, str]:
    """Verify that the ML-owned segmentation artifact exists and can be loaded."""
    path = segmentation_training_result.artifact_paths["model"]
    if not path.is_file() or not hasattr(joblib.load(path), "predict"):
        raise RuntimeError(f"Segmentation artifact is unavailable or invalid: {path}")
    return {"model_version": segmentation_training_result.model_version, "artifact_path": str(path)}


def _ensure_ml_tables(connection: Any) -> None:
    """Compatibility wrapper for assets that need the new MLOps schema."""
    ensure_mlops_tables(connection)


def _relative_artifact_path(path: Path) -> str:
    """Registry paths are portable project-relative paths, never machine-specific paths."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError as error:
        raise ValueError(f"Artifact must be inside the repository: {path}") from error


_SHAP_IMPORTANCE_COLUMNS = ["run_id", "model_name", "model_version", "feature_name", "source_feature", "feature_level", "importance_value", "importance_rank", "importance_method", "created_at"]


def _prepare_shap_importance_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """Select and validate SHAP rows before they cross the DuckDB write boundary."""
    missing = sorted(set(_SHAP_IMPORTANCE_COLUMNS).difference(rows.columns))
    if missing:
        raise ValueError(f"Missing SHAP importance columns: {missing}")
    prepared = rows.loc[:, _SHAP_IMPORTANCE_COLUMNS].copy()
    try:
        prepared["importance_value"] = pd.to_numeric(prepared["importance_value"], errors="raise")
        prepared["importance_rank"] = pd.to_numeric(prepared["importance_rank"], errors="raise").astype("int64")
        prepared["created_at"] = pd.to_datetime(prepared["created_at"], errors="raise", utc=True)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid SHAP importance dtype: {error}") from error
    if prepared[["run_id", "model_name", "model_version", "feature_name", "source_feature", "feature_level", "importance_method"]].isna().any().any() or prepared[["importance_value", "importance_rank", "created_at"]].isna().any().any():
        raise ValueError("SHAP importance contains null values required by mlops.model_feature_importance")
    if not np.isfinite(prepared["importance_value"].to_numpy()).all() or (prepared["importance_value"] < 0).any():
        raise ValueError("SHAP importance_value must contain finite non-negative numbers")
    return prepared


def _write_registry(motherduck: MotherDuckResource, result: Any, model_name: str, run_type: str, importance: pd.DataFrame | None = None) -> int:
    now = datetime.now(timezone.utc)
    artifact_path = _relative_artifact_path(result.artifact_paths["model"])
    run = pd.DataFrame([{"run_id": result.run["run_id"], "job_name": f"{model_name}_retraining_job", "model_name": model_name, "model_version": result.model_version, "run_type": run_type, "status": "SUCCESS", "feature_snapshot": None, "started_at": result.run["started_at"], "completed_at": now, "artifact_path": artifact_path, "error_message": None, "created_at": now}])
    registry = pd.DataFrame([{"model_name": model_name, "model_version": result.model_version, "run_id": result.run["run_id"], "stage": "CANDIDATE", "is_active": False, "artifact_path": artifact_path, "preprocessor_path": artifact_path, "created_at": now, "promoted_at": None, "promoted_by": None}])
    metrics = result.metric_records.rename(columns={"dataset_type": "dataset_split", "evaluated_at": "created_at"}).copy()
    metrics.insert(0, "run_id", result.run["run_id"]); metrics.insert(1, "model_name", model_name)
    metrics = metrics.loc[:, ["run_id", "model_name", "model_version", "metric_name", "metric_value", "dataset_split", "created_at"]]
    with motherduck.transaction() as connection:
        _ensure_ml_tables(connection)
        motherduck.append_dataframe("mlops.model_runs", run, connection=connection)
        motherduck.append_dataframe("mlops.model_registry", registry, connection=connection)
        motherduck.append_dataframe("mlops.model_metrics", metrics, connection=connection)
        if importance is not None and not importance.empty:
            required_importance = {"feature_name", "source_feature", "feature_level", "importance_value", "importance_rank"}
            missing = sorted(required_importance.difference(importance.columns))
            if missing:
                raise ValueError(f"SHAP importance is missing columns: {missing}")
            rows = importance.copy()
            if rows.duplicated(["feature_name", "feature_level"]).any() or not (rows["importance_value"] >= 0).all():
                raise ValueError("SHAP importance contains duplicate keys or invalid values")
            rows["run_id"] = result.run["run_id"]; rows["model_name"] = model_name; rows["model_version"] = result.model_version; rows["importance_method"] = "shap"; rows["created_at"] = now
            motherduck.append_dataframe("mlops.model_feature_importance", _prepare_shap_importance_rows(rows), connection=connection)
    return len(metrics)


@asset(group_name="price")
def price_registry_records(context, price_training_result: PriceTrainingResult, motherduck: MotherDuckResource) -> int:
    """Append price MLOps records transactionally; registration remains CANDIDATE."""
    count = _write_registry(motherduck, price_training_result, PRICE_MODEL_NAME, "TRAINING", price_training_result.shap_importance)
    context.log.info("Wrote %d price metric records", count)
    return count


@asset(group_name="segmentation")
def segmentation_registry_records(context, segmentation_training_result: SegmentationTrainingResult, motherduck: MotherDuckResource) -> int:
    """Append segmentation MLOps records transactionally; registration remains CANDIDATE."""
    count = _write_registry(motherduck, segmentation_training_result, SEGMENTATION_MODEL_NAME, "SEGMENTATION_TRAINING")
    context.log.info("Wrote %d segmentation metric records", count)
    return count


@asset(group_name="price")
def gold_price_predictions(context, price_training_result: PriceTrainingResult, price_registry_records: int, motherduck: MotherDuckResource) -> int:
    """Append held-out price predictions for the newly trained model version."""
    predictions = price_training_result.predictions.copy()
    required = ["listing_id", "actual_price", "predicted_price", "actual_log_price", "predicted_log_price", "residual", "absolute_error"]
    missing = sorted(set(required).difference(predictions.columns))
    if missing:
        raise ValueError(f"Price predictions are missing columns: {missing}")
    output = predictions.loc[:, required].copy(); output.insert(0, "model_version", price_training_result.model_version); output.insert(1, "run_id", price_training_result.run["run_id"]); output["feature_hash"] = output["listing_id"].map(motherduck.query_df(f"SELECT listing_id, feature_hash FROM {PRICE_TABLE}").set_index("listing_id")["feature_hash"]); output["prediction_type"] = "evaluation"; output["predicted_at"] = datetime.now(timezone.utc)
    if not np.isfinite(output[["actual_price", "predicted_price", "actual_log_price", "predicted_log_price", "residual", "absolute_error"]].to_numpy()).all() or (output["predicted_price"] < 0).any():
        raise ValueError("Price prediction output contains invalid numeric values")
    with motherduck.transaction() as connection:
        _ensure_ml_tables(connection); motherduck.append_dataframe(PRICE_PREDICTIONS_TABLE, output.loc[:, ["listing_id", "run_id", "model_version", "feature_hash", "actual_price", "predicted_price", "actual_log_price", "predicted_log_price", "residual", "absolute_error", "prediction_type", "predicted_at"]], connection=connection)
    context.log.info("Wrote %d predictions after %d registry metrics", len(output), price_registry_records)
    return len(output)


@asset(group_name="segmentation")
def gold_listing_segments(context, segmentation_training_result: SegmentationTrainingResult, segmentation_registry_records: int, motherduck: MotherDuckResource) -> int:
    """Append assignment and profile outputs transactionally for one model version."""
    assignments = segmentation_training_result.assignments.copy()
    profiles = segmentation_training_result.profiles.copy()
    with motherduck.transaction() as connection:
        _ensure_ml_tables(connection)
        assignments = assignments.assign(run_id=segmentation_training_result.run["run_id"], feature_hash=assignments["listing_id"].map(motherduck.query_df(f"SELECT listing_id, feature_hash FROM {SEGMENTATION_TABLE}").set_index("listing_id")["feature_hash"]))
        motherduck.append_dataframe(SEGMENT_ASSIGNMENTS_TABLE, assignments.loc[:, ["listing_id", "run_id", "model_version", "feature_hash", "cluster_id", "cluster_name", "distance_to_centroid", "assigned_at"]], connection=connection)
        motherduck.append_dataframe(SEGMENT_PROFILES_TABLE, profiles.loc[:, ["model_version", "cluster_id", "cluster_name", "listing_count", "median_price", "avg_price", "listing_share", "accommodates_mean", "bedrooms_mean", "bathrooms_mean", "beds_mean", "amenities_count_mean", "minimum_nights_log_mean", "dominant_room_type", "dominant_property_base_group", "created_at"]], connection=connection)
    context.log.info("Wrote %d assignments and %d profiles after %d registry metrics", len(assignments), len(profiles), segmentation_registry_records)
    return len(assignments)


@asset(deps=[AssetKey("gold_listing_segments")], group_name="segmentation")
def gold_segment_profiles(segmentation_training_result: SegmentationTrainingResult) -> int:
    """Represent profiles atomically persisted with the segment-assignment asset."""
    return len(segmentation_training_result.profiles)
