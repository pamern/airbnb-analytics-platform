"""Incremental, champion-only inference assets for price and segmentation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from dagster import AssetKey, asset

from ml.common.paths import REPO_ROOT
from ml.listing_segmentation.prediction import assign_clusters, load_segmentation_model
from ml.price_modeling.prediction import load_price_model, predict_price
from ml.price_modeling.preprocessing import prepare_modeling_frame
from orchestration.assets.ml_assets import PRICE_TABLE, SEGMENTATION_TABLE
from orchestration.mlops import (
    PRICE_MODEL_NAME,
    PRICE_PREDICTIONS_TABLE,
    SEGMENT_ASSIGNMENTS_TABLE,
    SEGMENTATION_MODEL_NAME,
    ensure_mlops_tables,
    finish_run,
    start_run,
)
from orchestration.resources.motherduck import MotherDuckResource

BATCH_SIZE = 100


@dataclass(frozen=True)
class RegisteredModel:
    """The single active Champion that is safe to use for inference."""

    model_version: str
    artifact_path: Path
    model_name: str
    stage: str


def _resolve_artifact_path(value: object) -> Path:
    path = Path(str(value))
    resolved = path if path.is_absolute() else REPO_ROOT / path
    return resolved.resolve()


def select_registered_model(records: pd.DataFrame, *, model_name: str) -> RegisteredModel:
    """Require exactly one active Champion; Candidates are never inference fallbacks."""
    required = {"model_version", "artifact_path", "model_name", "stage", "is_active"}
    missing = sorted(required.difference(records.columns))
    if missing:
        raise ValueError(f"Registry response for {model_name} is missing columns: {missing}")
    champions = records.loc[records["stage"].eq("CHAMPION") & records["is_active"].eq(True)]
    if champions.empty:
        raise RuntimeError(f"No active CHAMPION model is registered for {model_name}")
    if len(champions) != 1:
        raise RuntimeError(f"Expected exactly one active CHAMPION for {model_name}, found {len(champions)}")
    selected = champions.iloc[0]
    path = _resolve_artifact_path(selected["artifact_path"])
    if not path.is_file():
        raise FileNotFoundError(f"Registered artifact is unavailable for {model_name}: {path}")
    return RegisteredModel(str(selected["model_version"]), path, str(selected["model_name"]), str(selected["stage"]))


def _lookup_model(motherduck: MotherDuckResource, *, model_name: str) -> RegisteredModel:
    records = motherduck.query_df(
        "SELECT model_version, artifact_path, model_name, stage, is_active FROM mlops.model_registry WHERE model_name = ? AND stage = 'CHAMPION' AND is_active = TRUE",
        [model_name],
    )
    return select_registered_model(records, model_name=model_name)


def _artifact_features(artifact_path: Path) -> list[str]:
    schema_path = artifact_path.parent / "feature_schema.json"
    if not schema_path.is_file():
        raise FileNotFoundError(f"Artifact feature schema is unavailable: {schema_path}")
    features = json.loads(schema_path.read_text(encoding="utf-8")).get("features")
    if not isinstance(features, list) or not features:
        raise ValueError(f"Artifact feature schema is invalid: {schema_path}")
    return [str(feature) for feature in features]


def build_candidate_query(*, feature_table: str, result_table: str, result_time_column: str, model_version: str, result_type_filter: str | None = None) -> tuple[str, list[object]]:
    """Return a parameterized, NULL-safe query for unseen/stale scoring candidates."""
    extra_filter = " AND prediction_type = ?" if result_type_filter else ""
    query = f"""
        WITH latest_result AS (
            SELECT listing_id, feature_hash, model_version,
                   row_number() OVER (PARTITION BY listing_id ORDER BY {result_time_column} DESC) AS row_num
            FROM {result_table}
            WHERE feature_hash IS NOT NULL{extra_filter}
        )
        SELECT current_features.*
        FROM {feature_table} AS current_features
        LEFT JOIN latest_result
          ON current_features.listing_id = latest_result.listing_id
         AND latest_result.row_num = 1
        WHERE (
              latest_result.listing_id IS NULL
           OR latest_result.model_version IS DISTINCT FROM ?
           OR latest_result.feature_hash IS DISTINCT FROM current_features.feature_hash
        )
        AND NOT EXISTS (
            SELECT 1 FROM {result_table} AS historical
            WHERE historical.listing_id = current_features.listing_id
              AND historical.model_version = ?
              AND historical.feature_hash = current_features.feature_hash
        )
        ORDER BY
          CASE WHEN latest_result.listing_id IS NULL THEN 0 ELSE 1 END,
          CASE WHEN latest_result.model_version IS DISTINCT FROM ? THEN 0 ELSE 1 END,
          current_features.listing_id
        LIMIT ?
    """
    parameters: list[object] = []
    if result_type_filter:
        parameters.append(result_type_filter)
    parameters.extend([model_version, model_version, model_version, BATCH_SIZE])
    return query, parameters


@asset(group_name="price")
def current_price_champion(context, motherduck: MotherDuckResource) -> RegisteredModel:
    model = _lookup_model(motherduck, model_name=PRICE_MODEL_NAME)
    context.log.info("Price inference using Champion version=%s artifact=%s", model.model_version, model.artifact_path)
    return model


@asset(group_name="segmentation")
def current_segmentation_champion(context, motherduck: MotherDuckResource) -> RegisteredModel:
    model = _lookup_model(motherduck, model_name=SEGMENTATION_MODEL_NAME)
    mapping_path = model.artifact_path.parent / "cluster_mapping.json"
    if not mapping_path.is_file():
        raise FileNotFoundError(f"Segmentation cluster mapping is unavailable: {mapping_path}")
    context.log.info("Segmentation inference using Champion version=%s artifact=%s", model.model_version, model.artifact_path)
    return model


@asset(deps=[AssetKey(["gold", "gold_price_model_features"])], group_name="price")
def price_batch_predictions(context, current_price_champion: RegisteredModel, motherduck: MotherDuckResource) -> pd.DataFrame:
    """Score at most 100 unseen, feature-changed, or previous-model listings."""
    start_run(motherduck, run_id=context.run_id, job_name="price_prediction_job", model_name=PRICE_MODEL_NAME, model_version=current_price_champion.model_version, run_type="PRICE_PREDICTION", artifact_path=str(current_price_champion.artifact_path.relative_to(REPO_ROOT)))
    try:
        query, parameters = build_candidate_query(feature_table=PRICE_TABLE, result_table=PRICE_PREDICTIONS_TABLE, result_time_column="predicted_at", model_version=current_price_champion.model_version, result_type_filter="batch")
        data = motherduck.query_df(query, parameters)
        if data.empty:
            context.log.info("No price listings require scoring for Champion %s", current_price_champion.model_version)
            return pd.DataFrame(columns=["run_id", "model_version", "listing_id", "feature_hash", "predicted_log_price", "predicted_price", "prediction_type", "predicted_at"])
        prepared = prepare_modeling_frame(data)
        if len(prepared) != len(data):
            raise ValueError("Price inference candidates were unexpectedly filtered during feature preparation")
        predictions = predict_price(load_price_model(current_price_champion.artifact_path), prepared, _artifact_features(current_price_champion.artifact_path))
        if len(predictions) != len(prepared) or not np.isfinite(predictions.to_numpy()).all() or (predictions["predicted_price"] < 0).any():
            raise ValueError("Price batch prediction validation failed")
        return pd.DataFrame({"run_id": context.run_id, "model_version": current_price_champion.model_version, "listing_id": prepared["listing_id"].to_numpy(), "feature_hash": data["feature_hash"].to_numpy(), "predicted_log_price": predictions["predicted_log_price"].to_numpy(), "predicted_price": predictions["predicted_price"].to_numpy(), "prediction_type": "batch", "predicted_at": datetime.now(timezone.utc)})
    except Exception as error:
        finish_run(motherduck, run_id=context.run_id, status="FAILED", error_message=str(error))
        raise


@asset(deps=[AssetKey(["gold", "gold_cluster_model_features"])], group_name="segmentation")
def segmentation_assignments(context, current_segmentation_champion: RegisteredModel, motherduck: MotherDuckResource) -> pd.DataFrame:
    """Assign at most 100 stale listings using the Champion without fitting anything."""
    start_run(motherduck, run_id=context.run_id, job_name="segmentation_assignment_job", model_name=SEGMENTATION_MODEL_NAME, model_version=current_segmentation_champion.model_version, run_type="SEGMENTATION_ASSIGNMENT", artifact_path=str(current_segmentation_champion.artifact_path.relative_to(REPO_ROOT)))
    try:
        query, parameters = build_candidate_query(feature_table=SEGMENTATION_TABLE, result_table=SEGMENT_ASSIGNMENTS_TABLE, result_time_column="assigned_at", model_version=current_segmentation_champion.model_version)
        data = motherduck.query_df(query, parameters)
        if data.empty:
            context.log.info("No listings require segmentation assignment for Champion %s", current_segmentation_champion.model_version)
            return pd.DataFrame(columns=["run_id", "model_version", "listing_id", "feature_hash", "cluster_id", "cluster_name", "distance_to_centroid", "assigned_at"])
        assignments = assign_clusters(load_segmentation_model(current_segmentation_champion.artifact_path), data, required_features=_artifact_features(current_segmentation_champion.artifact_path), model_version=current_segmentation_champion.model_version)
        if len(assignments) != len(data) or not assignments["listing_id"].is_unique:
            raise ValueError("Segmentation assignment row-count or uniqueness validation failed")
        assignments.insert(0, "run_id", context.run_id); assignments.insert(3, "feature_hash", data["feature_hash"].to_numpy())
        return assignments
    except Exception as error:
        finish_run(motherduck, run_id=context.run_id, status="FAILED", error_message=str(error))
        raise


@asset(group_name="price")
def write_price_batch_predictions(context, price_batch_predictions: pd.DataFrame, motherduck: MotherDuckResource) -> int:
    """Atomically write a non-duplicate batch, or successfully record a no-work run."""
    try:
        if price_batch_predictions.empty:
            finish_run(motherduck, run_id=context.run_id, status="SUCCESS")
            return 0
        if price_batch_predictions.duplicated(["run_id", "listing_id"]).any():
            raise ValueError("Price inference output contains duplicate run/listing keys")
        with motherduck.transaction() as connection:
            ensure_mlops_tables(connection)
            duplicate = connection.execute(f"SELECT COUNT(*) FROM {PRICE_PREDICTIONS_TABLE} AS existing JOIN (SELECT ? AS run_id) AS current_run ON existing.run_id = current_run.run_id", [context.run_id]).fetchone()[0]
            if duplicate:
                raise RuntimeError("Price prediction run was already written")
            motherduck.append_dataframe(PRICE_PREDICTIONS_TABLE, price_batch_predictions.assign(actual_price=None, actual_log_price=None, residual=None, absolute_error=None).loc[:, ["listing_id", "run_id", "model_version", "feature_hash", "actual_price", "predicted_price", "actual_log_price", "predicted_log_price", "residual", "absolute_error", "prediction_type", "predicted_at"]], connection=connection)
        finish_run(motherduck, run_id=context.run_id, status="SUCCESS")
        return len(price_batch_predictions)
    except Exception as error:
        finish_run(motherduck, run_id=context.run_id, status="FAILED", error_message=str(error))
        raise


@asset(group_name="segmentation")
def write_segmentation_assignments(context, segmentation_assignments: pd.DataFrame, motherduck: MotherDuckResource) -> int:
    """Atomically write a non-duplicate assignment batch, or a valid no-work run."""
    try:
        if segmentation_assignments.empty:
            finish_run(motherduck, run_id=context.run_id, status="SUCCESS")
            return 0
        if segmentation_assignments.duplicated(["run_id", "listing_id"]).any():
            raise ValueError("Segmentation output contains duplicate run/listing keys")
        with motherduck.transaction() as connection:
            ensure_mlops_tables(connection)
            duplicate = connection.execute(f"SELECT COUNT(*) FROM {SEGMENT_ASSIGNMENTS_TABLE} WHERE run_id = ?", [context.run_id]).fetchone()[0]
            if duplicate:
                raise RuntimeError("Segmentation assignment run was already written")
            motherduck.append_dataframe(SEGMENT_ASSIGNMENTS_TABLE, segmentation_assignments.loc[:, ["listing_id", "run_id", "model_version", "feature_hash", "cluster_id", "cluster_name", "distance_to_centroid", "assigned_at"]], connection=connection)
        finish_run(motherduck, run_id=context.run_id, status="SUCCESS")
        return len(segmentation_assignments)
    except Exception as error:
        finish_run(motherduck, run_id=context.run_id, status="FAILED", error_message=str(error))
        raise
