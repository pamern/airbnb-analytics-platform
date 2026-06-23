"""Cached application-side access to model-performance warehouse tables."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np
import streamlit as st

from utils.motherduck import close_connection, connect_motherduck
from utils.sql import query_dataframe

QueryResult = tuple[pd.DataFrame, str | None]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShapArtifactData:
    shap_values: np.ndarray
    feature_values: np.ndarray | None
    feature_names: list[str]
    base_values: np.ndarray | float | None
    model_version: str
    output_scale: str


@st.cache_data(ttl=300, show_spinner=False)
def _read(sql: str, parameters: tuple[Any, ...] = ()) -> QueryResult:
    """Run one parameterized query and turn infrastructure failures into UI state."""
    connection = None
    try:
        connection = connect_motherduck(read_only=False)
        return query_dataframe(connection, sql, list(parameters)), None
    except Exception:  # database availability must not break the page
        LOGGER.exception("Model-performance warehouse query failed")
        return pd.DataFrame(), "Model-performance data is temporarily unavailable."
    finally:
        if connection is not None:
            close_connection(connection)


def get_model_registry(model_name: str) -> QueryResult:
    return _read(
        """select model_version, stage, is_active, created_at, promoted_at, promoted_by, artifact_path
        from mlops.model_registry where model_name = ? order by created_at desc""",
        (model_name,),
    )


def get_model_runs(model_name: str, date_from: date | None, date_to: date | None) -> QueryResult:
    clauses, parameters = ["model_name = ?"], [model_name]
    if date_from:
        clauses.append("cast(started_at as date) >= ?")
        parameters.append(date_from)
    if date_to:
        clauses.append("cast(started_at as date) <= ?")
        parameters.append(date_to)
    return _read(
        "select run_id, model_version, run_type, status, started_at, completed_at, artifact_path, error_message "
        "from mlops.model_runs where " + " and ".join(clauses) + " order by started_at desc",
        tuple(parameters),
    )


def get_model_metrics(model_name: str, model_version: str | None = None) -> QueryResult:
    clauses, parameters = ["model_name = ?"], [model_name]
    if model_version:
        clauses.append("model_version = ?")
        parameters.append(model_version)
    return _read(
        "select run_id, model_version, metric_name, metric_value, dataset_split, created_at "
        "from mlops.model_metrics where " + " and ".join(clauses) + " order by created_at desc",
        tuple(parameters),
    )


def get_metric_trend(model_name: str, date_from: date | None, date_to: date | None, model_version: str | None = None, dataset_split: str | None = None) -> QueryResult:
    clauses, parameters = ["metrics.model_name = ?", "runs.status = 'SUCCESS'"], [model_name]
    if date_from:
        clauses.append("cast(runs.started_at as date) >= ?")
        parameters.append(date_from)
    if date_to:
        clauses.append("cast(runs.started_at as date) <= ?")
        parameters.append(date_to)
    if model_version:
        clauses.append("metrics.model_version = ?")
        parameters.append(model_version)
    if dataset_split:
        clauses.append("metrics.dataset_split = ?")
        parameters.append(dataset_split)
    return _read(
        """select metrics.model_version, metrics.metric_name, metrics.metric_value,
                  metrics.dataset_split, runs.started_at
           from mlops.model_metrics as metrics
           inner join (
               select run_id, status, started_at,
                      row_number() over (partition by run_id order by created_at desc) as row_num
               from mlops.model_runs
           ) as runs on metrics.run_id = runs.run_id and runs.row_num = 1
           where """ + " and ".join(clauses) + " order by runs.started_at",
        tuple(parameters),
    )


def get_price_evaluation_predictions(model_version: str | None) -> QueryResult:
    clauses, parameters = ["actual_price is not null", "predicted_price is not null"], []
    if model_version:
        clauses.append("model_version = ?")
        parameters.append(model_version)
    return _read(
        "select listing_id, actual_price, predicted_price, predicted_price - actual_price as prediction_error, model_version "
        "from gold.gold_listing_price_predictions where " + " and ".join(clauses),
        tuple(parameters),
    )


def get_feature_importance(model_version: str | None) -> QueryResult:
    clauses, parameters = ["model_name = 'price_model'", "importance_method = 'shap'", "feature_level = 'ORIGINAL'"], []
    if model_version:
        clauses.append("model_version = ?")
        parameters.append(model_version)
    return _read(
        "select model_version, feature_name, importance_value, importance_method, feature_level "
        "from mlops.model_feature_importance where " + " and ".join(clauses) + " order by importance_value desc",
        tuple(parameters),
    )


def get_cluster_assignments(model_version: str | None) -> QueryResult:
    clauses, parameters = ["1 = 1"], []
    if model_version:
        clauses.append("model_version = ?")
        parameters.append(model_version)
    return _read(
        "select model_version, cluster_id, count(*) as listing_count "
        "from gold.gold_listing_cluster_assignments where " + " and ".join(clauses) +
        " group by model_version, cluster_id order by cluster_id",
        tuple(parameters),
    )


def get_cluster_profiles(model_version: str | None) -> QueryResult:
    """Read actual profile columns rather than assuming a mutable Gold schema."""
    columns, error = _read(
        """select column_name from information_schema.columns
           where table_schema = 'gold' and table_name = 'gold_cluster_profiles'
           order by ordinal_position"""
    )
    if error or columns.empty:
        return pd.DataFrame(), error or "The cluster profiles table is not available."
    names = columns["column_name"].tolist()
    quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in names)
    if model_version and "model_version" in names:
        return _read(f"select {quoted} from gold.gold_cluster_profiles where model_version = ?", (model_version,))
    return _read(f"select {quoted} from gold.gold_cluster_profiles")


@st.cache_data(ttl=300, show_spinner=False)
def get_cluster_pca_data(model_version: str | None) -> QueryResult:
    """Join persisted assignments to Gold clustering features for visualization only."""
    assignment_columns, error = _read(
        "select column_name from information_schema.columns where table_schema = 'gold' "
        "and table_name = 'gold_listing_cluster_assignments' order by ordinal_position"
    )
    feature_columns, feature_error = _read(
        "select column_name from information_schema.columns where table_schema = 'gold' "
        "and table_name = 'gold_cluster_model_features' order by ordinal_position"
    )
    if error or feature_error or assignment_columns.empty or feature_columns.empty:
        return pd.DataFrame(), error or feature_error or "PCA source tables are not available."
    assignments = set(assignment_columns["column_name"])
    features = feature_columns["column_name"].tolist()
    if "listing_id" not in assignments or "listing_id" not in features:
        return pd.DataFrame(), "PCA source tables do not share listing_id."
    assignment_select = ["a.\"listing_id\"", "a.\"cluster_id\""]
    for name in ("cluster_name", "distance_to_centroid", "model_version"):
        if name in assignments:
            assignment_select.append(f'a."{name}"')
    excluded = {"listing_id", "feature_hash", "model_version", "created_at", "updated_at"}
    feature_select = [f'f."{name}" as "feature__{name}"' for name in features if name not in excluded]
    clauses, parameters = ["1 = 1"], []
    if model_version and "model_version" in assignments:
        clauses.append('a."model_version" = ?')
        parameters.append(model_version)
    return _read(
        "select " + ", ".join(assignment_select + feature_select) +
        " from gold.gold_listing_cluster_assignments as a inner join gold.gold_cluster_model_features as f "
        "on a.\"listing_id\" = f.\"listing_id\" where " + " and ".join(clauses),
        tuple(parameters),
    )


def resolve_price_shap_artifacts(champion: pd.Series) -> tuple[dict[str, Path] | None, str | None]:
    """Resolve SHAP files only from the registry-selected Champion directory."""
    artifact = Path(str(champion.get("artifact_path", "")))
    root = Path(__file__).resolve().parents[2]
    resolved = (root / artifact).resolve() if not artifact.is_absolute() else artifact.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, "No SHAP artifact is available for the active Price Champion."
    directory = resolved if resolved.is_dir() else resolved.parent
    files = {"sample_values": directory / "shap_sample_values.parquet", "original_importance": directory / "shap_original_importance.csv", "summary": directory / "shap_sample_summary.json"}
    if not files["sample_values"].is_file():
        return None, "No SHAP artifact is available for the active Price Champion."
    return files, None


@st.cache_data(ttl=300, show_spinner=False)
def load_price_shap_artifact(model_version: str, artifact_path: str) -> tuple[ShapArtifactData | None, str | None]:
    """Adapt the persisted long-format SHAP sample for one exact artifact version."""
    files, error = resolve_price_shap_artifacts(pd.Series({"model_version": model_version, "artifact_path": artifact_path}))
    if error or files is None:
        return None, error
    try:
        frame = pd.read_parquet(files["sample_values"])
        LOGGER.info("Loading SHAP artifact path=%s shape=%s columns=%s dtypes=%s", files["sample_values"], frame.shape, frame.columns.tolist(), frame.dtypes.astype(str).to_dict())
        required = {"feature_name", "shap_value"}
        if not required.issubset(frame):
            return None, "The SHAP artifact format is not supported."
        if "model_version" in frame and not frame["model_version"].astype(str).eq(model_version).all():
            return None, "The SHAP artifact does not match the selected model version."
        sample_key = "sample_id" if "sample_id" in frame else "listing_id" if "listing_id" in frame else None
        if sample_key is None:
            return None, "The SHAP artifact has no sample identifier."
        if frame.duplicated([sample_key, "feature_name"]).any():
            LOGGER.warning("Duplicate SHAP sample-feature records in %s", files["sample_values"])
            return None, "The SHAP artifact contains duplicate sample-feature records."
        matrix = frame.pivot(index=sample_key, columns="feature_name", values="shap_value").sort_index(axis=1)
        values = matrix.to_numpy(dtype=float)
        if values.ndim != 2 or values.shape[1] != len(matrix.columns) or not np.isfinite(values).all():
            return None, "The SHAP artifact contains invalid contribution values."
        feature_values = None
        if "feature_value" in frame:
            raw = frame.pivot(index=sample_key, columns="feature_name", values="feature_value").reindex(index=matrix.index, columns=matrix.columns)
            converted = raw.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
            if converted.shape == values.shape and np.isfinite(converted).any(): feature_values = converted
        base_values: np.ndarray | float | None = None
        if "base_value" in frame:
            base = frame.groupby(sample_key, sort=False)["base_value"].first().reindex(matrix.index).to_numpy(dtype=float)
            if np.isfinite(base).all(): base_values = base
        return ShapArtifactData(values, feature_values, matrix.columns.astype(str).tolist(), base_values, model_version, "log_price"), None
    except Exception:
        LOGGER.exception("Could not parse Price SHAP artifact path=%s", files["sample_values"])
        return None, "The SHAP artifact could not be read."


@st.cache_data(ttl=300, show_spinner=False)
def get_shap_sample_artifact(model_version: str | None) -> QueryResult:
    """Load the SHAP sample belonging exactly to the selected Price Model version."""
    registry, error = get_model_registry("price_model")
    if error:
        return pd.DataFrame(), error
    if registry.empty:
        return pd.DataFrame(), "No SHAP artifact is available for the active Price Champion."
    selected = registry if model_version is None else registry[registry["model_version"].astype(str).eq(model_version)]
    if len(selected) != 1:
        return pd.DataFrame(), "No SHAP artifact is available for the active Price Champion."
    files, artifact_error = resolve_price_shap_artifacts(selected.iloc[0])
    if artifact_error or files is None:
        return pd.DataFrame(), artifact_error
    try:
        sample = pd.read_parquet(files["sample_values"])
        if "model_version" in sample and not sample["model_version"].astype(str).eq(str(selected.iloc[0]["model_version"])).all():
            return pd.DataFrame(), "No SHAP artifact is available for the active Price Champion."
        return sample, None
    except Exception:
        LOGGER.exception("Price Champion SHAP sample could not be read")
        return pd.DataFrame(), "The SHAP sample artifact could not be read."
