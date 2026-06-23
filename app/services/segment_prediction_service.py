"""Segment Champion prediction and cluster-market reads for Model Lab prediction."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import streamlit as st

from services.model_performance_service import QueryResult, _read, get_model_registry

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEGMENT_MODEL_NAME = "segmentation_model"
MIN_SEGMENT_DISTRIBUTION_SIZE = 5
SEGMENT_ONLY_INPUT_SCHEMA = {
    "beds": {"label": "Beds", "min": 0.0, "max": 30.0, "step": 0.5, "default": 1.0},
    "amenities_count": {"label": "Amenities Count", "min": 0, "max": 1000, "default": 0},
}


@dataclass(frozen=True)
class SegmentPredictionResult:
    cluster_id: int
    cluster_name: str
    distance_to_centroid: float | None
    model_version: str


def get_active_segment_champion() -> tuple[pd.Series | None, str | None]:
    registry, error = get_model_registry(SEGMENT_MODEL_NAME)
    if error: return None, error
    champions = registry[registry["stage"].astype(str).str.strip().str.upper().eq("CHAMPION") & registry["is_active"].fillna(False)]
    if len(champions) != 1: return None, "No single active Segment Model Champion is available."
    return champions.iloc[0], None


def _artifact_path(value: str) -> Path | None:
    candidate = Path(value); resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try: resolved.relative_to(PROJECT_ROOT)
    except ValueError: return None
    return resolved if resolved.is_file() else None


def get_segment_input_features(champion: pd.Series | None) -> tuple[list[str], str | None]:
    if champion is None: return [], "Segment prediction is unavailable for the active Segment Champion."
    path = _artifact_path(str(champion.get("artifact_path", "")))
    if path is None: return [], "Segment prediction is unavailable for the active Segment Champion."
    try:
        features = json.loads((path.parent / "feature_schema.json").read_text(encoding="utf-8")).get("features")
        if not isinstance(features, list) or not all(isinstance(feature, str) for feature in features): raise ValueError("invalid schema")
        return features, None
    except Exception:
        LOGGER.exception("Could not load Segment Champion schema")
        return [], "Segment prediction is unavailable for the active Segment Champion."


def build_segment_input_frame(form_values: dict[str, Any], expected_features: list[str]) -> pd.DataFrame:
    """Build the Segment-only raw frame; derived minimum_nights_log is explicit."""
    values = dict(form_values)
    if "minimum_nights_log" in expected_features and "minimum_nights_log" not in values:
        if "minimum_nights" not in values: raise ValueError("Missing source field minimum_nights for Segment Model")
        values["minimum_nights_log"] = float(np.log1p(float(values["minimum_nights"])))
    missing = [name for name in expected_features if name not in values]
    if missing: raise ValueError(f"Missing Segment Model features: {missing}")
    frame = pd.DataFrame([{name: values[name] for name in expected_features}])
    for name in expected_features:
        if name not in {"room_type", "property_base_group"}:
            frame[name] = pd.to_numeric(frame[name], errors="raise")
    return frame.loc[:, expected_features]


@st.cache_resource(show_spinner=False)
def _load_segment_artifact(model_version: str, artifact_path: str) -> Any | None:
    path = _artifact_path(artifact_path)
    if path is None: return None
    try: return joblib.load(path)
    except Exception: LOGGER.exception("Could not load Segment Champion artifact %s", model_version); return None


def predict_listing_segment(input_data: dict[str, Any], champion: pd.Series) -> tuple[SegmentPredictionResult | None, str | None]:
    features, error = get_segment_input_features(champion)
    artifact = _load_segment_artifact(str(champion["model_version"]), str(champion["artifact_path"]))
    if error or artifact is None: return None, error or "Segment prediction is unavailable for the active Segment Champion."
    try:
        frame = build_segment_input_frame(input_data, features)
        model = artifact.get("model") if isinstance(artifact, dict) and "model" in artifact else artifact
        cluster_id = int(np.asarray(model.predict(frame.loc[:, features])).reshape(-1)[0])
        mapping_path = _artifact_path(str(champion["artifact_path"])).parent / "cluster_mapping.json"
        mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.is_file() else {}
        distance = None
        if hasattr(model, "transform"):
            distance = float(np.asarray(model.transform(frame.loc[:, features])).reshape(1, -1)[0, cluster_id])
        return SegmentPredictionResult(cluster_id, str(mapping.get(str(cluster_id), f"Cluster {cluster_id}")), distance, str(champion["model_version"])), None
    except Exception:
        LOGGER.exception("Segment prediction failed")
        return None, "Segment prediction is unavailable for the active Segment Champion."


def get_cluster_profile(model_version: str, cluster_id: int | str) -> QueryResult:
    return _read("select * from gold.gold_cluster_profiles where model_version = ? and cluster_id = ?", (model_version, cluster_id))


def get_cluster_price_distribution(model_version: str, cluster_id: int | str) -> QueryResult:
    return _read(
        "select features.price as actual_price from gold.gold_listing_cluster_assignments assignments "
        "inner join gold.gold_cluster_model_features features on assignments.listing_id = features.listing_id "
        "where assignments.model_version = ? and assignments.cluster_id = ? and features.price is not null and features.price > 0",
        (model_version, cluster_id),
    )
