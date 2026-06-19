"""Evaluation helpers for listing segmentation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    calinski_harabasz_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.pipeline import Pipeline

from ml.listing_segmentation.config import (
    CATEGORICAL_FEATURES,
    MODEL_FEATURES,
    NUMERICAL_FEATURES,
)


def transform_features(model: Pipeline, features: pd.DataFrame) -> np.ndarray:
    """Return the encoded and scaled feature matrix from a fitted pipeline."""
    return model.named_steps["preprocessor"].transform(features[MODEL_FEATURES])


def evaluate_clustering(
    model: Pipeline,
    features: pd.DataFrame,
    cluster_labels: np.ndarray,
) -> dict[str, Any]:
    """Calculate clustering metrics that are meaningful for the fitted model."""
    transformed = transform_features(model, features)
    kmeans = model.named_steps["kmeans"]
    unique_clusters = np.unique(cluster_labels)
    metrics: dict[str, Any] = {
        "inertia": float(kmeans.inertia_),
        "n_clusters_observed": int(len(unique_clusters)),
    }

    if 1 < len(unique_clusters) < len(features):
        metrics["silhouette_score"] = float(silhouette_score(transformed, cluster_labels))
        metrics["calinski_harabasz_score"] = float(
            calinski_harabasz_score(transformed, cluster_labels)
        )
        metrics["davies_bouldin_score"] = float(
            davies_bouldin_score(transformed, cluster_labels)
        )
    else:
        metrics["silhouette_score"] = None
        metrics["calinski_harabasz_score"] = None
        metrics["davies_bouldin_score"] = None

    return metrics


def build_cluster_profiles(clustered: pd.DataFrame) -> pd.DataFrame:
    """Aggregate business-readable profiles for each cluster."""
    total_rows = len(clustered)
    profiles = (
        clustered.groupby("cluster_id", dropna=False)
        .agg(
            listing_count=("listing_id", "count"),
            price_mean=("price", "mean"),
            price_median=("price", "median"),
            accommodates_mean=("accommodates", "mean"),
            bedrooms_mean=("bedrooms", "mean"),
            bathrooms_mean=("bathrooms", "mean"),
            beds_mean=("beds", "mean"),
            amenities_count_mean=("amenities_count", "mean"),
            minimum_nights_log_mean=("minimum_nights_log", "mean"),
            dominant_room_type=("room_type", _mode_or_none),
            dominant_property_base_group=("property_base_group", _mode_or_none),
        )
        .reset_index()
        .sort_values("cluster_id")
    )
    profiles["listing_share"] = profiles["listing_count"] / total_rows
    ordered_columns = [
        "cluster_id",
        "listing_count",
        "listing_share",
        "price_mean",
        "price_median",
        "accommodates_mean",
        "bedrooms_mean",
        "bathrooms_mean",
        "beds_mean",
        "amenities_count_mean",
        "minimum_nights_log_mean",
        "dominant_room_type",
        "dominant_property_base_group",
    ]
    return profiles[ordered_columns]


def build_cluster_metrics_frame(metrics: dict[str, Any]) -> pd.DataFrame:
    """Represent scalar metrics as a CSV-friendly table."""
    return pd.DataFrame(
        [{"metric": metric_name, "value": metric_value} for metric_name, metric_value in metrics.items()]
    )


def build_centroids_frame(model: Pipeline) -> pd.DataFrame:
    """Return cluster centroids in transformed feature space."""
    preprocessor = model.named_steps["preprocessor"]
    kmeans = model.named_steps["kmeans"]
    feature_names = preprocessor.get_feature_names_out(CATEGORICAL_FEATURES + NUMERICAL_FEATURES)
    centroids = pd.DataFrame(kmeans.cluster_centers_, columns=feature_names)
    centroids.insert(0, "cluster_id", range(len(centroids)))
    return centroids


def _mode_or_none(series: pd.Series) -> object:
    modes = series.dropna().mode()
    if modes.empty:
        return None
    return modes.iloc[0]
