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
    """Create the minimal append-only ML result tables when absent."""
    connection.execute("CREATE SCHEMA IF NOT EXISTS gold")
    statements = [
        "CREATE TABLE IF NOT EXISTS gold.gold_ml_training_runs (run_id VARCHAR, model_version VARCHAR, model_task VARCHAR, training_mode VARCHAR, model_name VARCHAR, started_at TIMESTAMP, status VARCHAR)",
        "CREATE TABLE IF NOT EXISTS gold.gold_ml_model_registry (model_version VARCHAR, model_task VARCHAR, model_name VARCHAR, artifact_path VARCHAR, status VARCHAR, created_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS gold.gold_ml_model_metrics (model_version VARCHAR, model_task VARCHAR, dataset_type VARCHAR, metric_name VARCHAR, metric_value DOUBLE, metric_std DOUBLE, evaluated_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS gold.gold_price_predictions (model_version VARCHAR, listing_id BIGINT, actual_price DOUBLE, predicted_price DOUBLE, actual_log_price DOUBLE, predicted_log_price DOUBLE, residual DOUBLE, absolute_error DOUBLE, prediction_date TIMESTAMP, prediction_run_id VARCHAR, prediction_type VARCHAR, predicted_at TIMESTAMP)",
        "CREATE TABLE IF NOT EXISTS gold.gold_listing_segments (listing_id BIGINT, model_version VARCHAR, cluster_id INTEGER, cluster_name VARCHAR, distance_to_centroid DOUBLE, assigned_at TIMESTAMP, assignment_run_id VARCHAR)",
        "CREATE TABLE IF NOT EXISTS gold.gold_segment_profiles (model_version VARCHAR, cluster_id INTEGER, cluster_name VARCHAR, listing_count BIGINT, median_price DOUBLE, avg_price DOUBLE, listing_share DOUBLE, accommodates_mean DOUBLE, bedrooms_mean DOUBLE, bathrooms_mean DOUBLE, beds_mean DOUBLE, amenities_count_mean DOUBLE, minimum_nights_log_mean DOUBLE, dominant_room_type VARCHAR, dominant_property_base_group VARCHAR, created_at TIMESTAMP)",
    ]
    for statement in statements:
        connection.execute(statement)
    connection.execute("ALTER TABLE gold.gold_price_predictions ADD COLUMN IF NOT EXISTS prediction_run_id VARCHAR")
    connection.execute("ALTER TABLE gold.gold_price_predictions ADD COLUMN IF NOT EXISTS prediction_type VARCHAR")
    connection.execute("ALTER TABLE gold.gold_price_predictions ADD COLUMN IF NOT EXISTS predicted_at TIMESTAMP")
    connection.execute("ALTER TABLE gold.gold_listing_segments ADD COLUMN IF NOT EXISTS assignment_run_id VARCHAR")


def _write_registry(motherduck: MotherDuckResource, result: Any, model_task: str) -> int:
    run = pd.DataFrame([{**result.run, "model_task": model_task}]).loc[:, ["run_id", "model_version", "model_task", "training_mode", "model_name", "started_at", "status"]]
    registry = pd.DataFrame([{**result.registry, "model_task": model_task, "status": "CANDIDATE", "created_at": datetime.now(timezone.utc)}]).loc[:, ["model_version", "model_task", "model_name", "artifact_path", "status", "created_at"]]
    metrics = result.metric_records.copy(); metrics.insert(1, "model_task", model_task)
    with motherduck.transaction() as connection:
        _ensure_ml_tables(connection)
        motherduck.append_dataframe("gold.gold_ml_training_runs", run, connection=connection)
        motherduck.append_dataframe("gold.gold_ml_model_registry", registry, connection=connection)
        motherduck.append_dataframe("gold.gold_ml_model_metrics", metrics, connection=connection)
    return len(metrics)


@asset(group_name="price")
def price_registry_records(context, price_training_result: PriceTrainingResult, motherduck: MotherDuckResource) -> int:
    """Append price run, registry and metric records transactionally as CANDIDATE."""
    count = _write_registry(motherduck, price_training_result, "price_prediction")
    context.log.info("Wrote %d price metric records", count)
    return count


@asset(group_name="segmentation")
def segmentation_registry_records(context, segmentation_training_result: SegmentationTrainingResult, motherduck: MotherDuckResource) -> int:
    """Append segmentation run, registry and metric records transactionally as CANDIDATE."""
    count = _write_registry(motherduck, segmentation_training_result, "listing_segmentation")
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
    output = predictions.loc[:, required].copy(); output.insert(0, "model_version", price_training_result.model_version); output["prediction_date"] = datetime.now(timezone.utc); output["prediction_run_id"] = None; output["prediction_type"] = "evaluation"; output["predicted_at"] = output["prediction_date"]
    if not np.isfinite(output[["actual_price", "predicted_price", "actual_log_price", "predicted_log_price", "residual", "absolute_error"]].to_numpy()).all() or (output["predicted_price"] < 0).any():
        raise ValueError("Price prediction output contains invalid numeric values")
    with motherduck.transaction() as connection:
        _ensure_ml_tables(connection); motherduck.append_dataframe("gold.gold_price_predictions", output.loc[:, ["model_version", "listing_id", "actual_price", "predicted_price", "actual_log_price", "predicted_log_price", "residual", "absolute_error", "prediction_date", "prediction_run_id", "prediction_type", "predicted_at"]], connection=connection)
    context.log.info("Wrote %d predictions after %d registry metrics", len(output), price_registry_records)
    return len(output)


@asset(group_name="segmentation")
def gold_listing_segments(context, segmentation_training_result: SegmentationTrainingResult, segmentation_registry_records: int, motherduck: MotherDuckResource) -> int:
    """Append assignment and profile outputs transactionally for one model version."""
    assignments = segmentation_training_result.assignments.copy()
    profiles = segmentation_training_result.profiles.copy()
    with motherduck.transaction() as connection:
        _ensure_ml_tables(connection)
        assignments = assignments.assign(assignment_run_id=None)
        motherduck.append_dataframe("gold.gold_listing_segments", assignments.loc[:, ["listing_id", "model_version", "cluster_id", "cluster_name", "distance_to_centroid", "assigned_at", "assignment_run_id"]], connection=connection)
        motherduck.append_dataframe("gold.gold_segment_profiles", profiles.loc[:, ["model_version", "cluster_id", "cluster_name", "listing_count", "median_price", "avg_price", "listing_share", "accommodates_mean", "bedrooms_mean", "bathrooms_mean", "beds_mean", "amenities_count_mean", "minimum_nights_log_mean", "dominant_room_type", "dominant_property_base_group", "created_at"]], connection=connection)
    context.log.info("Wrote %d assignments and %d profiles after %d registry metrics", len(assignments), len(profiles), segmentation_registry_records)
    return len(assignments)


@asset(deps=[AssetKey("gold_listing_segments")], group_name="segmentation")
def gold_segment_profiles(segmentation_training_result: SegmentationTrainingResult) -> int:
    """Represent profiles atomically persisted with the segment-assignment asset."""
    return len(segmentation_training_result.profiles)
