"""Output and artifact helpers for listing segmentation."""

from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline

from ml.listing_segmentation.config import (
    ASSIGNMENT_COLUMNS,
    ARTIFACT_DIR,
    ARTIFACT_SUFFIX,
    CATEGORICAL_FEATURES,
    CSV_OUTPUT_DIR,
    KMEANS_PARAMS,
    METADATA_OUTPUT_DIR,
    MODEL_FEATURES,
    MODEL_NAME,
    MODEL_DISPLAY_NAME,
    N_CLUSTERS,
    NUMERICAL_FEATURES,
    RANDOM_STATE,
    SOURCE_TABLE,
)


def utc_timestamp() -> datetime:
    return datetime.now(timezone.utc)


def build_artifact_path(run_timestamp: datetime) -> Path:
    timestamp_text = run_timestamp.strftime("%Y%m%d_%H%M%S")
    return ARTIFACT_DIR / f"{timestamp_text}_{ARTIFACT_SUFFIX}"


def save_model_artifact(model: Pipeline, artifact_path: Path) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_path)
    loaded_model = joblib.load(artifact_path)
    if not hasattr(loaded_model, "predict"):
        raise RuntimeError(f"Saved artifact cannot be used for prediction: {artifact_path}")
    return artifact_path


def save_cluster_outputs(
    clustered: pd.DataFrame,
    profiles: pd.DataFrame,
    metrics_frame: pd.DataFrame,
    centroids: pd.DataFrame,
) -> dict[str, Path]:
    CSV_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "cluster_assignments": CSV_OUTPUT_DIR / "01_cluster_assignments.csv",
        "cluster_profiles": CSV_OUTPUT_DIR / "02_cluster_profiles.csv",
        "cluster_metrics": CSV_OUTPUT_DIR / "03_cluster_metrics.csv",
        "cluster_centroids": CSV_OUTPUT_DIR / "04_cluster_centroids.csv",
    }
    clustered[ASSIGNMENT_COLUMNS].to_csv(paths["cluster_assignments"], index=False)
    profiles.to_csv(paths["cluster_profiles"], index=False)
    metrics_frame.to_csv(paths["cluster_metrics"], index=False)
    centroids.to_csv(paths["cluster_centroids"], index=False)
    return paths


def save_metadata(
    *,
    run_timestamp: datetime,
    run_id: str,
    model_version: str,
    assigned_at: str,
    row_count: int,
    metrics: dict[str, Any],
    artifact_path: Path,
    cluster_distribution: list[dict[str, Any]],
    database_write: dict[str, Any] | None = None,
) -> dict[str, Path]:
    METADATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "run_summary": METADATA_OUTPUT_DIR / "01_run_summary.json",
        "feature_schema": METADATA_OUTPUT_DIR / "02_feature_schema.json",
        "model_config": METADATA_OUTPUT_DIR / "03_model_config.json",
    }
    run_summary = {
        "run_id": run_id,
        "model_name": MODEL_NAME,
        "model_display_name": MODEL_DISPLAY_NAME,
        "model_version": model_version,
        "assigned_at": assigned_at,
        "run_timestamp": run_timestamp.isoformat(),
        "run_timezone": "UTC",
        "source_table": SOURCE_TABLE,
        "row_count": row_count,
        "n_clusters": N_CLUSTERS,
        "cluster_distribution": cluster_distribution,
        "random_state": RANDOM_STATE,
        "kmeans_parameters": KMEANS_PARAMS,
        "evaluation_metrics": metrics,
        "local_artifact_filename": artifact_path.name,
        "database_write": database_write,
        "python_version": platform.python_version(),
        "scikit_learn_version": sklearn.__version__,
    }
    feature_schema = {
        "identifier_columns": ["listing_id"],
        "categorical_features": CATEGORICAL_FEATURES,
        "numerical_features": NUMERICAL_FEATURES,
        "model_features": MODEL_FEATURES,
        "excluded_from_model": ["price", "property_type", "minimum_nights"],
    }
    model_config = {
        "model_name": MODEL_NAME,
        "model_display_name": MODEL_DISPLAY_NAME,
        "model_version": model_version,
        "source_table": SOURCE_TABLE,
        "artifact_type": "sklearn_pipeline_joblib",
        "pipeline_steps": ["ColumnTransformer", "OneHotEncoder", "StandardScaler", "KMeans"],
        "kmeans_parameters": KMEANS_PARAMS,
    }
    _write_json(paths["run_summary"], run_summary)
    _write_json(paths["feature_schema"], feature_schema)
    _write_json(paths["model_config"], model_config)
    return paths


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
