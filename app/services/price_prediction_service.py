"""Safe app-side reads, prediction, and confirmed Price Champion promotion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import streamlit as st

from services.model_performance_service import QueryResult, _read, get_model_metrics, get_model_registry
from utils.motherduck import close_connection, connect_motherduck
from utils.sql import query_dataframe

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_active_price_champion() -> tuple[pd.Series | None, str | None]:
    registry, error = get_model_registry("price_model")
    if error:
        return None, error
    champions = registry[registry["stage"].astype(str).str.upper().eq("CHAMPION") & registry["is_active"].fillna(False)]
    if len(champions) != 1:
        return None, "No single active Price Model Champion is available."
    return champions.iloc[0], None


def get_price_candidates() -> QueryResult:
    return _read(
        """select model_version, created_at, artifact_path from mlops.model_registry
           where model_name = 'price_model' and stage = 'CANDIDATE' and is_active = false
           order by created_at desc"""
    )


def get_price_model_metrics(model_version: str) -> QueryResult:
    return get_model_metrics("price_model", model_version)


def _safe_artifact_path(artifact_path: str) -> tuple[Path | None, str | None]:
    candidate = Path(artifact_path)
    resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError:
        return None, "The Champion artifact path is outside the project workspace."
    return (resolved, None) if resolved.is_file() else (None, "The Champion model artifact is missing.")


@st.cache_resource(show_spinner=False)
def load_price_model_artifact(model_version: str, artifact_path: str) -> tuple[Any | None, str | None]:
    path, error = _safe_artifact_path(artifact_path)
    if error:
        return None, error
    try:
        return joblib.load(path), None
    except Exception:
        return None, "The Champion model artifact could not be loaded."


def predict_single_listing(input_data: dict[str, Any], champion: pd.Series) -> tuple[float | None, str | None]:
    model, error = load_price_model_artifact(str(champion["model_version"]), str(champion["artifact_path"]))
    if error:
        return None, error
    try:
        value = float(np.asarray(model.predict(pd.DataFrame([input_data]))).reshape(-1)[0])
        return float(np.expm1(value)), None
    except Exception:
        return None, "Prediction failed because the input does not match the Champion artifact."


def get_comparable_listings(input_data: dict[str, Any]) -> QueryResult:
    return _read(
        """select features.listing_id, features.neighbourhood, features.room_type,
                  predictions.actual_price, predictions.predicted_price,
                  predictions.predicted_price - predictions.actual_price as difference
           from gold.gold_price_model_features as features
           inner join gold.gold_listing_price_predictions as predictions
             on features.listing_id = predictions.listing_id
           where lower(features.neighbourhood) = lower(?) and features.room_type = ?
             and abs(coalesce(features.accommodates, 0) - ?) <= 1
             and abs(coalesce(features.bedrooms, 0) - ?) <= 1
           order by abs(coalesce(features.accommodates, 0) - ?) asc, abs(coalesce(features.bedrooms, 0) - ?) asc
           limit 10""",
        (input_data.get("neighbourhood"), input_data.get("room_type"), input_data.get("accommodates", 0), input_data.get("bedrooms", 0), input_data.get("accommodates", 0), input_data.get("bedrooms", 0)),
    )


def set_price_champion(candidate_version: str, promoted_by: str = "streamlit") -> str | None:
    """Promote one verified candidate atomically; callers must collect confirmation first."""
    connection = None
    try:
        connection = connect_motherduck(read_only=False)
        connection.execute("begin transaction")
        candidate = query_dataframe(connection, "select model_version from mlops.model_registry where model_name = 'price_model' and model_version = ? and stage = 'CANDIDATE' and is_active = false", [candidate_version])
        champion = query_dataframe(connection, "select model_version from mlops.model_registry where model_name = 'price_model' and stage = 'CHAMPION' and is_active = true", [])
        if len(candidate) != 1 or len(champion) != 1:
            connection.execute("rollback")
            return "Promotion requires exactly one active Champion and one inactive Candidate."
        connection.execute("update mlops.model_registry set stage = 'ARCHIVED', is_active = false where model_name = 'price_model' and stage = 'CHAMPION' and is_active = true")
        connection.execute("update mlops.model_registry set stage = 'CHAMPION', is_active = true, promoted_at = current_timestamp, promoted_by = ? where model_name = 'price_model' and model_version = ? and stage = 'CANDIDATE' and is_active = false", [promoted_by, candidate_version])
        connection.execute("commit")
        _read.clear()
        return None
    except Exception:
        if connection is not None:
            try: connection.execute("rollback")
            except Exception: pass
        return "Promotion failed and the registry transaction was rolled back."
    finally:
        if connection is not None: close_connection(connection)
