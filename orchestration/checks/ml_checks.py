"""Output validation checks that never mutate data or artifacts."""

from __future__ import annotations

import numpy as np
import pandas as pd
from dagster import AssetCheckResult, asset_check

from ml.price_modeling.pipeline import TrainingResult as PriceTrainingResult
from ml.listing_segmentation.config import N_CLUSTERS
from ml.listing_segmentation.pipeline import TrainingResult as SegmentationTrainingResult


@asset_check(asset="price_training_result")
def price_training_check(price_training_result: PriceTrainingResult) -> AssetCheckResult:
    """Check price artifact, finite RMSE and valid non-negative predictions."""
    predictions = price_training_result.predictions
    model_version_valid = predictions["model_version"].nunique() == 1 if "model_version" in predictions else True
    passed = price_training_result.artifact_paths["model"].is_file() and np.isfinite(price_training_result.metrics["rmse"]) and not predictions.empty and np.isfinite(predictions[["predicted_log_price", "predicted_price"]].to_numpy()).all() and not (predictions["predicted_price"] < 0).any() and predictions["listing_id"].notna().all() and model_version_valid
    return AssetCheckResult(passed=passed, metadata={"model_version": price_training_result.model_version, "rmse": price_training_result.metrics["rmse"]})


@asset_check(asset="segmentation_training_result")
def segmentation_training_check(segmentation_training_result: SegmentationTrainingResult) -> AssetCheckResult:
    """Check persisted KMeans output retains its configured cluster contract."""
    assignments = segmentation_training_result.assignments
    valid_ids = assignments["cluster_id"].between(0, N_CLUSTERS - 1).all()
    passed = segmentation_training_result.artifact_paths["model"].is_file() and not assignments.empty and assignments["listing_id"].is_unique and valid_ids and assignments["cluster_name"].notna().all() and assignments["model_version"].nunique() == 1
    return AssetCheckResult(passed=passed, metadata={"model_version": segmentation_training_result.model_version, "rows": len(assignments), "n_clusters": assignments["cluster_id"].nunique()})


@asset_check(asset="price_batch_predictions")
def price_prediction_check(price_batch_predictions: pd.DataFrame) -> AssetCheckResult:
    """Check inference output is one finite, non-negative prediction per listing."""
    passed = not price_batch_predictions.empty and price_batch_predictions["listing_id"].is_unique and price_batch_predictions["model_version"].nunique() == 1 and np.isfinite(price_batch_predictions[["predicted_log_price", "predicted_price"]].to_numpy()).all() and not (price_batch_predictions["predicted_price"] < 0).any()
    return AssetCheckResult(passed=passed, metadata={"rows": len(price_batch_predictions)})


@asset_check(asset="segmentation_assignments")
def segmentation_assignment_check(segmentation_assignments: pd.DataFrame) -> AssetCheckResult:
    """Check inference output has one valid named cluster per listing."""
    valid_ids = segmentation_assignments["cluster_id"].between(0, N_CLUSTERS - 1).all()
    passed = not segmentation_assignments.empty and segmentation_assignments["listing_id"].is_unique and segmentation_assignments["model_version"].nunique() == 1 and segmentation_assignments["cluster_name"].notna().all() and valid_ids
    return AssetCheckResult(passed=passed, metadata={"rows": len(segmentation_assignments)})
