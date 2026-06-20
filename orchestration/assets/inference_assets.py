"""Inference-only Dagster assets: load a registered model, then predict or assign."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from dagster import AssetKey, asset

from ml.listing_segmentation.prediction import assign_clusters, load_segmentation_model
from ml.price_modeling.prediction import load_price_model, predict_price
from ml.price_modeling.preprocessing import prepare_modeling_frame
from orchestration.assets.ml_assets import PRICE_TABLE, SEGMENTATION_TABLE, _ensure_ml_tables
from orchestration.resources.inference import InferenceConfig
from orchestration.resources.motherduck import MotherDuckResource


@dataclass(frozen=True)
class RegisteredModel:
    """Minimal registry metadata required for safe inference."""

    model_version: str
    artifact_path: Path
    model_name: str
    status: str


def select_registered_model(records: pd.DataFrame, *, model_task: str, allow_latest_candidate_fallback: bool) -> RegisteredModel:
    """Select a champion, or explicitly permitted latest candidate, from registry rows."""
    required = {"model_version", "artifact_path", "model_name", "status"}
    missing = sorted(required.difference(records.columns))
    if missing:
        raise ValueError(f"Registry response for {model_task} is missing columns: {missing}")
    champions = records.loc[records["status"].eq("CHAMPION")]
    selected = champions.iloc[0] if not champions.empty else None
    if selected is None and allow_latest_candidate_fallback:
        candidates = records.loc[records["status"].eq("CANDIDATE")]
        if not candidates.empty:
            selected = candidates.iloc[0]
    if selected is None:
        raise RuntimeError(f"No CHAMPION model is registered for {model_task}; candidate fallback is disabled or unavailable")
    path = Path(str(selected["artifact_path"]))
    if not path.is_file():
        raise FileNotFoundError(f"Registered artifact is unavailable for {model_task}: {path}")
    return RegisteredModel(str(selected["model_version"]), path, str(selected["model_name"]), str(selected["status"]))


def _lookup_model(motherduck: MotherDuckResource, *, model_task: str, fallback: bool) -> RegisteredModel:
    """Query registry with champions first and candidates only when configured."""
    statuses = ["CHAMPION", "CANDIDATE"] if fallback else ["CHAMPION"]
    placeholders = ", ".join("?" for _ in statuses)
    records = motherduck.query_df(
        f"SELECT model_version, artifact_path, model_name, status FROM gold.gold_ml_model_registry WHERE model_task = ? AND status IN ({placeholders}) ORDER BY CASE status WHEN 'CHAMPION' THEN 0 ELSE 1 END, created_at DESC",
        [model_task, *statuses],
    )
    return select_registered_model(records, model_task=model_task, allow_latest_candidate_fallback=fallback)


def _artifact_features(artifact_path: Path) -> list[str]:
    """Read the ML-owned artifact schema without duplicating feature definitions."""
    schema_path = artifact_path.parent / "feature_schema.json"
    if not schema_path.is_file():
        raise FileNotFoundError(f"Artifact feature schema is unavailable: {schema_path}")
    features = json.loads(schema_path.read_text(encoding="utf-8")).get("features")
    if not isinstance(features, list) or not features:
        raise ValueError(f"Artifact feature schema is invalid: {schema_path}")
    return [str(feature) for feature in features]


@asset(group_name="price")
def current_price_champion(context, motherduck: MotherDuckResource, inference_config: InferenceConfig) -> RegisteredModel:
    """Load registry metadata for the price champion without training or promotion."""
    model = _lookup_model(motherduck, model_task="price_prediction", fallback=inference_config.allow_latest_candidate_fallback)
    context.log.info("Price inference using version=%s status=%s artifact=%s", model.model_version, model.status, model.artifact_path)
    return model


@asset(group_name="segmentation")
def current_segmentation_champion(context, motherduck: MotherDuckResource, inference_config: InferenceConfig) -> RegisteredModel:
    """Load registry metadata for the segmentation champion without fitting KMeans."""
    model = _lookup_model(motherduck, model_task="listing_segmentation", fallback=inference_config.allow_latest_candidate_fallback)
    mapping_path = model.artifact_path.parent / "cluster_mapping.json"
    if not mapping_path.is_file():
        raise FileNotFoundError(f"Segmentation cluster mapping is unavailable: {mapping_path}")
    context.log.info("Segmentation inference using version=%s status=%s artifact=%s", model.model_version, model.status, model.artifact_path)
    return model


@asset(deps=[AssetKey(["gold", "gold_price_model_features"])], group_name="price")
def price_batch_predictions(context, current_price_champion: RegisteredModel, motherduck: MotherDuckResource) -> pd.DataFrame:
    """Create a batch prediction frame without target-dependent evaluation or retraining."""
    started = datetime.now(timezone.utc)
    data = motherduck.query_df(f"SELECT * FROM {PRICE_TABLE} LIMIT 100")
    if data.empty or "listing_id" not in data:
        raise ValueError("Price inference input is empty or missing listing_id")
    prepared = prepare_modeling_frame(data)
    if len(prepared) != len(data):
        raise ValueError("Price inference input was unexpectedly filtered during ML feature preparation")
    model = load_price_model(current_price_champion.artifact_path)
    predictions = predict_price(model, prepared, _artifact_features(current_price_champion.artifact_path))
    if len(predictions) != len(prepared) or not np.isfinite(predictions.to_numpy()).all() or (predictions["predicted_price"] < 0).any():
        raise ValueError("Price batch prediction validation failed")
    output = pd.DataFrame({"prediction_run_id": context.run_id, "model_version": current_price_champion.model_version, "listing_id": prepared["listing_id"].to_numpy(), "predicted_log_price": predictions["predicted_log_price"].to_numpy(), "predicted_price": predictions["predicted_price"].to_numpy(), "prediction_type": "batch", "predicted_at": started})
    context.log.info("Price prediction run=%s version=%s rows=%d seconds=%.3f", context.run_id, current_price_champion.model_version, len(output), (datetime.now(timezone.utc) - started).total_seconds())
    return output


@asset(deps=[AssetKey(["gold", "gold_cluster_model_features"])], group_name="segmentation")
def segmentation_assignments(context, current_segmentation_champion: RegisteredModel, motherduck: MotherDuckResource) -> pd.DataFrame:
    """Assign clusters with a persisted model without fitting preprocessing or KMeans."""
    started = datetime.now(timezone.utc)
    data = motherduck.query_df(f"SELECT * FROM {SEGMENTATION_TABLE}")
    if data.empty:
        raise ValueError("Segmentation inference input is empty")
    model = load_segmentation_model(current_segmentation_champion.artifact_path)
    assignments = assign_clusters(model, data, required_features=_artifact_features(current_segmentation_champion.artifact_path), model_version=current_segmentation_champion.model_version)
    if len(assignments) != len(data) or not assignments["listing_id"].is_unique:
        raise ValueError("Segmentation assignment row-count or uniqueness validation failed")
    assignments.insert(0, "assignment_run_id", context.run_id)
    context.log.info("Segmentation assignment run=%s version=%s rows=%d seconds=%.3f", context.run_id, current_segmentation_champion.model_version, len(assignments), (datetime.now(timezone.utc) - started).total_seconds())
    return assignments


@asset(group_name="price")
def write_price_batch_predictions(price_batch_predictions: pd.DataFrame, motherduck: MotherDuckResource) -> int:
    """Append one validated inference batch without registry or artifact mutation."""
    if price_batch_predictions.empty or price_batch_predictions.duplicated(["prediction_run_id", "listing_id"]).any():
        raise ValueError("Price inference output is empty or contains duplicate run/listing keys")
    with motherduck.transaction() as connection:
        _ensure_ml_tables(connection)
        existing = connection.execute("SELECT COUNT(*) FROM gold.gold_price_predictions WHERE prediction_run_id = ?", [price_batch_predictions["prediction_run_id"].iloc[0]]).fetchone()[0]
        if existing:
            raise RuntimeError("Price prediction run was already written")
        output = price_batch_predictions.assign(actual_price=None, actual_log_price=None, residual=None, absolute_error=None, prediction_date=price_batch_predictions["predicted_at"])
        motherduck.append_dataframe("gold.gold_price_predictions", output.loc[:, ["model_version", "listing_id", "actual_price", "predicted_price", "actual_log_price", "predicted_log_price", "residual", "absolute_error", "prediction_date", "prediction_run_id", "prediction_type", "predicted_at"]], connection=connection)
    return len(price_batch_predictions)


@asset(group_name="segmentation")
def write_segmentation_assignments(segmentation_assignments: pd.DataFrame, motherduck: MotherDuckResource) -> int:
    """Append one validated assignment batch without fitting or registry mutation."""
    if segmentation_assignments.empty or segmentation_assignments.duplicated(["assignment_run_id", "listing_id"]).any():
        raise ValueError("Segmentation inference output is empty or contains duplicate run/listing keys")
    with motherduck.transaction() as connection:
        _ensure_ml_tables(connection)
        existing = connection.execute("SELECT COUNT(*) FROM gold.gold_listing_segments WHERE assignment_run_id = ?", [segmentation_assignments["assignment_run_id"].iloc[0]]).fetchone()[0]
        if existing:
            raise RuntimeError("Segmentation assignment run was already written")
        motherduck.append_dataframe("gold.gold_listing_segments", segmentation_assignments.loc[:, ["listing_id", "model_version", "cluster_id", "cluster_name", "distance_to_centroid", "assigned_at", "assignment_run_id"]], connection=connection)
    return len(segmentation_assignments)
