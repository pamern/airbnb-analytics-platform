"""Cached, read-only access to model-performance warehouse tables."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from utils.motherduck import close_connection, connect_motherduck
from utils.sql import query_dataframe

QueryResult = tuple[pd.DataFrame, str | None]


@st.cache_data(ttl=300, show_spinner=False)
def _read(sql: str, parameters: tuple[Any, ...] = ()) -> QueryResult:
    """Run one parameterized read query and turn infrastructure failures into UI state."""
    connection = None
    try:
        connection = connect_motherduck(read_only=True)
        return query_dataframe(connection, sql, list(parameters)), None
    except Exception as exc:  # database availability must not break the page
        return pd.DataFrame(), str(exc)
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


def get_metric_trend(model_name: str, date_from: date | None, date_to: date | None) -> QueryResult:
    clauses, parameters = ["metrics.model_name = ?", "runs.status = 'SUCCESS'"], [model_name]
    if date_from:
        clauses.append("cast(runs.started_at as date) >= ?")
        parameters.append(date_from)
    if date_to:
        clauses.append("cast(runs.started_at as date) <= ?")
        parameters.append(date_to)
    return _read(
        """select metrics.model_version, metrics.metric_name, metrics.metric_value,
                  metrics.dataset_split, runs.started_at
           from mlops.model_metrics as metrics
           inner join mlops.model_runs as runs on metrics.run_id = runs.run_id
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


@st.cache_data(ttl=300, show_spinner=False)
def get_shap_sample_artifact(model_version: str | None) -> QueryResult:
    """Load a persisted SHAP sample if the registry/artifact provides one."""
    registry, error = get_model_registry("price_model")
    if error:
        return pd.DataFrame(), error
    candidates: list[Path] = []
    if not registry.empty:
        selected = registry if model_version is None else registry[registry["model_version"].astype(str).eq(model_version)]
        for artifact_path in selected.get("artifact_path", pd.Series(dtype=str)).dropna():
            path = Path(str(artifact_path))
            candidates.extend([path.parent / "shap_sample_values.parquet", path / "shap_sample_values.parquet"])
    output_root = Path(__file__).resolve().parents[2] / "ml" / "outputs"
    if output_root.exists():
        candidates.extend(output_root.rglob("shap_sample_values.parquet"))
    for path in dict.fromkeys(candidates):
        try:
            if path.exists():
                return pd.read_parquet(path), None
        except Exception:
            return pd.DataFrame(), "The SHAP sample artifact could not be read."
    return pd.DataFrame(), "No SHAP sample artifact is available for this model version."
