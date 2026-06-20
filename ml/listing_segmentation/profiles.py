"""Cluster assignment and profile construction using existing business rules."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from ml.listing_segmentation.config import MODEL_FEATURES, SEGMENT_MAP
from ml.listing_segmentation.evaluate import build_cluster_profiles as _build_legacy_profiles
from ml.listing_segmentation.evaluate import transform_features


def apply_cluster_names(cluster_ids: pd.Series) -> pd.Series:
    """Map stable KMeans labels to the existing business segment names."""
    return cluster_ids.map(SEGMENT_MAP).fillna("Unknown")


def build_cluster_assignments(model: Pipeline, data: pd.DataFrame, *, model_version: str, assigned_at: datetime | None = None) -> pd.DataFrame:
    """Assign clusters and calculate the existing distance-to-centroid metric."""
    assigned_at = assigned_at or datetime.now(timezone.utc)
    labels = model.predict(data[MODEL_FEATURES]).astype(int)
    transformed = transform_features(model, data)
    distances = model.named_steps["kmeans"].transform(transformed)[np.arange(len(data)), labels]
    return pd.DataFrame({"listing_id": data["listing_id"].to_numpy(), "model_version": model_version, "cluster_id": labels, "cluster_name": apply_cluster_names(pd.Series(labels)).to_numpy(), "distance_to_centroid": distances, "assigned_at": assigned_at})


def build_cluster_profiles(data: pd.DataFrame, assignments: pd.DataFrame, *, model_version: str, created_at: datetime | None = None) -> pd.DataFrame:
    """Build exactly the existing cluster profile measures plus traceability fields."""
    created_at = created_at or datetime.now(timezone.utc)
    clustered = data.copy(); clustered["cluster_id"] = assignments["cluster_id"].to_numpy()
    clustered["segment_name"] = assignments["cluster_name"].to_numpy()
    profiles = _build_legacy_profiles(clustered).rename(columns={"price_mean": "avg_price", "price_median": "median_price"})
    profiles.insert(0, "model_version", model_version)
    profiles.insert(2, "cluster_name", apply_cluster_names(profiles["cluster_id"]).to_numpy())
    profiles["created_at"] = created_at
    return profiles
