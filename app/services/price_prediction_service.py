"""Safe app-side reads, prediction, and confirmed Price Champion promotion."""

from __future__ import annotations

import logging
import json
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
LOGGER = logging.getLogger(__name__)

# Widget rules are centralized here; the active artifact remains the source of
# truth for which of these raw features are required at prediction time.
PRICE_INPUT_SCHEMA: dict[str, dict[str, object]] = {
    "neighbourhood": {"label": "Neighbourhood", "kind": "categorical", "group": "basic"},
    "room_type": {"label": "Room Type", "kind": "categorical", "group": "basic"},
    "property_base_group": {"label": "Property Group", "kind": "categorical", "group": "basic"},
    "accommodates": {"label": "Accommodates", "kind": "integer", "group": "basic", "min": 1, "max": 30, "default": 2},
    "bedrooms": {"label": "Bedrooms", "kind": "number", "group": "basic", "min": 0.0, "max": 30.0, "step": 0.5, "default": 1.0},
    "bathrooms": {"label": "Bathrooms", "kind": "number", "group": "basic", "min": 0.0, "max": 30.0, "step": 0.5, "default": 1.0},
    "review_scores_location": {"label": "Review Score: Location", "kind": "number", "group": "review", "min": 0.0, "max": 5.0, "step": 0.1, "default": 4.5},
    "number_of_reviews_ltm": {"label": "Number of Reviews LTM", "kind": "integer", "group": "review", "min": 0, "max": 10000, "default": 0},
    "minimum_nights": {"label": "Minimum Nights", "kind": "integer", "group": "review", "min": 1, "max": 3650, "default": 1},
    "host_response_time": {"label": "Host Response Time", "kind": "categorical", "group": "host"},
    "host_response_rate": {"label": "Host Response Rate (%)", "kind": "number", "group": "host", "min": 0.0, "max": 100.0, "step": 1.0, "default": 100.0},
    "host_acceptance_rate": {"label": "Host Acceptance Rate (%)", "kind": "number", "group": "host", "min": 0.0, "max": 100.0, "step": 1.0, "default": 100.0},
    "host_listings_count": {"label": "Host Listings Count", "kind": "integer", "group": "host", "min": 0, "max": 100000, "default": 1},
    "calculated_host_listings_count": {"label": "Calculated Host Listings Count", "kind": "integer", "group": "host", "min": 0, "max": 100000, "default": 1},
    "host_total_listings_count": {"label": "Host Total Listings Count", "kind": "integer", "group": "host", "min": 0, "max": 100000, "default": 1},
}


def get_price_input_features(champion: pd.Series | None) -> tuple[list[str], str | None]:
    """Read the exact raw feature schema and target transform from the active artifact."""
    if champion is None:
        return [], "No active Price Model Champion is available."
    artifact_path = str(champion.get("artifact_path", ""))
    model_path, error = _safe_artifact_path(artifact_path)
    if error or model_path is None:
        return [], error
    try:
        schema_path = model_path.parent / "feature_schema.json"
        with schema_path.open(encoding="utf-8") as file:
            schema = json.load(file)
        features = schema.get("features")
        if not isinstance(features, list) or not all(isinstance(feature, str) for feature in features):
            raise ValueError("feature_schema.json has no valid feature list")
        if schema.get("target_column") != "log_price":
            raise ValueError("The active artifact does not confirm a log-price target")
        unknown = sorted(set(features).difference(PRICE_INPUT_SCHEMA))
        if unknown:
            raise ValueError(f"Unsupported feature metadata: {unknown}")
        return features, None
    except Exception:
        LOGGER.exception("Could not load Price Model input schema")
        return [], "The active Champion input schema is unavailable."


def get_price_input_options(features: list[str]) -> tuple[dict[str, list[str]], str | None]:
    """Read categorical values from the Gold feature table, never from UI constants."""
    categorical = [feature for feature in features if PRICE_INPUT_SCHEMA[feature]["kind"] == "categorical"]
    if not categorical:
        return {}, None
    selects = [
        f"select '{feature}' as feature_name, cast(\"{feature}\" as varchar) as option_value "
        f"from gold.gold_price_model_features where \"{feature}\" is not null"
        for feature in categorical
    ]
    values, error = _read("select distinct feature_name, option_value from (" + " union all ".join(selects) + ") options where trim(option_value) <> '' order by feature_name, option_value")
    if error:
        return {}, error
    return {
        feature: values.loc[values["feature_name"].eq(feature), "option_value"].astype(str).tolist()
        for feature in categorical
    }, None


def get_active_price_champion() -> tuple[pd.Series | None, str | None]:
    registry, error = get_model_registry("price_model")
    if error:
        return None, error
    champions = registry[
        registry["stage"].astype(str).str.strip().str.upper().eq("CHAMPION")
        & registry["is_active"].fillna(False)
    ]
    if len(champions) != 1:
        return None, "No single active Price Model Champion is available."
    return champions.iloc[0], None


def get_price_candidates() -> QueryResult:
    return _read(
        """select model_version, created_at, artifact_path from mlops.model_registry
           where model_name = 'price_model' and upper(trim(stage)) = 'CANDIDATE' and is_active = false
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
        features, schema_error = get_price_input_features(champion)
        if schema_error:
            return None, schema_error
        frame = pd.DataFrame([input_data])
        if set(frame.columns) != set(features):
            raise ValueError("Prediction input does not match the active Champion schema")
        frame = frame.loc[:, features]
        value = float(np.asarray(model.predict(frame)).reshape(-1)[0])
        if not np.isfinite(value):
            raise ValueError("Model produced a non-finite value")
        # get_price_input_features verifies the persisted target_column is log_price.
        return float(np.expm1(value)), None
    except Exception:
        LOGGER.exception("Price prediction failed")
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
    transaction_started = False
    try:
        connection = connect_motherduck(read_only=False)
        connection.execute("begin transaction")
        transaction_started = True
        candidate = query_dataframe(connection, "select model_version from mlops.model_registry where model_name = 'price_model' and model_version = ? and upper(trim(stage)) = 'CANDIDATE' and is_active = false", [candidate_version])
        champion = query_dataframe(connection, "select model_version from mlops.model_registry where model_name = 'price_model' and upper(trim(stage)) = 'CHAMPION' and is_active = true", [])
        if len(candidate) != 1 or len(champion) != 1:
            connection.execute("rollback")
            transaction_started = False
            return "Promotion requires exactly one active Champion and one inactive Candidate."
        connection.execute("update mlops.model_registry set stage = 'ARCHIVED', is_active = false where model_name = 'price_model' and upper(trim(stage)) = 'CHAMPION' and is_active = true")
        connection.execute("update mlops.model_registry set stage = 'CHAMPION', is_active = true, promoted_at = current_timestamp, promoted_by = ? where model_name = 'price_model' and model_version = ? and upper(trim(stage)) = 'CANDIDATE' and is_active = false", [promoted_by, candidate_version])
        verified = query_dataframe(
            connection,
            "select model_version from mlops.model_registry where model_name = 'price_model' and upper(trim(stage)) = 'CHAMPION' and is_active = true",
            [],
        )
        if len(verified) != 1 or str(verified.iloc[0]["model_version"]) != candidate_version:
            connection.execute("rollback")
            transaction_started = False
            return "Promotion verification failed; the registry transaction was rolled back."
        connection.execute("commit")
        transaction_started = False
        st.cache_data.clear()
        return None
    except Exception:
        LOGGER.exception("Price Champion promotion failed")
        if connection is not None and transaction_started:
            try:
                connection.execute("rollback")
            except Exception:
                LOGGER.exception("Price Champion promotion rollback failed")
        return "Promotion failed and the registry transaction was rolled back."
    finally:
        if connection is not None:
            close_connection(connection)
